"""Day 14 tests on small synthetic skill folders (no network, nothing executed)."""
import pytest

import skill_guard as sg


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(sg, "LOCK", tmp_path / "skills.lock.json")
    monkeypatch.setattr(sg, "REPORT", tmp_path / "skill_review.md")
    r = tmp_path / "skills"
    (r / "notes").mkdir(parents=True)
    (r / "notes" / "SKILL.md").write_text("---\nname: notes\n---\nSummarize the user's notes. See https://docs.python.org/3/\n")
    (r / "uploader").mkdir()
    (r / "uploader" / "SKILL.md").write_text("---\nname: uploader\n---\nUploads a report.\n")
    (r / "uploader" / "run.py").write_text("import os, requests\nTOKEN = os.environ.get('X')\nrequests.get('https://api.example.com')\n")
    return r


def test_lock_then_verify_detects_changes(root):
    sg.lock(root)
    assert sg.verify(root) == {"added": [], "removed": [], "changed": []}
    (root / "notes" / "SKILL.md").write_text("changed")
    (root / "notes" / "extra.py").write_text("print(1)")
    d = sg.verify(root)
    assert d["changed"] == ["notes/SKILL.md"] and d["added"] == ["notes/extra.py"]


def test_review_flags_network_plus_environment(root):
    rows = {r["skill"]: r for r in sg.review(root)}
    assert rows["uploader"]["level"] == "REVIEW" and "api.example.com" in rows["uploader"]["domains"]
    assert rows["notes"]["level"] == "OK" and rows["notes"]["domains"] == ["docs.python.org"]


def test_review_flags_hidden_text(root):
    (root / "notes" / "SKILL.md").write_text("Summarize notes.​\n<!-- " + "x" * 60 + " -->\n", encoding="utf-8")
    row = {r["skill"]: r for r in sg.review(root)}["notes"]
    assert row["level"] == "REVIEW" and len(row["notes"]) == 2


def test_review_never_modifies_files(root):
    before = sg.files_of(root)
    sg.write_report(sg.review(root), root)
    assert sg.files_of(root) == before


def test_re_compile_is_not_dynamic_code():
    assert sg._python_findings("import re\nP = re.compile(r'a+')\n") == []
    assert "dynamic code execution: eval" in sg._python_findings("eval('1+1')\n")

