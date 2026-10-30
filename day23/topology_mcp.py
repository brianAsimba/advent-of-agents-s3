"""Day 23 step 3: the topology as a read-only MCP server (course: https://apptopology.googleapis.com/mcp),
so an agent can check impact before it changes anything. Tools never modify the graph."""
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blast_radius as br  # noqa: E402
import topology as t  # noqa: E402

server = MCPServer("app-topology", version="1.0.0")
_GRAPH = t.build(t.load_estate(), t.sample_traffic())


@server.tool()
def list_mcp_servers() -> list[dict]:
    """All MCP servers in the topology with their owning team."""
    return [{"name": n.name, "owner": n.owner} for n in _GRAPH.nodes.values() if n.type == "MCPServer"]


EDGE_MODEL = ("Edges: Agent -DEPENDS_ON-> Binding -DEPENDS_ON-> MCPServer (declared), and "
              "Agent -Observability/SENDS_TRAFFIC-> MCPServer (live, from traces). Agents never DEPEND_ON a server "
              "directly: from a server, go FROM to Binding, then FROM to Agent.")


@server.tool(description=(
    "Runs a topology pattern: {\"start\": {\"type\": \"MCPServer\"|\"Agent\"|\"Binding\", \"name\": ...}, "
    "\"hops\": [{\"label\": \"DEPENDS_ON\"|\"Observability/SENDS_TRAFFIC\", \"direction\": \"FROM\" (who points "
    "at me) or \"TO\", \"types\": [...]}]}. " + EDGE_MODEL + " Returns matching paths and a count."))
def generate_resources_graph(pattern: dict) -> dict:
    try:
        paths = t.query(_GRAPH, pattern)
    except (LookupError, KeyError, TypeError) as e:
        return {"count": 0, "paths": [], "error": str(e), "hint": EDGE_MODEL}
    out = {"count": len(paths),
           "paths": [" <- ".join([f"{p[0].type}:{p[0].name}"] + [f"{n.type}:{n.name}" for _, n in p[1:]])
                     if pattern["hops"] and pattern["hops"][0]["direction"] == "FROM" else
                     " -> ".join([f"{p[0].type}:{p[0].name}"] + [f"{n.type}:{n.name}" for _, n in p[1:]])
                     for p in paths]}
    if not paths:
        out["hint"] = "No path matched. " + EDGE_MODEL  # an empty list alone tells a model nothing
    return out


@server.tool()
def blast_radius(mcp_server: str) -> dict:
    """Registered dependents and live callers (24 h: calls, error rate, p95) of one MCP server, with a
    SAFE/STOP verdict and the owners to contact."""
    try:
        return br.blast_radius(_GRAPH, mcp_server)
    except LookupError as e:
        return {"error": str(e)}


if __name__ == "__main__":
    server.run("stdio")
