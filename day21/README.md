# Day 21 locally: governance archetypes (central hub vs federated mesh vs hub-of-hubs)

A handful of agents in one project is easy to govern. Hundreds, across lines of business (LOBs) and regulated regions, force a choice. Get it wrong and you get **compliance blind spots** (nobody sees everything) or a **developer bottleneck** (everything waits on one team).

| Archetype | Shape | Strength | Weakness |
|---|---|---|---|
| **A. Central hub** | one registry + one gateway; spokes route egress through the hub | one inventory, one org-wide kill switch | every approval queues on the central team; one shared catalog leaks metadata across LOBs |
| **B. Federated** | each LOB/region runs its own registry and gateway; org-wide floor settings on top | autonomy, data residency, no cross-LOB metadata | no central inventory; a kill switch is N separate actions |
| **C. Hub-of-hubs** | LOBs approve their own agents; a hub aggregates the inventory and owns shared Tier-0 servers | local speed + central visibility + one kill switch for shared tools | two layers to run |

**Two-tier identity scoping:** Tier 1 is coarse: a `principalSet` lets every workload in a spoke project reach baseline Google APIs. Tier 2 is fine: a single `principal` (one agent) may call MCP servers only if a condition holds (`destination.registered && destination.owner == ...`). Everything else is denied by default.

| Course | Here |
|---|---|
| `governance_archetype_advisor.py`: topology dataclass, `recommend_archetype()` | `advisor.Topology`, `advisor.recommend()` (same rule, with reasons and one advisory) |
| `generate_two_tier_hub_policy()` → `central_hub_uap.json` | `advisor.two_tier_policy()` → `.out/central_hub_uap.json` (gitignored) |
| Agent Gateway evaluates the policy | `advisor.evaluate()`: Tier 1, Tier 2, default deny |
| Argolis simulator for the three archetypes | `mesh.py`: the same workload through A, B and C, measured |

## Run (repo root)
```bash
uv run pytest day21 -q
```
```bash
uv run python day21/demo.py
```

## What my run showed (2026-10-24)
**Policy:** concierge → Vertex AI (Tier 1) ALLOW; batch job in the same spoke → Vertex AI ALLOW (coarse) but → the MCP server DENY (fine); concierge → an unregistered MCP server DENY; the same agent name in another spoke → DENY (SPIFFE IDs include the project).

**Same workload** (3 LOBs × 10 agents, 2 shared Tier-0 servers, one compromised):

| | central approvals | central sees | cross-LOB leaks | kill-switch actions |
|---|---|---|---|---|
| A. Central hub | 32 | 30/30 | 60 | 1 |
| B. Federated | 0 | 0/30 | 0 | 3 |
| C. Hub-of-hubs | 2 | 30/30 | 0 | 1 |

In B, revoking the compromised server in only one registry left **2 of 3 LOBs still able to call it**.

**My consulting practice** (one client per spoke, a shared tool library): the course rule says **B** (autonomous clients, one region), but shared tools still need one owner and one kill switch, so the advisor flags **consider C**.
