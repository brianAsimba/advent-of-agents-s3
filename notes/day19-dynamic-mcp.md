# Day 19 — Dynamic MCP Governance: Eliminating Hardcoded Tool Endpoints
[Page](https://adventofagents.com/2026/10/19) · [Video: 5-minute kata (6 min)](https://www.youtube.com/watch?v=5GPvyWraUiY) · [Demo repo](https://github.com/arobinson12/advent-of-agents-s3-day19-mcp-governance) · [Registry MCP server](https://docs.cloud.google.com/agent-registry/use-agentregistry-mcp) · [Registry MCP tools reference](https://docs.cloud.google.com/agent-registry/reference/mcp) · [ADK MCP tools](https://google.github.io/adk-docs/tools/mcp-tools/)

## Core idea
A hardcoded MCP URL and key in code or `.env` turns every platform change into an outage or a risk. When an endpoint **moves**, a server is **patched** or an integration is **revoked**, hardcoded agents either break or keep calling something unvetted. Fix: resolve tools **at runtime** through the registry, keep credentials in **one** governed place, and screen tool traffic **inline**.

## How it works
1. **Register** three ways: auto-discovery (Agent Engine, Cloud Run, GKE, Apigee), the Services API (`create_service`, e.g. GitHub's MCP), or Terraform (`google_agent_registry_service`, `..._binding`).
2. **AuthProviderBinding:** links a registered server to Agent Auth Manager (API keys/PATs, 3-legged OAuth delegation, Google IAM), so credentials never live in agent repos.
3. **Meta-MCP discovery:** the agent connects to the registry's MCP server and calls `search_mcp_servers`, `get_mcp_server`, `fetch_available_bindings` (needs `mcp.toolUser` + `agentregistry.viewer`).
4. **Model Armor floor settings** with `GOOGLE_MCP_SERVER: INSPECT_AND_BLOCK` screen MCP tool calls for injection and sensitive data.

## What I built (2026-10-24, real MCP over HTTP + Claude)
- A release-notes MCP server over streamable HTTP that needs a bearer key (read from the credential store per request), a read-only registry meta-MCP with the course's three tools, and platform code that resolves APPROVED servers only and attaches the current key per connection.
- **Run:** after moving to v2 and rotating the key, the governed agent kept working with no code change. The hardcoded agent's tools failed to load, and **ADK still started it, with zero tools**, only logging a warning. Screening blocked an injected instruction in the 1.4.0 notes. Revocation made the governed agent refuse to start.

## Lessons
- **Resolve late, fail closed.** No approved match = no agent. Never fall back to a cached URL.
- **Bind by name, rotate the value.** The binding name stays stable; the key behind it can change at any time.
- **Check that tools actually loaded.** An agent that starts without its tools is a silent failure; the model may guess instead of saying "no tool".
- **Discovery tools never return secrets.** `fetch_available_bindings` gives names and types only.

## Connections
- **SMB clients / barber pilot:** each client's credentials (Google Calendar OAuth, Twilio, Stripe) in one secret store keyed by client + binding name; n8n and agents reference the name. Rotating a leaked key = one update, no redeploy.
- **Trading agent:** Alpaca paper keys behind a binding name; a "revoked" flag that makes the executor refuse to start is a clean kill switch.
- **Day 17:** registry entries and bindings belong in IaC (the course's Terraform resources), so an endpoint move is a reviewed PR.

## Check yourself
- What three platform events break a hardcoded agent?
- Why should resolution fail closed instead of falling back to the last known URL?
- What does `fetch_available_bindings` return, and what does it deliberately not return?
- Why check that an agent's tools loaded, not just that it started?
