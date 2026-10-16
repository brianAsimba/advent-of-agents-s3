# Day 9 — Principal Access Boundaries: Contain Blast Radius
[Page](https://adventofagents.com/2026/10/09) · [Video (4 min)](https://www.youtube.com/watch?v=YDbt7oMdpyc) · [PAB overview](https://g.dev/cloud/adventofagents-season3-pab) · [Manage PAB policies](https://g.dev/cloud/adventofagents-season3-manage-pab-policies) · [Demo repo](https://g.dev/cloud/adventofagents-season3-pab-demo-repo)

## Core idea
Enterprises organize projects in **folders**, and IAM grants on a folder are **inherited** by every project below it. An agent granted read at the folder level can therefore read sibling teams' projects. If a prompt injection or an unexpected tool call points it at another team's bucket, IAM says yes, and you have cross-project exfiltration.

A **Principal Access Boundary (PAB)** puts a perimeter around the **identity** instead of the resource: the strict allowlist of projects an agent may *ever* reach. **Both** must allow a request:

| Check | Answers | Attached to |
|---|---|---|
| IAM allow policy | What actions can this principal perform? | Resources (inherited down folders) |
| Principal Access Boundary | Which resources may this principal ever touch? | Principals (here: all agent identities in a project) |

Anything outside the boundary fails at the control plane with `403 Forbidden: Principal Access Boundary violation`, before any data is touched.

## Steps on Google Cloud
1. Create an org-level PAB policy whose ALLOW rule lists only Project 1.
2. Bind it to Project 1's agent identities (principal set `//agents.global.org-ORG/attribute.container/projects/NUMBER`).
3. Test: the agent reads its own bucket (OK) and another project's bucket (403 PAB violation).

## How it differs from earlier days
- **Day 5 (IAM):** grants decide *what* is allowed, but grants accumulate and are inherited.
- **Day 8 (gateway):** decides which *tools* may be called.
- **Day 9 (PAB):** caps the identity's *reach*, regardless of grants made today or tomorrow. A boundary grants nothing on its own; it only fences.

## Running it without Google Cloud
`day09/`: folder `manufacturing` with projects `stamping` (agent's home) and `hr-payroll`. A folder-level grant lets the Claude storage inspector read HR payroll "for the quarterly audit"; a PAB bound to stamping's agents blocks it, even after a mistaken direct grant on HR.

## Connections
- **GM:** this is the exact shape of a plant/function folder hierarchy. A stamping AI agent should be boundaried to stamping projects even if a broad "manufacturing" grant exists.
- **Trading agent:** fence it to the trading account and data folder; it should never reach personal or work files even if a broad grant creeps in.
- **Day 4:** strengthens Prevention, and limits Response's blast radius.

## Check yourself
- Why does a folder-level grant create a blast-radius problem for agents?
- Why does a PAB still help after someone makes a mistaken direct grant?
- Why does a PAB alone not let the agent read anything?
