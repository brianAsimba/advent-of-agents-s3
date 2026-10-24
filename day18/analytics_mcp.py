"""customer-analytics-mcp: a real MCP server (stdio) with three tools, one of them destructive. Fake data.

Course: a FastMCP server on GKE, labelled MCP_SERVER so it registers itself. Here: run as a subprocess
by whoever connects to it (the gateway). Nothing here checks permissions; that's the gateway's job.
"""
from mcp.server.mcpserver import MCPServer

KPIS = {"2026-Q3": {"revenue_usd": 1_240_000, "active_customers": 3_180, "churn_pct": 2.4},
        "2026-Q2": {"revenue_usd": 1_105_000, "active_customers": 3_020, "churn_pct": 2.9}}
TICKETS: list[dict] = []
CUSTOMERS = {"rows": 3180}

server = MCPServer("customer-analytics-mcp", version="1.0.0")


@server.tool()
def query_kpi_summary(quarter: str) -> dict:
    """Revenue, active customers and churn for a quarter such as '2026-Q3'."""
    return KPIS.get(quarter, {"error": f"no data for {quarter}"})


@server.tool()
def create_data_quality_ticket(table: str, issue: str) -> dict:
    """Opens a data-quality ticket for a table."""
    TICKETS.append({"table": table, "issue": issue})
    return {"ticket_id": f"DQ-{len(TICKETS):04d}", "status": "open"}


@server.tool()
def purge_customer_table(confirm: bool = False) -> dict:
    """DESTRUCTIVE: deletes every row in the customer table."""
    CUSTOMERS["rows"] = 0
    return {"deleted": True, "rows_left": 0}


if __name__ == "__main__":
    server.run("stdio")
