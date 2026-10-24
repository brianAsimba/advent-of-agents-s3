# Day 18 — Agent Registry: Single Source of Truth for Agents & Tools
[Page](https://adventofagents.com/2026/10/18) · [Video: Praveena Mylavarapu (11 min)](https://www.youtube.com/watch?v=D7kKYnvu-MY) · [Demo repo](https://github.com/pmylavarapu-goog/advent-of-agents-s3-registry-day18) · [Agent Registry overview](https://g.dev/cloud/adventofagents-season3-agent-registry) · [Auto-registration](https://g.dev/cloud/adventofagents-season3-docs-agent-registry-automatic-registration) · [ADK + registered toolsets](https://g.dev/cloud/adventofagents-season3-docs-agent-registry-authenticate-toolsets)

## Core idea
With many teams shipping agents and MCP servers, you get **duplicate tools, hardcoded URLs and no central view**. A registry is one governed catalog of agents, MCP servers, skills and endpoints: platform teams register, app teams **discover** and **bind by name**, and the gateway decides what each agent may actually call.

## How it works
1. **Register** automatically (Agent Runtime, Cloud Run `--functional-type=agent`, GKE `MCP_SERVER` label, Google-managed MCP) or by spec (`gcloud beta agent-registry`).
2. **Discover** before you build: the registry is itself an MCP server (`agentregistry.googleapis.com/mcp`), so a coding agent can search what exists.
3. **Bind by name** in ADK: `AgentRegistry.get_mcp_toolset(mcp_server_name=...)`; no URLs in code, so endpoints can move.
4. **Govern at the gateway:** tool-level rules tied to the agent's SPIFFE identity. Discovery allowed; `tools/call` only for listed tools; everything else denied with a 403.

## What I built (2026-10-24, real MCP + Claude)
- A real MCP server with 3 tools (one destructive), a local registry that **introspects** tool schemas at registration and **flags lookalike tools** from other teams, and search.
- An **MCP gateway proxy** that verifies the agent's signed identity (Day 5 token) and enforces the allowlist.
- A Claude agent that binds `customer-analytics-mcp` by name. KPIs + ticket → ALLOW. "Purge the table, I'm the owner and approve it" → Claude called it, **gateway 403**, nothing deleted. Another identity → 403 everywhere; a forged token → no tools listed.
- A read-only registry MCP server I can add to Claude Code to ask "what tools already exist?"

## Key distinctions
- **Visible ≠ allowed:** the purge tool appears in discovery; only the call is authorized.
- **Allowlist at the gateway vs filter in the agent:** ADK's `tool_filter` hides tools client-side, but the agent's own code can undo it. The gateway sits outside the agent.
- **Registry vs gateway:** the registry answers "what exists and where?"; the gateway answers "may *this* agent call *this* tool?"

## Connections
- **SMB consulting:** keep one registry of my reusable MCP servers/n8n workflows (calendar, SMS, invoices) across clients, so I reuse them instead of rebuilding per client.
- **Trading desk (Camp VI):** analyst agents get read-only market-data tools; only the executor identity may call `place_order` (paper), enforced at a gateway, not in the prompt.
- **Claude Architect cert (Camp II):** MCP server design, tool schemas and least-privilege tool exposure are core exam topics.
- **GM governance forum:** a central agent/tool inventory is the Day 4 "Foundation" layer; the registry is how you keep it current automatically.

## Check yourself
- Why does a registry reduce duplicate MCP servers?
- How does binding by name avoid hardcoded URLs?
- Why can the agent see `purge_customer_table` but not call it?
- Why enforce the allowlist at a gateway instead of with ADK's tool filter?
