# Day 14 on Claude: guard your installed skills (integrity lockfile + read-only review)

A skill mixes **natural-language instructions that steer the model** (`SKILL.md`) with scripts. Dependency scanners (`pip-audit`, `npm audit`) only catch *known* CVEs, so they're blind to a freshly written hidden instruction or a script that reads secrets. The course gates skills in CI with NVIDIA **SkillSpector**, a domain lockfile (`sat.lock`) and a hash manifest (`asbom.json`), and publishes only clean skills to Agent Registry.

This folder applies the two defensive halves to **my real installed skills** (`~/.claude/skills`). Everything is read-only: nothing is executed, edited or deleted.

| Course | Here |
|---|---|
| `asbom.json`: SHA-256 of every file | `lock` writes `skills.lock.json`; `verify` reports any added, removed or changed file |
| Static scan (AST) of scripts | `review`: Python AST + shell patterns, flagging network use, environment reads, subprocess, `eval`/`exec`, hidden characters, long HTML comments in SKILL.md |
| `sat.lock` domain allowlist | `review` lists every domain each skill mentions |
| LLM semantic pass, CI gate | Not here; that's SkillSpector in the course repo (run it yourself, see below) |

## Run (repo root)
```bash
uv run python day14/skill_guard.py lock
```
```bash
uv run python day14/skill_guard.py verify
```
```bash
uv run python day14/skill_guard.py review
```
`skills.lock.json` and `skill_review.md` stay local (gitignored): they're an inventory of my machine.

## How to read the review
**REVIEW** means "worth a human look", not "malicious". On my machine, all three REVIEW flags (docx, pptx, xlsx) come from one shared helper, `scripts/office/soffice.py`, which opens a *local* Unix socket for LibreOffice and passes a copy of the environment to it. That's benign once read. Static scanners trade false positives for coverage: the first version also flagged every `re.compile(...)` as "dynamic code" and `urllib.parse` as "network", both fixed.

**Habit:** run `verify` after installing or syncing skills. Any changed file means re-review that skill before using it.
