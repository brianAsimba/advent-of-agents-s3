# Day 20 locally: two gateways (egress vs ingress)

Agents need **two** security boundaries:
- **Egress (Agent Gateway, Days 8/18/19):** *may this agent reach this endpoint or tool?* Deny by default, registry allowlist, SPIFFE identity, inline screening.
- **Ingress (Apigee, today):** *how may agents consume this backend?* Turn existing REST/SOAP APIs into MCP tools without rewriting them, trim responses so they don't bloat the model's context, and stop runaway loops before they hammer the backend.

| Course (Apigee) | Here |
|---|---|
| Enterprise backend (SAP, BigQuery, on-prem) | `legacy_crm.py`: one REST endpoint, a ~23 KB response per account |
| Apigee MCP proxy: REST → MCP JSON-RPC at `/v1/mcp` | `ingress_gateway.py`: `lookup_customer_account` calls the REST API (stateless, JSON responses, curl-friendly) |
| Schema mediation (lean responses) | `mediate()`: 6 agreed fields; `--no-mediation` passes everything through for comparison |
| Spike Arrest → HTTP 429 | `SpikeArrest`: 2 `tools/call` per 10 s per `x-client-id`, `Retry-After`; discovery isn't limited |
| Payload limits | request bodies over 16 KB → 413 |
| Agent Gateway egress, deny by default | `billing_agent.egress_toolset()`: only governed MCP endpoints; the raw backend is refused |

## Run (repo root)
```bash
uv run pytest day20 -q
```
```bash
uv run python day20/demo.py
```

## What my run showed (2026-10-24)
1. `tools/list` through the gateway → `lookup_customer_account`: the legacy API became an MCP tool with no backend change.
2. **Mediation:** backend 23,121 bytes → agent 151 bytes (153× smaller).
3. **Runaway loop**, 5 rapid calls: `200, 200, 429, 429, 429`, and only **2 of 5** reached the backend (the course's "halts on call #3").
4. **Context bloat with Claude**, same question: **1,617** prompt tokens through the mediated gateway vs **20,956** pass-through (13×), the same answer either way. That's the cost and context difference on every call.
5. Claude asked for five balances: it got two, saw the rate limit, said so and **stopped** (no retry storm).
6. Pointing the agent straight at the backend → refused by the egress allowlist.
