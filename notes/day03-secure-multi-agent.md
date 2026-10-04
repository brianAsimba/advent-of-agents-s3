# Day 3 — Architecting Secure Multi-Agent Systems
[Page](https://adventofagents.com/2026/10/03) · [Video (13 min)](https://www.youtube.com/watch?v=c89LrULUrmI) · [Companion: Marina Wyss (21 min)](https://www.youtube.com/watch?v=qwsGEbrHnjQ) · [Whitepaper](https://goo.gle/agent-security-enterprise)

## Core idea
No all-powerful "God Agent". Split work across narrow agents so a successful prompt injection compromises only one low-privilege piece. Worked example: a **Multi-Agent Warranty Claims System** (Google Next 2026 paper), an automotive use case worth knowing for OEM interviews.

> The page promises **four** boundaries but documents three. Find the fourth in the video/whitepaper.

## Boundary 1 — Separation of duties
| Agent | Can | Cannot |
|---|---|---|
| Case Manager (orchestrator) | Receive sanitized requests, coordinate | Touch DB or shipping APIs |
| Data Vault (retriever) | Read-only entitlement DB queries | Talk to users |
| Logistics Liaison (executor, own Cloud Run) | Call shipping APIs | See customer/entitlement data |

An injection that fools the Case Manager hits a dead end: it holds no data or action tools.

## Boundary 2 — Trust and verify
- **Agent Identity:** short-lived, mTLS-attested **SPIFFE** certificates per agent (an expiring passport rather than a static key).
- **Agent Gateway:** single policy enforcement point for inbound and agent-to-agent (A2A) traffic. Runs **Model Armor** inline (strips jailbreaks and injections, masks PII before text reaches a model) and uses **IAP** to verify the caller on every hop.
- **Agent Registry:** directory of authorized agents and verified MCP servers.

## Boundary 3 — Private network
- **Private Service Connect:** serverless agents reach backends without the public internet.
- **VPC Service Controls:** a perimeter that blocks data egress, so a compromised agent can't copy data out.

## How Days 1–3 connect
Day 2's "restrict tools" control becomes separation of duties here; "sanitize input" becomes Model Armor at the gateway; Day 1's Govern phase is Identity + Registry + Gateway.

## Applied: Camp VI trading desk
- **Analyst ≈ Data Vault:** reads market data, filings and charts. Read-only. No order tools.
- **Risk manager ≈ Case Manager:** coordinates, enforces sizing and position rules. No broker access.
- **Executor ≈ Logistics Liaison:** only holder of Alpaca credentials; hard limits in code; never sees raw news text.

## Check yourself
- An injected claim fools the Case Manager. What can the attacker *not* do, and why?
- What does a short-lived certificate protect against that a static service-account key doesn't?
