"""Runs HTTP inputs against the PR's code in a child process, and decides from the results whether they got through.

The model proposes inputs; the checks here decide. The canaries are random per run and the model never sees them, so
a claim of success can't be faked: the response either contains another user's secret or it doesn't.

This child process has no secrets in its environment and a timeout, but it is NOT a real sandbox: it can still reach
the disk and network. That's acceptable for the fixture in sample/. Untrusted PRs need a container with no network.
"""
import json
import os
import secrets
import shlex
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

RUNNER = Path(__file__).resolve().parent / "pr_runner.py"
SHELL_CONTROL = set(";|&()<>`$\n")
SQL_INJECTION, COMMAND_INJECTION, XSS = {"CWE-89"}, {"CWE-77", "CWE-78"}, {"CWE-79", "CWE-80"}
BROKEN_ACCESS = {"CWE-639", "CWE-284", "CWE-285", "CWE-862", "CWE-863"}
VERIFIABLE = SQL_INJECTION | COMMAND_INJECTION | XSS | BROKEN_ACCESS


class SandboxError(RuntimeError):
    pass


def new_canaries() -> dict:
    return {"bob_token": f"tok-{secrets.token_hex(8)}", "bob_memo": f"memo-{secrets.token_hex(8)}"}


def run_probes(app_dir: Path, probes: list[dict], canaries: dict, timeout: int = 20) -> list[dict]:
    env = {k: os.environ[k] for k in ("SYSTEMROOT", "TEMP", "TMP") if k in os.environ}  # allowlist: no API keys
    try:
        done = subprocess.run([sys.executable, "-I", str(RUNNER)], capture_output=True, text=True, encoding="utf-8",
                              env=env, cwd=app_dir, timeout=timeout,
                              input=json.dumps({"app_dir": str(app_dir), "canaries": canaries, "probes": probes}))
    except subprocess.TimeoutExpired as e:
        raise SandboxError(f"timed out after {timeout}s") from e
    if done.returncode != 0:
        tail = done.stderr.strip().splitlines()[-1:] or ["no error output"]
        raise SandboxError(f"app failed to run: {tail[0][:200]}")
    return json.loads(done.stdout)


def shell_injected(command) -> bool:
    """True if a string given to the fake shell would run more than the one intended command. Lists can't."""
    if not isinstance(command, str):
        return False
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace = " \t\r"
    try:
        return any(tok and set(tok) <= SHELL_CONTROL for tok in lexer)
    except ValueError:  # an unbalanced quote: the input broke out of the quoting
        return True


class _ActiveContent(HTMLParser):
    found = False

    def handle_starttag(self, tag, attrs):
        if tag == "script" or any(name.startswith("on") for name, _ in attrs):
            self.found = True
        if any(name in ("href", "src") and (value or "").lower().startswith("javascript:") for name, value in attrs):
            self.found = True


def script_in_page(result: dict) -> bool:
    if not result["content_type"].startswith("text/html"):
        return False
    parser = _ActiveContent()
    parser.feed(result["body"])
    return parser.found


def exploited(cwe: str, results: list[dict], canaries: dict) -> bool:
    if cwe in SQL_INJECTION:
        return any(c in r["body"] for r in results for c in canaries.values())
    if cwe in BROKEN_ACCESS:
        return any(canaries["bob_memo"] in r["body"] for r in results)
    if cwe in COMMAND_INJECTION:
        return any(shell_injected(c) for r in results for c in r["shell_calls"])
    if cwe in XSS:
        return any(script_in_page(r) for r in results)
    raise ValueError(f"no check for {cwe}")


def regressions(app_dir: Path, checks: list[dict]) -> list[str]:
    """Runs the repo's own checks. Returns what broke (empty = behavior kept)."""
    try:
        results = run_probes(app_dir, checks, new_canaries())
    except SandboxError as e:
        return [str(e)]
    broken = []
    for check, r in zip(checks, results):
        if r["status"] != check["status"]:
            broken.append(f"{check['path']}: status {r['status']}, expected {check['status']}")
        elif "contains" in check and check["contains"] not in r["body"]:
            broken.append(f"{check['path']}: response is missing '{check['contains']}'")
        elif "shell_contains" in check and check["shell_contains"] not in str(r["shell_calls"]):
            broken.append(f"{check['path']}: shell was not called with '{check['shell_contains']}'")
    return broken
