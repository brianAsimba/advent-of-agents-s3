"""The registry's own MCP server ("meta-MCP"; course: https://agentregistry.googleapis.com/mcp). Read-only.

Tools match the course: search_mcp_servers, get_mcp_server, fetch_available_bindings.
fetch_available_bindings returns binding NAMES and types, never secret values.
"""
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog  # noqa: E402

server = MCPServer("agent-registry", version="1.0.0")


@server.tool()
def search_mcp_servers(searchString: str) -> list[dict]:  # noqa: N803 (name matches the course API)
    """Searches registered MCP servers by name or description."""
    q = searchString.lower()
    return [{k: s[k] for k in ("name", "description", "version", "status", "interfaces")}
            for s in catalog.services().values() if q in s["name"].lower() or q in s["description"].lower()]


@server.tool()
def get_mcp_server(name: str) -> dict:
    """Full registry entry for one MCP server (without credentials)."""
    s = catalog.services().get(name)
    return {k: v for k, v in s.items() if k != "auth_binding"} if s else {"error": f"'{name}' not registered"}


@server.tool()
def fetch_available_bindings(name: str) -> list[dict]:
    """Auth bindings available for a server: names and types only."""
    s = catalog.services().get(name)
    return [{"binding": s["auth_binding"], "type": "api_key"}] if s else []


if __name__ == "__main__":
    server.run("stdio")
