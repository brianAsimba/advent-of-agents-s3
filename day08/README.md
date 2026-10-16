# Day 8 on Claude: agent policies at a gateway

An MCP server often bundles safe tools (`lookup_order`) with dangerous ones (`issue_refund`, `delete_account`) on one endpoint. "Never delete accounts" in a prompt is not a boundary. The course puts **Agent Gateway** between agents and tools, enforcing an **IAM Access Policy** bound to each agent's identity. This folder models it locally:

| Course | Here |
|---|---|
| Agent Gateway inspects every outbound call | `gateway.call()` is the only path to the tool server |
| Default deny on egress | Unmatched requests → 403 |
| `DENY` rules evaluated before `ALLOW` | `decide()` |
| Principals = SPIFFE identities (Day 5) | Caller verified from its Day 5 token; wildcards like `agents/*` |
| CEL on `destination.agent_registry.mcp_server.tool.name` | `{"tool_name_in": [...]}` in `policy.json` (plain data, no `eval`) |
| Agent Registry | `REGISTRY`: only `orders-mcp` is approved |

Policy (`policy.json`): nobody may `delete_account`; `support_agent` may not `issue_refund`; registered servers allowed; everything else denied.

## Run
```bash
uv run pytest day08 -q
```
```bash
uv run python day08/demo.py
```
1. **Decisions table** (no model): read allowed; refund denied for support but allowed for refunds; delete denied for everyone; an unregistered URL default-denied.
2. **Live on Claude:** a normal order lookup; then a message with an injected "SYSTEM NOTICE" asking for a $500 refund, an account deletion and a data upload to an outside URL; then the refunds agent's approved $20 refund.
3. **Audit** and the list of calls that actually reached the tool server.

The support agent's prompt is deliberately permissive ("do what the customer asks"): the gateway, not the prompt, is the boundary.
