"""Day 25 demo: a PR with four planted flaws goes through scan, /verify, /fix, a human /approve, and a green gate.

Run from the repo root (some Claude usage, about 8 model calls). Everything is fake and local: a throwaway git repo,
an app driven through an in-process test client, and a stub shell that never runs anything.
  uv run python day25/demo.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")
sys.path.insert(0, str(HERE))

import mender as m  # noqa: E402

AUTHOR, MAINTAINER, OUTSIDER = "sam", "riley", "drive-by"


def run(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "user.name=sam", "-c", "user.email=sam@example.invalid",
                           *args], cwd=repo, check=True, capture_output=True, text=True, encoding="utf-8").stdout


def commit(repo: Path, name: str, text: str, message: str) -> None:
    (repo / name).write_text(text, encoding="utf-8", newline="\n")
    run(repo, "add", "-A")
    run(repo, "commit", "-m", message)


def make_repo(repo: Path) -> None:
    sample = HERE / "sample"
    run(repo, "init", "-b", "main")
    run(repo, "config", "core.autocrlf", "false")
    (repo / m.CHECKS_FILE).write_text((sample / "ci_checks.json").read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    commit(repo, "app.py", (sample / "base_app.py").read_text(encoding="utf-8"), "base service")
    run(repo, "checkout", "-b", "pr")
    commit(repo, "app.py", (sample / "pr_app.py").read_text(encoding="utf-8"), "add search, ping, hello, invoices")


def say(cm: m.CodeMender, comment_id: str, user: str, permission: str, text: str) -> None:
    print(f"\n{user} ({permission}): {text}\n  -> {cm.on_comment(comment_id, user, permission, text)}")


def main() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        repo = Path(tmp)
        make_repo(repo)
        cm = m.CodeMender(repo, author=AUTHOR)

        print("=== PR opened: scan ===")
        cm.scan()
        print(cm.comment_body)

        print("\n=== Who may ask ===")
        say(cm, "c1", OUTSIDER, "read", "/fix all")

        print("\n=== Prove each finding (the model picks inputs, a separate check decides) ===")
        say(cm, "c2", MAINTAINER, "write", "/verify all")
        for f in cm.findings:
            if f.probes:
                print(f"  {f.id} {f.cwe} proven by: {f.probes[0]['path']} {f.probes[0]['params']}")
        print(cm.comment_body)
        say(cm, "c2", MAINTAINER, "write", "/verify all")
        print("  (the same comment id delivered twice runs once)")

        print("\n=== Stage a patch: the exploit must fail on it and the repo's checks must pass ===")
        say(cm, "c3", MAINTAINER, "write", "/fix all")
        print(cm.comment_body)
        if not cm.staged:
            sys.exit("No patch was staged, so the demo stops here. The gate stays red.")

        print("\n=== The approval has to match this person, this patch and this commit ===")
        stale = cm.staged.id
        say(cm, "c4", AUTHOR, "write", f"/approve {stale}")
        print("\nsam pushes a docs commit while the patch waits")
        commit(repo, "NOTES.md", "release notes\n", "add notes")
        cm.on_push()
        say(cm, "c5", MAINTAINER, "write", f"/approve {stale}")
        say(cm, "c6", MAINTAINER, "write", "/fix all")
        if not cm.staged:
            sys.exit("No patch was staged on the second try, so the demo stops here. The gate stays red.")

        print("\n=== A person approves; the exploit is re-run on the commit; the new code is scanned ===")
        say(cm, "c7", MAINTAINER, "write", f"/approve {cm.staged.id}")
        print(cm.comment_body)

        print("\n=== git log on the PR branch ===")
        print(run(repo, "log", "--format=%h %an: %s", "main..pr").rstrip())

        print("\n=== Audit trail (append-only) ===")
        for event, actor, finding, cwe, detail in cm.audit_rows():
            print(f"  {event:18} {actor:16} {finding or '':3} {cwe or '':8} {' '.join((detail or '').split())[:70]}")
        print(f"\nmodel calls: {m.LLM_CALLS['n']}; sticky comment revisions: {cm.comment_revisions}, still one comment")
        cm.audit_db.close()


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Missing ANTHROPIC_API_KEY: copy day25/.env.example to day25/.env")
    main()
