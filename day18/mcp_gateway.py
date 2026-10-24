"""Day 18 Agent Gateway: an MCP proxy between an agent and one registered MCP server.

Started per connection: `python day18/mcp_gateway.py <server-name>` with AGENT_TOKEN in its environment.
  - verifies the agent's identity token (Day 5) before anything else
  - Rule 1: discovery (initialize, tools/list) is allowed, so the agent can see the schemas
  - Rule 2: tools/call is allowed ONLY for tools on that identity's allowlist; anything else is
            answered with 403 and never reaches the server (implicit deny)
  - writes every decision to .registry/gateway_audit.jsonl
"""
import json
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
from mcp import ClientSession, types
from mcp.client.stdio import stdio_client
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import agent_registry as registry  # noqa: E402

POLICY_FILE = HERE / "policy.json"
AUDIT_FILE = registry.STORE / "gateway_audit.jsonl"


def allowed_tools(principal: str | None, server: str) -> set[str]:
    rules = json.loads(POLICY_FILE.read_text(encoding="utf-8"))["rules"]
    return {t for r in rules if r["principal"] == principal and r["server"] == server for t in r["allow_tools_call"]}


def audit(principal, server, method, tool, allowed, reason="") -> None:
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%H:%M:%S"), "principal": principal, "server": server,
                            "method": method, "tool": tool, "allowed": allowed, "reason": reason}) + "\n")


def identity() -> tuple[str | None, str]:
    try:
        return registry.iam_lib.verify(os.environ.get("AGENT_TOKEN", "")), ""
    except PermissionError as e:
        return None, str(e)


async def main(server_name: str) -> None:
    principal, why = identity()
    entry = registry.get(server_name)
    allow = allowed_tools(principal, server_name)

    @asynccontextmanager
    async def upstream_lifespan(_):
        async with stdio_client(registry._params(entry)) as (r, w):
            async with ClientSession(r, w) as up:
                await up.initialize()
                yield {"up": up}

    async def on_list_tools(ctx, params):
        if principal is None:
            audit(None, server_name, "tools/list", None, False, f"identity rejected: {why}")
            return types.ListToolsResult(tools=[])
        audit(principal, server_name, "tools/list", None, True)
        return await ctx.lifespan_context["up"].list_tools()

    async def on_call_tool(ctx, params: types.CallToolRequestParams):
        if principal is None or params.name not in allow:
            reason = f"identity rejected: {why}" if principal is None else "tool not on this agent's allowlist"
            audit(principal, server_name, "tools/call", params.name, False, reason)
            return types.CallToolResult(is_error=True, content=[types.TextContent(
                type="text", text=f"403 PERMISSION_DENIED by Agent Gateway: {reason}")])
        audit(principal, server_name, "tools/call", params.name, True)
        return await ctx.lifespan_context["up"].call_tool(params.name, params.arguments or {})

    server = Server("agent-gateway", lifespan=upstream_lifespan, on_list_tools=on_list_tools, on_call_tool=on_call_tool)
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main, sys.argv[1])
