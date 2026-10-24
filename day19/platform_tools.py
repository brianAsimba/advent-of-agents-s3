"""Day 19 platform code: resolve tools at runtime through the registry's MCP server, bind credentials centrally,
screen every tool result inline. Agents built here contain no endpoint URL and no credential.

governed_agent()   the course's design (resolve -> bind -> screen; fails closed)
hardcoded_agent()  the anti-pattern: URL in code, API key from .env
"""
import json
import os
import sys
from pathlib import Path

from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams, StreamableHTTPConnectionParams
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "day10"))
import catalog  # noqa: E402
import shield  # noqa: E402  (Day 10 rules: the inline "Model Armor floor" for tool traffic)

MODEL = LiteLlm(model="anthropic/claude-opus-5-5")
BLOCKED = "Tool result blocked by inline screening (possible prompt injection)."  # fixed wording
SCREEN_LOG: list[dict] = []
INSTRUCTION = ("You are governed_release_auditor. Answer questions about product releases using only the "
               "release-notes tools. Be brief. If a tool result is blocked, say so plainly.")


class Unresolvable(Exception):
    pass


def _registry_params() -> StdioServerParameters:
    return StdioServerParameters(command=sys.executable, args=[str(HERE / "registry_mcp.py")], env=dict(os.environ))


def _payload(res):
    if res.structured_content is not None:
        sc = res.structured_content
        return sc.get("result", sc) if isinstance(sc, dict) else sc
    return json.loads(res.content[0].text) if res.content else None


async def resolve(search: str) -> dict:
    """Asks the registry (over MCP) for an APPROVED server. Raises if none: no silent fallback URL."""
    bindings = []
    async with stdio_client(_registry_params()) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            hits = _payload(await s.call_tool("search_mcp_servers", {"searchString": search})) or []
            approved = [h for h in hits if h["status"] == "APPROVED" and h["interfaces"]]
            if approved:
                bindings = _payload(await s.call_tool("fetch_available_bindings", {"name": approved[0]["name"]})) or []
    if not approved:  # decided after the connection closes, so the error isn't wrapped in a task group
        raise Unresolvable(f"no APPROVED MCP server matches '{search}' (found: "
                           f"{[(h['name'], h['status']) for h in hits] or 'none'})")
    entry = approved[0]
    if not bindings:
        raise Unresolvable(f"no auth binding for {entry['name']}")
    return {"name": entry["name"], "url": entry["interfaces"][0]["url"], "version": entry["version"],
            "binding": bindings[0]["binding"]}


def screen_result(tool, args, tool_context, tool_response):
    """after_tool_callback: inline screening of what came back from the MCP server."""
    text = json.dumps(tool_response, default=str)
    v = shield.screen_rules(text)
    SCREEN_LOG.append({"tool": tool.name, "action": v.action, "reason": v.reason})
    return {"status": "blocked", "message": BLOCKED} if v.action == "BLOCK" else None


def registry_toolset() -> McpToolset:
    """Read-only discovery tools for the agent (course: the registry discovery toolset)."""
    return McpToolset(connection_params=StdioConnectionParams(server_params=_registry_params(), timeout=30),
                      tool_filter=["search_mcp_servers", "get_mcp_server", "fetch_available_bindings"])


async def governed_agent(search: str = "release") -> tuple[Agent, dict]:
    target = await resolve(search)
    binding = target["binding"]
    governed = McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=target["url"], timeout=20),
        # The credential is looked up per connection, from the auth manager. Not in code, .env or the prompt.
        header_provider=lambda ctx: {"Authorization": f"Bearer {catalog.credential(binding)}"})
    agent = Agent(name="governed_release_auditor", model=MODEL, instruction=INSTRUCTION,
                  tools=[governed], after_tool_callback=screen_result)
    return agent, {k: target[k] for k in ("name", "url", "version")}


HARDCODED_URL = "http://127.0.0.1:8191/mcp"  # the anti-pattern


def hardcoded_agent() -> Agent:
    tools = McpToolset(connection_params=StreamableHTTPConnectionParams(
        url=HARDCODED_URL, timeout=10, headers={"Authorization": f"Bearer {os.environ.get('RELEASE_API_KEY', '')}"}))
    return Agent(name="hardcoded_release_auditor", model=MODEL, instruction=INSTRUCTION, tools=[tools])
