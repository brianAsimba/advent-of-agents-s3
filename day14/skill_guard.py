"""Day 14: integrity lockfile + read-only review for installed agent skills.

Course concept                                   Here
-----------------------------------------------  -----------------------------------------------------
Agent Software Bill of Materials (asbom.json)    `lock`  : SHA-256 of every file in every skill -> skills.lock.json
  pins a hash for every file                      `verify`: reports files added, removed or changed since the lock
Static scan of scripts + LLM pass on SKILL.md    `review`: read-only static report (no model, nothing executed)
Capability lockfile: domain allowlist            `review` lists every web domain each skill mentions

Nothing here runs, edits or deletes a skill. Usage (repo root):
  uv run python day14/skill_guard.py lock      [--root PATH]
  uv run python day14/skill_guard.py verify    [--root PATH]
  uv run python day14/skill_guard.py review    [--root PATH]
Default root: ~/.claude/skills
"""
import argparse
import ast
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCK = HERE / "skills.lock.json"
REPORT = HERE / "skill_review.md"
DEFAULT_ROOT = Path.home() / ".claude" / "skills"

TEXT_EXT = {".md", ".txt", ".py", ".sh", ".js", ".ts", ".ps1", ".json", ".yaml", ".yml", ".toml", ".html", ".xml"}
SCRIPT_EXT = {".py", ".sh", ".js", ".ts", ".ps1"}
NET_MODULES = {"requests", "urllib", "urllib3", "http", "httpx", "aiohttp", "socket", "ftplib", "smtplib"}
EXEC_CALLS = {"eval", "exec", "compile", "__import__"}
SHELL_NET = re.compile(r"\b(curl|wget|Invoke-WebRequest|Invoke-RestMethod|fetch\()", re.I)
SHELL_ENV = re.compile(r"(\$env:|\$\{?[A-Z_]{3,}\}?|process\.env|os\.environ|getenv)")
URL = re.compile(r"https?://([A-Za-z0-9.-]+)")
HIDDEN = re.compile("[​‌‍⁠﻿‪-‮]")
HTML_COMMENT = re.compile(r"<!--(.*?)-->", re.S)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def skills(root: Path) -> list[Path]:
    """Every folder that contains a SKILL.md (skills can be nested, e.g. under a synced folder)."""
    return sorted({p.parent for p in root.rglob("SKILL.md")})


def files_of(root: Path) -> dict[str, dict]:
    return {str(p.relative_to(root)).replace("\\", "/"): {"sha256": sha256(p), "size": p.stat().st_size}
            for p in sorted(root.rglob("*")) if p.is_file()}


# ---------- lock / verify ----------

def lock(root: Path) -> dict:
    data = {"root": str(root), "files": files_of(root)}
    LOCK.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def verify(root: Path) -> dict:
    if not LOCK.exists():
        raise SystemExit("No skills.lock.json yet. Run `lock` first.")
    old = json.loads(LOCK.read_text(encoding="utf-8"))["files"]
    new = files_of(root)
    return {"added": sorted(set(new) - set(old)),
            "removed": sorted(set(old) - set(new)),
            "changed": sorted(k for k in set(old) & set(new) if old[k]["sha256"] != new[k]["sha256"])}


# ---------- review (static, read-only) ----------

def _python_findings(src: str) -> list[str]:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return ["could not parse Python (review by hand)"]
    imports, calls, env = set(), set(), False
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):  # urllib.parse only parses text; it does not touch the network
            imports |= {a.name.split(".")[0] for a in n.names if a.name != "urllib.parse"}
        elif isinstance(n, ast.ImportFrom) and n.module and n.module != "urllib.parse":
            imports.add(n.module.split(".")[0])
        elif isinstance(n, ast.Call):
            f = n.func
            name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
            if isinstance(f, ast.Name) and name in EXEC_CALLS:  # bare eval()/exec(), not re.compile()
                calls.add(name)
            if name in ("getenv",) or (isinstance(f, ast.Attribute) and f.attr in ("system", "popen")):
                calls.add(name)
        elif isinstance(n, ast.Attribute) and n.attr == "environ":
            env = True
    out = []
    net = sorted(imports & NET_MODULES)
    if net:
        out.append("network modules: " + ", ".join(net))
    if "subprocess" in imports:
        out.append("runs other programs (subprocess)")
    if calls & EXEC_CALLS:
        out.append("dynamic code execution: " + ", ".join(sorted(calls & EXEC_CALLS)))
    if env or "getenv" in calls:
        out.append("reads environment variables")
    return out


def review(root: Path) -> list[dict]:
    rows = []
    for sk in skills(root):
        files = [p for p in sk.rglob("*") if p.is_file()]
        domains, notes, level = set(), [], "OK"
        for p in files:
            if p.suffix.lower() not in TEXT_EXT:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            domains |= {d.lower() for d in URL.findall(text)}
            rel = str(p.relative_to(sk)).replace("\\", "/")
            if HIDDEN.search(text):
                notes.append(f"{rel}: hidden/invisible characters"); level = "REVIEW"
            if p.name == "SKILL.md":
                hidden_comments = [c for c in HTML_COMMENT.findall(text) if len(c.strip()) > 40]
                if hidden_comments:
                    notes.append(f"{rel}: {len(hidden_comments)} long HTML comment(s), invisible when rendered"); level = "REVIEW"
            if p.suffix.lower() == ".py":
                f = _python_findings(text)
                if f:
                    notes.append(f"{rel}: " + "; ".join(f))
                    if any("network" in x for x in f) and any("environment" in x for x in f):
                        level = "REVIEW"  # network + environment access in one script deserves a human look
                    elif any("dynamic code" in x for x in f):
                        level = "REVIEW"
                    elif level == "OK":
                        level = "INFO"
            elif p.suffix.lower() in SCRIPT_EXT:
                net, env = bool(SHELL_NET.search(text)), bool(SHELL_ENV.search(text))
                if net or env:
                    notes.append(f"{rel}: " + ", ".join(x for x, y in (("network command", net), ("environment access", env)) if y))
                    level = "REVIEW" if (net and env) else (level if level != "OK" else "INFO")
        rows.append({"skill": str(sk.relative_to(root)).replace("\\", "/") or sk.name, "files": len(files),
                     "scripts": sum(p.suffix.lower() in SCRIPT_EXT for p in files),
                     "domains": sorted(domains), "level": level, "notes": notes})
    return rows


def write_report(rows: list[dict], root: Path) -> None:
    lines = [f"# Skill review: {root}", "",
             "Read-only static review. **REVIEW** = worth a human look (e.g. network + environment access in one "
             "script, dynamic code execution, hidden text). **INFO** = has scripts with notable capabilities. "
             "Nothing was executed or changed.", "",
             "| Skill | Level | Files | Scripts | Domains mentioned |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['skill']} | {r['level']} | {r['files']} | {r['scripts']} | {', '.join(r['domains'][:6])}{' …' if len(r['domains']) > 6 else ''} |")
    for r in rows:
        if r["notes"]:
            lines += ["", f"## {r['skill']} ({r['level']})"] + [f"- {n}" for n in r["notes"]]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["lock", "verify", "review"])
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    a = ap.parse_args(argv)
    root = Path(a.root).expanduser().resolve()
    if a.cmd == "lock":
        d = lock(root)
        print(f"Locked {len(d['files'])} files under {root} -> {LOCK.name}")
    elif a.cmd == "verify":
        d = verify(root)
        print("No changes since the lock." if not any(d.values()) else json.dumps(d, indent=2))
        return 1 if any(d.values()) else 0
    else:
        rows = review(root)
        write_report(rows, root)
        counts = {lvl: sum(r["level"] == lvl for r in rows) for lvl in ("OK", "INFO", "REVIEW")}
        print(f"Reviewed {len(rows)} skills: {counts}. Report: {REPORT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
