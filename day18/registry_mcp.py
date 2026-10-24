"""The registry itself as an MCP server (course: agentregistry.googleapis.com/mcp, used from Antigravity CLI).
Read-only: it can search and describe, never register or call tools. Add it to Claude Code with the
command in day18/README.md to ask "what MCP servers and tools already exist?" before writing new ones.
"""
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_registry as registry  # noqa: E402

server = MCPServer("agent-registry", version="1.0.0")


@server.tool()
def list_mcp_servers() -> list[dict]:
    """Every registered MCP server with its owner and tool names."""
    return [{"name": s["name"], "owner": s["owner"], "description": s["description"],
             "tools": [t["name"] for t in s["tools"]]} for s in registry._load()["mcp_servers"].values()]


@server.tool()
def search_tools(query: str) -> list[dict]:
    """Searches registered tools by keyword (name or description)."""
    return registry.search(query)


@server.tool()
def get_tool_schemas(server_name: str) -> list[dict]:
    """Input schemas of every tool on one registered MCP server."""
    return registry.get(server_name)["tools"]


if __name__ == "__main__":
    server.run("stdio")
