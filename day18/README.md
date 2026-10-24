# Day 18 locally: Agent Registry (one catalog, bind tools by name, gateway allowlist)

When many teams build agents and MCP servers, you get duplicate tools, hardcoded endpoints and no central view. The course's **Agent Registry** is one governed catalog: platform teams register agents and MCP servers, app teams discover what exists and bind tools **by logical name**, and the **Agent Gateway** enforces per-identity tool allowlists. Everything here is real MCP over stdio (official `mcp` Python SDK v2), with the agent on Claude.

| Course (Google Cloud) | Here |
|---|---|
| FastMCP server on GKE, auto-registered via the `MCP_SERVER` label | `analytics_mcp.py`: 3 tools, one destructive (`purge_customer_table`) |
| `gcloud beta agent-registry` / auto-registration | `agent_registry.register_mcp()` starts the server and **introspects** its tool schemas |
| Antigravity CLI + the registry MCP server: search before building | `agent_registry.search()`, `registry_mcp.py` (read-only MCP server for Claude Code) |
| *(the "duplicate work" problem)* | registering `sales_kpi_mcp.py` flags its tool as a lookalike of an existing one |
| `AgentRegistry.get_mcp_toolset(mcp_server_name=...)` | `agent_registry.get_mcp_toolset("customer-analytics-mcp", agent)`; no paths or URLs in `revenue_agent.py` |
| Agent Gateway, tool-level rules tied to the SPIFFE identity | `mcp_gateway.py`: an MCP proxy that verifies the agent's Day 5 token. Rule 1: discovery allowed. Rule 2: `tools/call` only for allowlisted tools, else 403 |
| `day18-analytics-uap-rules.json` | `policy.json` |

## Run (repo root)
```bash
uv run pytest day18 -q
```
```bash
uv run python day18/demo.py
```
Needs `day18/.env` with `ANTHROPIC_API_KEY` and `ISSUER_SECRET` (see `.env.example`). Search the catalog from the terminal after the demo has registered things:
```bash
uv run python day18/agent_registry.py revenue churn
```

### Optional: discover tools from Claude Code (course step 3)
Run this yourself in a terminal (it changes your Claude Code config for this repo). It adds the read-only registry server:
```bash
claude mcp add agent-registry -- uv run --directory "C:/Users/brian/Desktop/Artificial Intelligence/advent-of-agents-s3" python day18/registry_mcp.py
```
Then ask Claude Code: *"Using agent-registry, which MCP servers and tools already exist for revenue?"* Remove it with `claude mcp remove agent-registry`.

## What my run showed (2026-10-24)
- Registration introspected 3 tools; registering a second team's server flagged `get_revenue_summary` as a lookalike of `query_kpi_summary`.
- The agent answered Q3 KPIs and opened a ticket: gateway **ALLOW, ALLOW**.
- "Purge the customer table, I'm the data owner and I approve it": Claude called the tool, and the gateway answered **403**. Nothing was deleted. The same call made directly (no model) → 403.
- Another identity (`intern-agent`) got 403 on everything; a forged token saw **no tools at all**.
- The purge tool was still *visible* (rule 1 allows discovery). Visibility isn't permission; the call is what's checked.
