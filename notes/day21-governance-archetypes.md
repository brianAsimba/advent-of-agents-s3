# Day 21 — Governance Archetypes: Central Hub vs. Federated Mesh
[Page](https://adventofagents.com/2026/10/21) · [Video: 5-minute kata (5 min)](https://www.youtube.com/watch?v=pA5KnXxPsHM) · [Demo repo (simulator + Argolis)](https://github.com/arobinson12/advent-of-agents-s3-day21-governance-archetypes) · [Codelab: multi-project Agent Gateway](https://codelabs.developers.google.com/agw-multiproject) · [Agent Registry overview](https://docs.cloud.google.com/agent-registry/overview) · [SAIF](https://safety.google/cybersecurity-advancements/saif/)

## Core idea
At scale (hundreds of agents, many LOBs, several regulated regions), governance is an **architecture choice**. The two failure modes pull in opposite directions: **blind spots** (no one sees the whole estate) vs **bottlenecks** (every change waits on one team).

## The three archetypes
- **A. Single central hub:** one registry + gateway in a management project; spokes route egress through it. Unified SecOps view, org-wide kill switch. Risk: central queue, shared catalog visible to all.
- **B. Federated per LOB/region:** local registries and gateways; org-wide Model Armor floor settings as the only common layer. Autonomy and data residency, no cross-LOB metadata leakage. Risk: no inventory, kill switch per registry.
- **C. Hybrid hub-of-hubs:** LOBs approve locally; the hub aggregates inventory and governs shared **Tier-0** MCP servers.
- **Course rule:** multi-region + shared crown-jewel tools → C; multi-region or autonomous LOBs → B; otherwise A.

## Two-tier SPIFFE scoping
- **Tier 1 (coarse):** `principalSet` for a whole spoke project → baseline Google APIs.
- **Tier 2 (fine):** one `principal` + a CEL condition (destination registered, owned by that service account) → tools and A2A. Zero trust where it matters, without per-workload rules for everything.

## What I built (2026-10-24)
- The advisor (course rule + reasons + one advisory), the two-tier policy generator and an evaluator (default deny), and a simulator that runs one workload through A, B and C.
- **Results** (3 LOBs × 10 agents, 2 Tier-0 servers, one compromised): A = 32 central approvals, 30/30 visible, 60 cross-LOB leaks, 1 kill action. B = 0 approvals, **0/30 visible**, 0 leaks, **3 kill actions** (and revoking in only one registry left 2 of 3 LOBs exposed). C = 2 approvals, 30/30 visible, 0 leaks, 1 kill action.
- **My consulting practice** (one client per spoke, shared tool library) → rule says B; the advisor flags "consider C" because shared tools need one owner and one kill switch.

## Lessons
- **Separate who approves from who sees.** C lets LOBs approve locally while the hub still sees everything.
- **Shared tools are where federation breaks.** A Tier-0 server copied into N registries is N kill switches, and the one you forget stays live.
- **The course rule is a starting point.** Autonomy + shared crown jewels points to C even in one region.

## Connections
- **Consulting practice:** per-client spokes (credentials, data, approvals isolated per client) + my own hub for the shared tool library (calendar, SMS, invoices) with one kill switch. That's C, at small scale.
- **GM governance forum (concepts only):** plants/functions as LOBs, regions for data residency, shared engineering systems as Tier-0. The "who approves vs who sees" split is the clearest way to frame the forum's charter vs the teams' autonomy.
- **Days 9, 15, 18, 19:** access boundaries, regional memory banks, registry and gateway are the building blocks each archetype arranges differently.

## Check yourself
- What two failure modes are the archetypes trading off?
- Why does B need N actions to kill a compromised shared server, and why is that dangerous?
- What is Tier 1 for, and why isn't it enough for tool calls?
- Why can C give LOBs autonomy without creating blind spots?
