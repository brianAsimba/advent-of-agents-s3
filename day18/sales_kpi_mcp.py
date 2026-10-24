"""A second team's new MCP server that duplicates an existing tool. Registering it shows the overlap warning."""
from mcp.server.mcpserver import MCPServer

server = MCPServer("sales-kpi-mcp", version="0.1.0")


@server.tool()
def get_revenue_summary(quarter: str) -> dict:
    """Revenue, active customers and churn for a sales quarter."""
    return {"revenue_usd": None, "note": "work in progress"}


if __name__ == "__main__":
    server.run("stdio")
