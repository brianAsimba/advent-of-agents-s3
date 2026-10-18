# Day 14 — Skill Scanning: Block Poisoned Skills Before Agents Use Them
[Page](https://adventofagents.com/2026/10/14) · [Video (8 min)](https://www.youtube.com/watch?v=9A-CzJNxZp0) · [Companion: Owain Lewis, spec-driven development (33 min)](https://www.youtube.com/watch?v=RhaF4LVAVng) · [Local kata repo](https://g.dev/cloud/adventofagents-season3-day14-demo) · [CI/CD + Agent Registry repo](https://g.dev/cloud/adventofagents-season3-day14-cicd-demo) · [NVIDIA SkillSpector](https://github.com/nvidia/skillspector)

## Core idea
A community skill or MCP server can hide an instruction in its `SKILL.md`, or ship a script that does something it shouldn't. **Skills are a new kind of supply-chain risk** because they combine scripts with natural-language instructions that steer the model directly. Classic scanners (`pip-audit`, `npm audit`) look for known vulnerabilities in published packages and miss both.

**Day 13 contains untrusted code at runtime; Day 14 stops bad skills before an agent ever loads them.**

## The course's gate (in CI/CD)
1. **NVIDIA SkillSpector:** static analysis of scripts (Python AST, taint tracking, YARA rules) plus an LLM semantic pass over `SKILL.md`.
2. **Capability lockfile (`sat.lock`):** an explicit allowlist of domains the skill may contact.
3. **Agent Software Bill of Materials (`asbom.json`):** SHA-256 of every file, so any later tampering is visible.
4. **Publish only skills with zero HIGH/CRITICAL findings** to Agent Registry; agents discover only vetted tools.

## What I built and found
`day14/skill_guard.py` on my real `~/.claude/skills` (13 skills, 217 files): `lock` (hash every file), `verify` (detect any change since), `review` (read-only static report). Result: 9 OK, 1 INFO (skill-creator: subprocess + env for its eval scripts), 3 REVIEW. All three REVIEW flags trace to one shared file, `soffice.py`, which uses a **local** Unix socket and passes the environment to LibreOffice: **benign once read**. Lesson: static scanners produce false positives (my first pass also flagged `re.compile` and `urllib.parse`), so a human or LLM pass is needed, and "approved" should be tied to the file hash, so any change triggers re-review.

## Connections
- **My own setup:** I install skills and track marketplaces (skills.sh, SkillsMP). A third-party skill runs with Claude Code's access to my machine. `verify` after every install or sync.
- **Barber pilot / SMB clients:** any n8n community node or MCP server I use for a client should pass the same gate.
- **GM:** a skill/tool allowlist with hash pinning is a concrete governance-forum control (Day 4's Foundation inventory plus Prevention).

## Check yourself
- Why can't `pip-audit` catch a poisoned SKILL.md?
- What does a hash manifest (ASBOM) let you detect that a one-time scan doesn't?
- Why do static scanners need a second (human or LLM) pass?
