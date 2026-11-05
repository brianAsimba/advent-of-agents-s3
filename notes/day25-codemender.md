# Day 25 — CodeMender: Fix Vulnerable Code Before It Merges
[Page](https://adventofagents.com/2026/10/25) · [Video (13 min)](https://www.youtube.com/embed/LerewxBM0rM) · [Starter kit](https://github.com/GCP-Architecture-Guides/codemender-gitops-starter-kit) · [PoC guide](https://github.com/GCP-Architecture-Guides/codemender-gitops-starter-kit/blob/main/POC_GUIDE.md) · [Introducing CodeMender](https://deepmind.google/blog/introducing-codemender-an-ai-agent-for-code-security/) · [WIF for CI/CD](https://g.dev/cloud/adventofagents-season3-docs-wif-deployment-pipelines)

## Core idea
Agent tools are ordinary code that a model calls with model-chosen arguments, so one flaw can turn a prompt injection into a breach. Scanner dashboards report such flaws after the merge. CodeMender stays in the PR and closes the loop: **find → prove → patch → prove the patch → a human approves.**

## How it works (course)
- **Trigger:** a GitHub Actions workflow on PR events and on comments starting with `/verify`, `/fix`, `/approve` or `/dismiss`. It gets an OIDC token, authenticates through Workload Identity Federation (no stored key), and posts the event to a Cloud Run backend. The backend re-reads the event from the GitHub API before acting.
- **Sticky comment:** one comment edited in place, listing each finding's CWE, file, line and severity.
- **Gate:** `security/codemender-gate` fails on open Critical findings. It only blocks a merge if branch protection requires it.
- **`/verify all`:** a generated exploit runs in a sandbox. **`/fix all`:** stages a diff and re-runs the exploit. **`/approve`:** commits. Only a person's approval causes a commit.
- **Governance:** commands need write/admin; redelivered comments run once; subprocesses get an allowlisted environment with no secrets; dismissals need a category and can't turn a failed scan green.

## What I built (2026-11-04, Claude + a throwaway git repo)
A four-flaw Flask fixture (SQL injection, command injection, XSS, IDOR) run through an in-process test client with a stub shell, so nothing executes and nothing listens on a port.
- All four found, despite a code comment telling scanners to report nothing.
- All four proven by checks Claude can't fake: a random secret Claude never saw appears in the response, or the stub shell receives a second command.
- Patch staged on the first try, committed only after a different person approved it; the gate went green once the exploits failed on the new commit and the rescan was clean.
- A read-only user, the PR's author, a stale patch and a redelivered comment were all refused or ignored.
- XSS was proven but rated **Medium**, so it would not have blocked on its own.
- 8 model calls.

## Lessons
- **Separate the proposer from the judge.** The model proposes inputs and patches; a deterministic check decides. "The exploit worked" is an observation, not a claim.
- **Prove the patch the same way you proved the flaw.** Same inputs, now failing, plus the repo's own checks still passing. Failures go back to the model before any person sees them.
- **Approval binds to a specific thing.** A bare "approve" can land on code that changed after review. This approval names the patch id and dies if the branch moves (same idea as Day 16's signed mandates).
- **Fail closed at every step.** Failed scan, unscanned commit, unproven finding, unverifiable CWE, fix that couldn't be re-tested: all keep the gate red.
- **Everything in a PR is attacker-controlled:** code comments, strings, and the code's own output. A PR's code runs in the harness too, so it must never see secrets, and its checks must come from the base branch.
- **Green means "nothing known is open", not "safe".** The scanner can miss things, and a patch can stop one exploit and miss its variant. A person still reads the diff.
- **Severity is a policy input.** A model's rating decided that a proven XSS wouldn't block (same lesson as Day 24's alert threshold).

## Connections
- **Days 3, 8, 12, 15:** those harden tools at design time; this catches flaws at PR time, and Day 24 catches what gets through at runtime.
- **Day 17:** the CI pipeline where a gate like this would run; the repo's CI could require it.
- **Trading agent / SMB clients:** run this over tool code before it ships; "every flaw proven, every patch approved by a person" is a clear thing to tell a client.
- **Career:** scan → prove → patch → approve applies to any regulated codebase, without using any employer's code.

## Check yourself
The course page has no questions, so these are mine.
- Why does the model not get to say whether the exploit worked?
- Why are the regression checks read from the base branch instead of the PR?
- What attack does binding `/approve` to a patch id and commit prevent?
- Why does `not_reproduced` still block?
- What can a green gate still be hiding?
