# Day 4 — Governance Maturity Model: Progressive Trust for Agents
[Page](https://adventofagents.com/2026/10/04) · [Video (7 min)](https://www.youtube.com/watch?v=nNjqaKVR3tc) · [Govern your agents](https://g.dev/cloud/adventofagents-season3-gemini-enterprise-govern)

## Core idea
Most organizations can't say how many agents they run, who owns each one, what they can reach, or what happens when one misbehaves. Before adding controls, **score where you are**. Five layers, each answering one question and building on the one below:

| # | Layer | Question | Level-3 bar (Google stack) |
|---|---|---|---|
| 1 | Foundation | Is every agent cataloged, owned, identifiable? | Agent Registry + named owner + own SPIFFE identity + IaC deploys |
| 2 | Prevention | Can you block violations inline? | Every tool call through Agent Gateway; Model Armor fails closed; egress denied by default |
| 3 | Detection | Can you spot anomalies, with an immutable audit trail? | OpenTelemetry traces + audit logs in a queryable sink |
| 4 | Response | Can you prove containment worked? | Tested playbook revokes one agent's credentials in < 1 minute |
| 5 | Continuous Alignment | Do escapes become better policy? | Postmortems → policy updates, gated by regression evals |

## Scoring rules
1. Rate 15 areas (3 per layer) at **1** (ad hoc), **3** (standardized in production) or **5** (automated everywhere).
2. **A layer scores its weakest area.** One weak link defines the layer.
3. **Start at the lowest layer below 3.** The order is structural: a gateway enforces against identities that must already exist; detection needs governed traffic to watch.
4. Phase it: Foundation days 1–30 → Prevention + Detection 31–60 → Response + Alignment 61–90.

## My score (`day04/assess.py day04/my_estate.json`)
All five layers score **1**. Only `circuit_breakers` reaches 3 (trading agent's 5-slot cap, whole shares, trailing stops; Day 3's `enforce_limits`). Start: **Foundation**.

## Personal / small-business translation of the Level-3 bar
| Area | Google enterprise version | My-scale equivalent |
|---|---|---|
| Identity | SPIFFE identity per agent | A separate API key per agent, so one can be revoked alone |
| Inventory | Agent Registry | An `agents.yaml` listing each agent, owner, tools, keys, data touched |
| Infrastructure | Terraform / IaC | One scripted launch/deploy per agent; no hand-run steps |
| Prompt shielding | Model Armor at gateway, fail closed | Screening on all untrusted input (user and retrieved text), and block on screening errors |
| Data leaks | Managed PII masking | Output redaction, like Day 2's OUT checkpoint |
| Circuit breakers | Gateway rate/iteration limits | Max turns per run, Anthropic console spend limit, position limits |
| Tracing | OpenTelemetry → Cloud Trace | Save every run's trace to a file or a free tracing tool |
| Anomalies | Token/trajectory alerts | Alert if a run's token count or tool-call count is far above normal |
| Audit | Immutable logs → BigQuery | Append-only log that the agent itself can't edit |
| Containment | Revoke one agent's identity | Per-agent keys + a one-page "how to kill it" note (the barber pilot already plans this) |
| Threat alerts | Security Command Center | Email/push alert on rejected orders or blocked injections |
| Playbooks | Tested incident templates | A written, rehearsed "agent misbehaved" checklist |
| Drift | Daily evals | Scheduled eval set (e.g., trading rationales cite real numbers) |
| Red teaming | Continuous injection scans | A fixed list of attack prompts run on every change |
| Policy updates | Scheduled reviews | Review each DESIGN_SPEC monthly; incidents update it |

## Why this matters for me
- **GM:** this is a ready-made frame for the stamping AI governance forum: score the portfolio, start at the weakest structural layer, phase over 90 days. (Score GM privately, never in this public repo.)
- **Interviews:** "start at the lowest layer below 3, because the order is structural" is a crisp AI-leader answer.
- **Barber pilot:** Foundation-level hygiene (own key, inventory, kill switch) is cheap and should be there from day one.

## Check yourself
- Why does a layer score its *weakest* area rather than its average?
- Why can't you fix Detection before Foundation?
