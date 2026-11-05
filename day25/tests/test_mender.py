"""Day 25 tests: oracles, sandbox environment, gate, commands, approval binding (fake model client, real git + subprocess)."""
import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import mender as m
import pr_sandbox as s

DAY = Path(__file__).resolve().parents[1]
FIXED = (Path(__file__).parent / "fixed_app.py").read_text(encoding="utf-8")
VULN = (DAY / "sample" / "pr_app.py").read_text(encoding="utf-8")
BASE = (DAY / "sample" / "base_app.py").read_text(encoding="utf-8")
CHECKS = (DAY / "sample" / "ci_checks.json").read_text(encoding="utf-8")


def _probe(path, **params):
    return {"method": "GET", "path": path, "params": [{"name": k, "value": v} for k, v in params.items()]}


SQLI = _probe("/search", q="x%' UNION SELECT api_token FROM users --")
CMD = _probe("/ping", host="127.0.0.1; id")
XSS = _probe("/hello", name="<script>alert(1)</script>")
IDOR = _probe("/invoices/2")


def _finding(cwe, function, severity="Critical", line=10):
    return {"cwe": cwe, "title": f"{cwe} issue", "path": "app.py", "line": line, "function": function,
            "severity": severity, "explanation": "why"}


ALL_FOUR = {"findings": [_finding("CWE-89", "search"), _finding("CWE-78", "ping"), _finding("CWE-79", "hello", "High"),
                         _finding("CWE-639", "invoice")]}
NONE = {"findings": []}


class FakeClient:
    """Answers each model call by its schema, from queues; an empty queue means a malformed reply."""

    def __init__(self, scans=(), probes=(), fixes=(), boom=False, stop_reason="end_turn"):
        self.q = {"findings": list(scans), "probes": list(probes), "files": list(fixes)}
        self.boom, self.stop_reason, self.seen = boom, stop_reason, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.seen.append(kw)
        if self.boom:
            raise ConnectionError("api down")
        key = next(k for k in self.q if k in kw["output_config"]["format"]["schema"]["properties"])
        text = json.dumps(self.q[key].pop(0)) if self.q[key] else "{}"
        return SimpleNamespace(stop_reason=self.stop_reason, content=[SimpleNamespace(type="text", text=text)])


def _run(repo, *args):
    subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
                   cwd=repo, check=True, capture_output=True)


def _commit(repo, name, text, msg="change"):
    (repo / name).write_text(text, encoding="utf-8", newline="\n")
    _run(repo, "add", "-A")
    _run(repo, "commit", "-m", msg)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "shop"
    r.mkdir()
    _run(r, "init", "-b", "main")
    _run(r, "config", "core.autocrlf", "false")
    (r / m.CHECKS_FILE).write_text(CHECKS, encoding="utf-8", newline="\n")
    _commit(r, "app.py", BASE, "base")
    _run(r, "checkout", "-b", "pr")
    _commit(r, "app.py", VULN, "add features")
    return r


def _fix(content=FIXED, path="app.py"):
    return {"summary": "fixes", "files": [{"path": path, "content": content}]}


def _app_dir(tmp_path, source):
    d = tmp_path / "copy"
    d.mkdir(exist_ok=True)
    (d / "app.py").write_text(source, encoding="utf-8")
    return d


def _verified(repo, fixes=(), scans=()):
    """A PR with all four findings proven."""
    c = FakeClient(scans=[ALL_FOUR, *scans], probes=[{"probes": [p]} for p in (SQLI, CMD, XSS, IDOR)], fixes=fixes)
    cm = m.CodeMender(repo, author="sam", client=c)
    cm.scan()
    assert cm.on_comment("c1", "riley", "write", "/verify all").startswith("verified")
    return cm, c


# ---------- oracles: the model never decides ----------

@pytest.mark.parametrize("cwe,probe", [("CWE-89", SQLI), ("CWE-78", CMD), ("CWE-79", XSS), ("CWE-639", IDOR)])
def test_each_exploit_works_on_the_vulnerable_app_and_not_on_the_fixed_one(tmp_path, cwe, probe):
    canaries = s.new_canaries()
    assert s.exploited(cwe, s.run_probes(_app_dir(tmp_path, VULN), [probe], canaries), canaries)
    assert not s.exploited(cwe, s.run_probes(_app_dir(tmp_path, FIXED), [probe], canaries), canaries)


def test_harmless_inputs_do_not_count_as_exploits(tmp_path):
    canaries = s.new_canaries()
    d = _app_dir(tmp_path, VULN)
    assert not s.exploited("CWE-89", s.run_probes(d, [_probe("/search", q="Widget")], canaries), canaries)
    assert not s.exploited("CWE-78", s.run_probes(d, [_probe("/ping", host="example.com")], canaries), canaries)
    assert not s.exploited("CWE-79", s.run_probes(d, [_probe("/hello", name="Ann")], canaries), canaries)
    assert not s.exploited("CWE-639", s.run_probes(d, [_probe("/invoices/1")], canaries), canaries)


@pytest.mark.parametrize("command,expected", [
    ("ping -c 1 example.com", False), ("ping -c 1 '127.0.0.1; id'", False), (["ping", "x; id"], False),
    ("ping -c 1 127.0.0.1; id", True), ("ping x | id", True), ("ping $(id)", True), ("ping `id`", True),
    ("ping x\nid", True), ("ping 'unbalanced", True)])
def test_shell_injection_check(command, expected):
    assert s.shell_injected(command) is expected


def test_regression_checks_pass_on_both_versions(tmp_path):
    checks = json.loads(CHECKS)
    assert s.regressions(_app_dir(tmp_path, VULN), checks) == []
    assert s.regressions(_app_dir(tmp_path, FIXED), checks) == []


# ---------- what the PR's code can reach ----------

def test_pr_code_does_not_see_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    src = ("import os\nfrom flask import Flask\ndef create_app(conn, shell):\n    app = Flask(__name__)\n"
           "    @app.get('/env')\n    def env():\n        return os.environ.get('ANTHROPIC_API_KEY', 'absent')\n"
           "    return app\n")
    assert s.run_probes(_app_dir(tmp_path, src), [_probe("/env")], s.new_canaries())[0]["body"] == "absent"


def test_prints_from_pr_code_do_not_corrupt_results(tmp_path):
    src = VULN + "\nprint('[]')\n"
    assert s.run_probes(_app_dir(tmp_path, src), [_probe("/health")], s.new_canaries())[0]["status"] == 200


def test_app_that_will_not_load_is_a_sandbox_error(tmp_path):
    with pytest.raises(s.SandboxError):
        s.run_probes(_app_dir(tmp_path, "this is not python"), [_probe("/x")], s.new_canaries())


def test_hanging_app_times_out(tmp_path):
    with pytest.raises(s.SandboxError, match="timed out"):
        s.run_probes(_app_dir(tmp_path, "import time\ntime.sleep(30)\n"), [_probe("/x")], s.new_canaries(), timeout=1)


# ---------- scan and gate ----------

def test_scan_blocks_on_critical_and_keeps_one_sticky_comment(repo):
    cm = m.CodeMender(repo, author="sam", client=FakeClient(scans=[ALL_FOUR]))
    cm.scan()
    assert cm.gate()[0] == "failure" and "F1, F2, F4" in cm.gate()[1]
    assert cm.comment_body.startswith(m.MARKER) and cm.comment_body.count(m.MARKER) == 1
    assert "F3" in cm.comment_body


def test_scan_treats_pr_text_as_untrusted(repo):
    c = FakeClient(scans=[NONE])
    m.CodeMender(repo, author="sam", client=c).scan()
    assert "untrusted" in c.seen[0]["system"] and "<PR>" in c.seen[0]["messages"][0]["content"]
    assert c.seen[0]["fallbacks"] == "default"


@pytest.mark.parametrize("client", [FakeClient(boom=True), FakeClient(scans=[NONE], stop_reason="refusal"), FakeClient()])
def test_failed_scan_fails_the_gate(repo, client):
    cm = m.CodeMender(repo, author="sam", client=client)
    cm.scan()
    assert cm.scan_status == "failed" and cm.gate()[0] == "failure"


def test_clean_scan_passes_only_for_the_scanned_commit(repo):
    cm = m.CodeMender(repo, author="sam", client=FakeClient(scans=[NONE]))
    cm.scan()
    assert cm.gate()[0] == "success"
    _commit(repo, "app.py", VULN + "\n# more code\n")
    assert cm.gate() == ("failure", "this commit has not been scanned")


def test_findings_in_files_outside_the_pr_are_dropped(repo):
    other = {**_finding("CWE-89", "elsewhere"), "path": "not_in_this_pr.py"}
    cm = m.CodeMender(repo, author="sam", client=FakeClient(scans=[{"findings": [other]}]))
    cm.scan()
    assert cm.findings == []


def test_findings_track_across_commits_as_lines_shift(repo):
    moved = {"findings": [_finding("CWE-89", "search", line=99)]}
    cm = m.CodeMender(repo, author="sam", client=FakeClient(scans=[{"findings": [_finding("CWE-89", "search")]}, moved]))
    cm.scan()
    _commit(repo, "app.py", "# shifted\n" + VULN)
    cm.on_push()
    assert len(cm.findings) == 1 and cm.findings[0].line == 99


# ---------- commands ----------

def test_read_permission_cannot_run_commands(repo):
    c = FakeClient(scans=[ALL_FOUR])
    cm = m.CodeMender(repo, author="sam", client=c)
    cm.scan()
    calls = len(c.seen)
    assert cm.on_comment("c1", "drive-by", "read", "/verify all").startswith("refused")
    assert len(c.seen) == calls and all(f.status == "open" for f in cm.findings)


def test_redelivered_comment_runs_once(repo):
    cm, c = _verified(repo)
    calls = len(c.seen)
    assert cm.on_comment("c1", "riley", "write", "/verify all") == "ignored" and len(c.seen) == calls


def test_verify_confirms_from_the_check_not_the_model(repo):
    cm, _ = _verified(repo)
    assert [f.status for f in cm.findings] == ["confirmed"] * 4


def test_input_that_does_not_get_through_stays_blocking(repo):
    c = FakeClient(scans=[{"findings": [_finding("CWE-89", "search")]}], probes=[{"probes": [_probe("/search", q="Widget")]}])
    cm = m.CodeMender(repo, author="sam", client=c)
    cm.scan()
    cm.on_comment("c1", "riley", "write", "/verify all")
    assert cm.findings[0].status == "not_reproduced" and cm.gate()[0] == "failure"
    assert cm.on_comment("c2", "riley", "write", "/fix all").startswith("nothing to fix")


def test_cwe_with_no_check_is_unverifiable_and_blocks(repo):
    c = FakeClient(scans=[{"findings": [_finding("CWE-502", "search")]}])
    cm = m.CodeMender(repo, author="sam", client=c)
    cm.scan()
    cm.on_comment("c1", "riley", "write", "/verify all")
    assert cm.findings[0].status == "unverifiable" and cm.gate()[0] == "failure" and len(c.seen) == 1


def test_model_failure_during_verify_stays_blocking(repo):
    c = FakeClient(scans=[{"findings": [_finding("CWE-89", "search")]}])  # no probes queued: malformed reply
    cm = m.CodeMender(repo, author="sam", client=c)
    cm.scan()
    cm.on_comment("c1", "riley", "write", "/verify all")
    assert cm.findings[0].status == "not_reproduced" and "could not run" in cm.findings[0].note
    assert cm.gate()[0] == "failure"


# ---------- fix: nothing reaches a person until it proves itself ----------

def test_good_patch_is_staged_not_committed(repo):
    cm, _ = _verified(repo, fixes=[_fix()])
    before = cm.head()
    reply = cm.on_comment("c2", "riley", "write", "/fix all")
    assert cm.staged and cm.staged.id in reply and cm.head() == before
    assert cm.staged.id in cm.comment_body and "```diff" in cm.comment_body and cm.gate()[0] == "failure"


@pytest.mark.parametrize("bad,expected", [
    (VULN + "\n# no real change\n", "exploit still works"),
    (FIXED.replace('@app.get("/hello")', '@app.get("/removed")'), "regression"),
    ("def broken(:\n", "regression"),
])
def test_bad_patches_never_reach_a_person(repo, bad, expected):
    cm, c = _verified(repo, fixes=[_fix(bad), _fix(bad)])
    reply = cm.on_comment("c2", "riley", "write", "/fix all")
    assert cm.staged is None and reply.startswith("no patch staged") and expected in reply
    assert "rejected" in c.seen[-1]["messages"][0]["content"]  # the second try was told why


def test_rejected_patch_gets_a_second_try(repo):
    cm, _ = _verified(repo, fixes=[_fix(VULN + "\n# nope\n"), _fix()])
    assert "2 attempt(s)" in cm.on_comment("c2", "riley", "write", "/fix all") and cm.staged


@pytest.mark.parametrize("path", ["ci_checks.json", ".github/workflows/ci.yml", "other.py"])
def test_patch_may_not_touch_other_files(repo, path):
    cm, _ = _verified(repo, fixes=[_fix(path=path), _fix(path=path)])
    reply = cm.on_comment("c2", "riley", "write", "/fix all")
    assert cm.staged is None and "may not be changed" in reply


def test_pr_cannot_weaken_the_regression_checks(repo):
    _commit(repo, m.CHECKS_FILE, "[]\n")
    cm, _ = _verified(repo, fixes=[_fix(FIXED.replace('@app.get("/hello")', '@app.get("/removed")'))] * 2)
    assert "regression" in cm.on_comment("c2", "riley", "write", "/fix all")


# ---------- approve: a person, this patch, this commit ----------

def _staged(repo, scans=(NONE,), fixes=None):
    cm, c = _verified(repo, fixes=fixes or [_fix()], scans=scans)
    cm.on_comment("c2", "riley", "write", "/fix all")
    return cm, c


def test_approve_commits_and_gate_goes_green_only_after_retesting(repo):
    cm, _ = _staged(repo)
    pid, before = cm.staged.id, cm.head()
    reply = cm.on_comment("c3", "riley", "write", f"/approve {pid}")
    assert reply == f"committed patch {pid}; gate: success" and cm.head() != before
    assert [f.status for f in cm.findings] == ["fixed"] * 4 and cm.staged is None
    assert (repo / "app.py").read_text(encoding="utf-8").replace("\r\n", "\n") == FIXED
    assert "approved by riley" in subprocess.run(["git", "log", "-1", "--format=%s"], cwd=repo, capture_output=True,
                                                 text=True).stdout


def test_pr_author_cannot_approve_their_own_patch(repo):
    cm, _ = _staged(repo)
    before = cm.head()
    assert "wrote this PR" in cm.on_comment("c3", "sam", "write", f"/approve {cm.staged.id}") and cm.head() == before


def test_approval_must_name_the_staged_patch(repo):
    cm, _ = _staged(repo)
    assert "not the staged patch" in cm.on_comment("c3", "riley", "write", "/approve deadbeef")
    assert "unknown command" in cm.on_comment("c4", "riley", "write", "/approve")


def test_approval_is_void_after_the_branch_moves(repo):
    cm, _ = _staged(repo)
    pid = cm.staged.id
    _commit(repo, "NOTES.md", "docs\n")
    assert "branch moved" in cm.on_comment("c3", "riley", "write", f"/approve {pid}")


def test_push_voids_the_staged_patch_and_docs_only_push_skips_the_scan(repo):
    cm, c = _staged(repo)
    pid, calls = cm.staged.id, len(c.seen)
    _commit(repo, "NOTES.md", "docs\n")
    cm.on_push()
    assert cm.staged is None and len(c.seen) == calls and cm.scanned_sha == cm.head()
    assert "no patch is staged" in cm.on_comment("c3", "riley", "write", f"/approve {pid}")


def test_code_push_needs_a_new_scan(repo):
    cm, c = _staged(repo)
    calls = len(c.seen)
    _commit(repo, "app.py", VULN + "\n# more\n")
    c.q["findings"].append(ALL_FOUR)
    cm.on_push()
    assert len(c.seen) == calls + 1 and cm.scanned_sha == cm.head()


def test_push_that_undoes_a_fix_reopens_it_even_if_the_scanner_misses_it(repo):
    cm, c = _staged(repo)
    cm.on_comment("c3", "riley", "write", f"/approve {cm.staged.id}")
    assert cm.gate()[0] == "success"
    _commit(repo, "app.py", VULN)
    c.q["findings"].append(NONE)  # the scanner sees nothing this time
    cm.on_push()
    assert cm.findings[0].status == "confirmed" and cm.gate()[0] == "failure"


def test_failed_rescan_after_commit_keeps_the_gate_red(repo):
    cm, c = _staged(repo)
    c.boom = True
    cm.on_comment("c3", "riley", "write", f"/approve {cm.staged.id}")
    assert all(f.status == "fixed" for f in cm.findings) and cm.gate()[0] == "failure"


# ---------- dismiss and audit ----------

def test_dismiss_needs_a_category_and_can_clear_a_finding(repo):
    c = FakeClient(scans=[{"findings": [_finding("CWE-502", "search")]}])
    cm = m.CodeMender(repo, author="sam", client=c)
    cm.scan()
    assert cm.on_comment("c1", "riley", "write", "/dismiss F1 because reasons").startswith("refused")
    assert cm.on_comment("c2", "riley", "write", "/dismiss F1 false_positive not reachable") == "dismissed F1"
    assert cm.gate()[0] == "success"


def test_dismissal_cannot_turn_a_failed_scan_green(repo):
    cm = m.CodeMender(repo, author="sam", client=FakeClient(scans=[{"findings": [_finding("CWE-502", "search")]}]))
    cm.scan()
    cm.on_comment("c1", "riley", "write", "/dismiss F1 false_positive nope")
    cm._client.boom = True
    cm.scan()
    assert cm.gate()[0] == "failure"


def test_audit_is_append_only_and_names_who_approved(repo):
    cm, _ = _staged(repo)
    cm.on_comment("c3", "sam", "write", f"/approve {cm.staged.id}")
    pid = cm.staged.id
    cm.on_comment("c4", "riley", "write", f"/approve {pid}")
    rows = cm.audit_rows()
    assert ("approve_refused", "sam") in [r[:2] for r in rows]
    assert ("patch_committed", "riley", None, None, pid) in rows
    for sql in ("UPDATE events SET actor='x'", "DELETE FROM events"):
        with pytest.raises(Exception, match="append-only"):
            cm.audit_db.execute(sql)


def test_sample_is_never_served():
    assert "app.run" not in VULN and "app.run" not in BASE
    assert shutil.which("git")
    assert os.path.exists(DAY / "pr_runner.py")
