"""Day 18 local Agent Registry: one catalog of MCP servers and agents; agents bind tools by NAME.

What Google Cloud does                                     What this file does
---------------------------------------------------------  --------------------------------------------------------
Auto-registration (MCP_SERVER label) / gcloud agent-registry register_mcp(): starts the server, introspects its tools
Catalog of agents, MCP servers, tool schemas               .registry/registry.json (gitignored, rebuilt by the demo)
Search before you build (Antigravity CLI + registry MCP)   search(), and registry_mcp.py for Claude Code
Duplicate work across teams                                 register_mcp() reports overlapping tools
AgentRegistry.get_mcp_toolset(mcp_server_name=...)          get_mcp_toolset(name, agent): no paths or URLs in agent code
Agent Gateway in front of every tool call                   the toolset connects through mcp_gateway.py, never directly
"""
import json
import os
import re
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent
STORE = Path(os.environ.get("DAY18_STORE", HERE / ".registry"))  # tests point this at a temp folder
REGISTRY = STORE / "registry.json"
sys.path.insert(0, str(HERE.parent / "day05"))
import iam_lib  # noqa: E402  (Day 5: one signed identity per agent)


def _load() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {"mcp_servers": {}, "agents": {}}


def _save(data: dict) -> None:
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _params(entry: dict, env: dict | None = None) -> StdioServerParameters:
    return StdioServerParameters(command=sys.executable, args=[str(HERE / a) for a in entry["launch"]],
                                 env={**os.environ, **(env or {})})


async def _introspect(entry: dict) -> list[dict]:
    async with stdio_client(_params(entry)) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = await s.list_tools()
            return [{"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
                    for t in res.tools]


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 3}


async def register_mcp(name: str, launch: list[str], owner: str, description: str) -> dict:
    """Registers an MCP server by introspecting its tools. Returns the entry plus any overlap with existing tools."""
    entry = {"name": name, "kind": "mcp_server", "owner": owner, "description": description,
             "endpoint": f"stdio://{name}", "launch": launch}
    entry["tools"] = await _introspect(entry)
    data = _load()
    overlaps = []
    for other in data["mcp_servers"].values():
        if other["name"] == name:
            continue
        for t in entry["tools"]:
            for o in other["tools"]:
                if t["name"] == o["name"] or len(_words(t["description"]) & _words(o["description"])) >= 3:
                    overlaps.append(f"{t['name']} looks like {other['name']}/{o['name']}")
    data["mcp_servers"][name] = entry
    _save(data)
    return {**entry, "overlaps": overlaps}


def register_agent(name: str, uses: list[str], owner: str) -> dict:
    data = _load()
    entry = {"name": name, "kind": "agent", "owner": owner, "identity": iam_lib.spiffe_id(name), "uses": uses}
    data["agents"][name] = entry
    _save(data)
    return entry


def search(query: str) -> list[dict]:
    """Finds MCP servers and tools whose name or description matches any word of the query."""
    q = _words(query) | set(query.lower().split())
    hits = []
    for s in _load()["mcp_servers"].values():
        for t in s["tools"]:
            text = f"{s['name']} {s['description']} {t['name']} {t['description']}".lower()
            score = sum(w in text for w in q)
            if score:
                hits.append({"server": s["name"], "owner": s["owner"], "tool": t["name"],
                             "description": t["description"], "score": score})
    return sorted(hits, key=lambda h: -h["score"])


def get(name: str) -> dict:
    s = _load()["mcp_servers"].get(name)
    if s is None:
        raise KeyError(f"'{name}' is not in the registry")
    return s


def gateway_params(server_name: str, agent_name: str) -> StdioServerParameters:
    """How an agent reaches a registered server: always through the gateway, carrying its own identity token.
    The platform mints the token; the model never sees it."""
    get(server_name)
    token = iam_lib.mint(agent_name)
    return StdioServerParameters(command=sys.executable, args=[str(HERE / "mcp_gateway.py"), server_name],
                                 env={**os.environ, "AGENT_TOKEN": token})


def get_mcp_toolset(server_name: str, agent_name: str):
    from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
    return McpToolset(connection_params=StdioConnectionParams(
        server_params=gateway_params(server_name, agent_name), timeout=30))


if __name__ == "__main__":
    for h in search(" ".join(sys.argv[1:]) or "revenue"):
        print(f"{h['server']:<26} {h['tool']:<28} {h['description']}")
