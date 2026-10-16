# Day 8 — Agent Policies: Stop Agents from Calling Dangerous Tools
[Page](https://adventofagents.com/2026/10/08) · [Video (5 min)](https://www.youtube.com/watch?v=l6I5POMbqME) · [Companion: Abhishek Veeramalla (12 min)](https://www.youtube.com/watch?v=QE-jDKvh4yU) · [Agent Gateway](https://g.dev/cloud/adventofagents-season3-agent-gateway) · [IAM Access Policies](https://g.dev/cloud/adventofagents-season3-day8-iam-access-policies) · [Demo repo](https://g.dev/cloud/adventofagents-season3-day8-github-demo)

## Core idea
MCP servers often put safe tools (`lookup_order`) next to dangerous ones (`issue_refund`, `delete_account`) on the same endpoint. "Never delete customer accounts" in the system prompt is **not a security boundary**: a prompt injection or a model mistake can still trigger the tool. **Agent Gateway** is a network checkpoint between agents and tools that enforces policy *before* the call reaches the backend.

## How the policy works
- **Default deny:** the gateway blocks all outbound traffic unless a rule allows it.
- **One IAM Access Policy, bound to agent identities** (Day 5's SPIFFE IDs; `principalSet://…/*` matches all agents in the org).
- **ALLOW** rule: trusted destinations (`googleapis.com` for the model and logging, plus MCP servers registered in **Agent Registry**).
- **DENY** rule: a hard guardrail, **evaluated first**. A CEL condition on `destination.agent_registry.mcp_server.tool.name` blocks `delete_account` and `issue_refund` with **HTTP 403** at the proxy; `lookup_order` passes.

## How Day 8 fits the earlier days
| Day | Control | Where it runs |
|---|---|---|
| 2 | `before_tool_callback` (DURING checkpoint) | Inside the agent's process |
| 3 | `enforce_limits` on the executor | Inside the agent's process |
| 5 | Identity + IAM on data | At the data service |
| **8** | **Gateway policy on tool calls** | **Outside the agent, on the network path** |
Day 8's advantage: the control holds even if the agent's own code is buggy, misconfigured or compromised, because the agent can't skip the gateway.

## Running it without Google Cloud
`day08/`: a local gateway with `policy.json` (DENY first, then ALLOW, else default deny), identities from Day 5, a registry, and a tool server that only the gateway can reach. A permissive support agent on Claude gets an injected "SYSTEM NOTICE" asking for a refund, a deletion and an upload to an outside URL.

## Connections
- **Trading agent / Camp VI:** the executor's broker calls should pass a gateway policy (allowed tickers, sides, max size) that lives outside the agent, a stronger version of Day 3's `enforce_limits`.
- **Barber pilot:** read tools (availability) allowed; cancellations only for the owner identity; any unregistered URL blocked (stops data exfiltration).
- **GM / Day 4:** this is the Prevention layer's "every tool call routes via a gateway".

## Check yourself
- Why must DENY rules be evaluated before ALLOW rules?
- What does a gateway protect against that an in-agent callback (Day 2) doesn't?
- Why is "default deny" the right starting point for agent egress?
