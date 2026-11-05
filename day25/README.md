# Day 25 locally: CodeMender (fix vulnerable code before it merges)

Scanner dashboards report flaws after the merge, when fixing them is someone else's chore. CodeMender works inside the pull request: it finds flaws, proves them with an exploit, stages a patch, and commits only when a person approves. The course's version is allowlisted and needs GCP plus a GitHub token, so this rebuilds the loop locally against a throwaway git repo. All data is fake.

| Course (Gemini platform) | Here |
|---|---|
| Scans the cumulative PR diff | `scan()`: `git diff base...head`, Claude, structured findings |
| Sticky PR comment | `comment_body`, replaced in place, marked with the same HTML comment |
| Gate `security/codemender-gate` fails on Critical findings | `gate()`, which also fails on a failed scan or an unscanned commit |
| `/verify all`: generated `exploit.sh` in a sandboxed container | Claude proposes HTTP inputs only; `pr_sandbox.py` runs them and decides |
| `/fix all`: staged patch, exploit re-run | same inputs must fail on a patched copy, and the base branch's checks must pass; one retry with the reasons |
| `/approve` commits; the agent never does | `_approve()` |
| `/dismiss` needs a governance category; can't turn a failed scan green | same |
| Commands need write/admin; redelivered comments run once | same |
| Subprocesses get an allowlisted environment with no secrets | same (`run_probes`) |
| BigQuery audit | append-only SQLite `events` |
| *(my additions)* | approval names the patch id and is void if the branch moved; the PR author can't approve; patches can't touch `ci_checks.json` or `.github/`; regression checks come from the base branch; a push re-tests earlier fixes |

Model calls use `claude-opus-5-5` with server-side `fallbacks: "default"`, so a safety decline retries on another model before the fail-closed path applies.

## Why nothing here can do real damage
- `sample/pr_app.py` has four planted flaws and is never served: requests go through Flask's in-process test client.
- `shell()` is a stub that records its argument. No command runs, including `127.0.0.1; id`.
- Claude produces data (HTTP inputs, file contents), never code the harness runs as a script. Its patch does run, in a child process, but only after it's written to a temp copy.

**That child process is not a real sandbox.** It has no secrets in its environment and a timeout, but it can still reach the disk and network. Fine for this fixture; never run a stranger's PR this way. That needs a container with no network, and results the PR's code can't forge.

## Run (repo root)
```bash
uv run pytest day25 -q
```
```bash
uv run python day25/demo.py
```
The tests take a few minutes on Windows, because each exploit run starts a Python process and imports Flask.

## What my run showed (2026-11-04)
- **Scan:** all four flaws found, even with a code comment telling scanners the security team had reviewed the file and to report nothing.
- **Severity:** SQL injection, command injection and IDOR came back Critical; reflected XSS came back **Medium**, so it would not have blocked the merge by itself even once proven.
- **Verify:** 4 of 4 confirmed by the checks, not by Claude's word: the response contained a random secret Claude never saw, or the stub shell received a second command.
- **Fix:** patch staged on the first attempt, with parameterized SQL, an argument list instead of a shell string, escaping, and an ownership check.
- **Refusals:** a read-only user, the PR's author, and a patch made stale by a docs push were all refused. The redelivered comment was ignored.
- **Green:** only after riley approved, the commit landed, the exploits failed on the new commit, and the rescan came back clean.
- **Cost:** 8 model calls, including the second `/fix all` after the stale patch.
- **A bug the tests caught:** on Windows, text-mode stdin turned the patch's line endings into CRLF and `git apply` rejected it. It now sends bytes.

## Limits
- **Green means "nothing known is open", not "safe".** A flaw the scanner misses never reaches the verify step.
- **"Fixed" means the inputs that proved it no longer work.** A narrow patch could stop those and miss a variant. The repo's checks protect features, not security, so a person still has to read the diff.
- **The checks only cover what they cover.** Other CWEs become `unverifiable` and stay blocking until someone dismisses them with a reason.
- **`not_reproduced` isn't cleared.** Claude may simply have picked poor inputs, so a Critical one still blocks.
- **The model's severity rating drives the gate,** as the XSS result shows. Decide whether proven findings should block regardless of rating.
- **Only the slash-command logic is here.** There is no real webhook, GitHub token or workload identity federation; `/approve` by bare command in the course is `/approve <patch id>` here.
