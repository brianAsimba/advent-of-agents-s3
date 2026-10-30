# Day 23 locally: agent topology and blast radius (see what breaks before you delete a tool)

Before retiring an MCP server or shipping a breaking change to one of its tools, you need two answers: **who declared a dependency** on it, and **who is calling it right now**. That information is usually spread over the registry, runtimes, traces and READMEs. App Topology puts it in one graph you can query.

| Course (App Topology) | Here |
|---|---|
| Discovered resources as nodes | `topology.Node`: Agent, MCPServer, Binding (from `estate.json`, servers from Days 18–20) |
| `DEPENDS_ON` edges (Agent Registry bindings) | Agent → Binding → MCPServer |
| `Observability/SENDS_TRAFFIC` edges from Cloud Trace, with error rate and p95 | built from OpenTelemetry tool-call spans (Day 22 shape): calls, error rate, p95 per agent→server |
| JSON pattern: start node, edge label, direction (`FROM` = who points at me), node types | `topology.query(pattern)` |
| `blast_radius.py`: dependents + callers → SAFE / STOP + owners | same; exit 0 SAFE, 1 STOP, 2 not found (usable as a CI gate) |
| App Topology remote MCP server + Gemini CLI | `topology_mcp.py` (read-only) + a Claude agent |

## Run (repo root)
```bash
uv run python day23/blast_radius.py --list
```
```bash
uv run python day23/blast_radius.py legacy-search-mcp
```
```bash
uv run python day23/demo.py
```

## What my run showed (2026-10-29)
**Static vs live disagree**, for `legacy-search-mcp`:
- the registry says `revenue-insights-agent`, `support-concierge`;
- traces say `nightly-report-job`, `support-concierge`;
- **shadow consumer:** `nightly-report-job` calls it with no binding (17% errors, p95 5.9 s). A registry-only review would miss it, and retiring the server would break it silently;
- **stale binding:** `revenue-insights-agent` is registered but sent nothing in 24 h.

**Verdicts:** `weather-mcp` SAFE; `legacy-search-mcp` STOP (contact cx-team, data-eng, finance-analytics); `crm-accounts-mcp` STOP (billing-ops, cx-team).

**Plain English via MCP:** Claude answered "not safe", named the shadow caller and all three teams, and flagged that a 24 h window can miss weekly or monthly jobs. My first version of `generate_resources_graph` returned a bare `[]` when Claude's pattern didn't match (it tried Agent → MCPServer directly), and Claude reported the lookups "came back empty". Now the tool returns a count, readable paths, and a **hint describing the edge model** on empty results.
