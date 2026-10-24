# Day 19 locally: dynamic MCP governance (no hardcoded endpoints or keys)

Hardcoding an MCP server's URL and API key in agent code or `.env` breaks the day the platform team **moves** an endpoint, **patches** a vulnerable server or **revokes** a compromised integration: the agent either fails or keeps calling something it shouldn't. Day 19 resolves tools at **runtime** through the registry's own MCP server, binds credentials in **one** governed place, and screens tool traffic inline. Real MCP throughout: the tool server speaks streamable HTTP and requires a bearer key; the agent runs on Claude.

| Course (Google Cloud) | Here |
|---|---|
| Registry Services API `create_service`, Terraform registry resources | `catalog.register_service / update_endpoint / revoke` (platform-side) |
| Registry meta-MCP: `search_mcp_servers`, `get_mcp_server`, `fetch_available_bindings` | `registry_mcp.py` (same tool names, read-only, never returns secrets) |
| `AuthProviderBinding` → Agent Auth Manager (keys, OAuth, IAM) | `catalog.bind_credential / credential`: the key lives only in the store; rotation keeps the binding name |
| ADK resolves an approved endpoint, errors if none | `platform_tools.resolve()`: APPROVED only, **fails closed** |
| Governed `McpToolset` (`StreamableHTTPConnectionParams`) | Same, with a `header_provider` that reads the *current* key per connection |
| Model Armor floor `GOOGLE_MCP_SERVER: INSPECT_AND_BLOCK` | `after_tool_callback` → Day 10's `shield.screen_rules` on every tool result |
| Remote MCP server (GitHub) with a PAT | `release_mcp.py` on localhost; 401 without the bound key, and it rejects unknown `Host` headers |
| *(the anti-pattern)* | `hardcoded_agent()`: URL in code, key copied into `.env` |

## Run (repo root)
```bash
uv run pytest day19 -q
```
```bash
uv run python day19/demo.py
```
It starts release servers v1 (port 8191) and v2 (8192) and stops them at the end. Each run uses a fresh temporary registry and credential store.

## What my run showed (2026-10-24)
1. **Day one:** both agents answered from the v1 server.
2. **Security patch:** the platform moved the service to v2 and rotated the key, then shut v1 down. The **governed** agent resolved v2 and kept working with no code change. The **hardcoded** agent's tools **failed to load, and ADK started it anyway with no tools**, logging only a warning. Claude honestly said it had no tool; a less careful model could have made up an answer. Code should check that tools loaded, not trust that the agent "started".
3. **Inline screening:** the 1.4.0 notes contained an instruction aimed at AI agents. Blocked before the model saw it (1 block, rules layer).
4. **Revocation:** status `REVOKED` in the registry → the governed agent **refused to start** (fails closed).
