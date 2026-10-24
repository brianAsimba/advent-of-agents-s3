# Day 20 — Agent Gateway vs. Apigee: The Tale of Two Gateways
[Page](https://adventofagents.com/2026/10/20) · [Video: Christopher Duncan & Elliott Abraham (10 min)](https://www.youtube.com/watch?v=ikqlZLLYrLA) · [Demo repo](https://g.dev/cloud/adventofagents-season3-day20-demo) · [Agent Gateway docs](https://g.dev/cloud/adventofagents-season3-agent-gateway) · [Apigee docs](https://g.dev/cloud/adventofagents-season3-docs-apigee)

## Core idea
Two boundaries, two questions:
- **Egress (Agent Gateway):** *what may this agent call?* Deny by default, registry allowlist, SPIFFE identity, Model Armor. Sits at the agent runtime boundary.
- **Ingress (Apigee):** *how are enterprise backends consumed?* Fronts SAP, BigQuery, Cloud Run, on-prem; translates REST/SOAP into MCP; mediates schemas so responses stay lean; rate-limits with **Spike Arrest** to stop runaway loops.

Defense in depth: the agent's side controls *reach*, the backend's side controls *consumption*.

## Why ingress matters for agents specifically
- **Runaway loops:** a confused agent can call the same tool hundreds of times in a minute. Humans don't do that; backends aren't sized for it.
- **Hallucinated bursts:** made-up IDs fan out into many failing calls.
- **Context bloat:** legacy APIs return everything. Every byte becomes tokens: cost, latency, and a model that has to find 6 fields in 200 log entries.

## What I built (2026-10-24, real MCP over HTTP + Claude)
- A legacy REST CRM (~23 KB per account), an ingress gateway that exposes it as an MCP tool with mediation, Spike Arrest (2 calls / 10 s / client → 429 + Retry-After) and a body limit, and an egress allowlist on the agent side.
- **Results:** mediation 23,121 → 151 bytes; burst of 5 → `200, 200, 429, 429, 429`, only 2 reached the backend; the same Claude question cost **1,617 vs 20,956 prompt tokens** (13×) mediated vs pass-through, same answer; Claude hit the limit, said so and stopped; going around the ingress gateway was refused by egress.

## Key distinctions
- **Egress vs ingress:** who is protected? Egress protects the world from the agent; ingress protects the backend (and the agent's context) from agent-scale traffic.
- **Mediation vs redaction (Day 11):** mediation trims for relevance and cost; redaction removes sensitive values. Often both, at the same proxy.
- **Spike Arrest vs quota:** Spike Arrest smooths bursts (per second/minute); a quota caps volume (per day/month).

## Connections
- **Barber pilot / SMB clients:** small businesses' systems (Square, Google Calendar, a booking site) have rate limits and fragile APIs. Put a thin proxy in front: lean responses, per-agent rate limits, a kill switch. An n8n workflow or a Cloud Run function can play the Apigee role.
- **Trading agent:** a market-data proxy that trims vendor payloads to OHLCV and enforces a call budget per agent keeps API costs and token costs predictable.
- **Cost of agents:** the 13× token difference is the argument to make to any client: tool response design is a cost lever.

## Check yourself
- Which gateway verifies the agent's identity, and which protects the backend?
- Why do agents need Spike Arrest when human-facing APIs often don't?
- What did mediation change in tokens, and why does it also improve answers?
- How would an agent reach the backend if egress didn't deny it, and why is that bad?
