"""Day 18 tests: registration, search, overlap, gateway allowlist over real MCP stdio (no model calls)."""
import asyncio
import inspect
import json

import pytest
from mcp import ClientSession
from mcp.client.stdio import stdio_client

import revenue_agent as agent
import mcp_gateway as gateway
import agent_registry as registry


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("ISSUER_SECRET", "test-secret")
    monkeypatch.setenv("DAY18_STORE", str(tmp_path))  # for the gateway subprocess
    monkeypatch.setattr(registry, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(gateway, "AUDIT_FILE", tmp_path / "gateway_audit.jsonl")
    asyncio.run(registry.register_mcp("customer-analytics-mcp", ["analytics_mcp.py"], "data-platform", "KPIs"))
    return tmp_path


async def _through_gateway(agent_name, calls, token=None):
    params = registry.gateway_params("customer-analytics-mcp", agent_name)
    if token is not None:
        params.env["AGENT_TOKEN"] = token
    out = {}
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            out["list"] = [t.name for t in (await s.list_tools()).tools]
            for name, args in calls:
                res = await s.call_tool(name, args)
                out[name] = (res.is_error, res.content[0].text)
    return out


def test_registration_introspects_tool_schemas():
    tools = {t["name"]: t for t in registry.get("customer-analytics-mcp")["tools"]}
    assert set(tools) == {"query_kpi_summary", "create_data_quality_ticket", "purge_customer_table"}
    assert tools["query_kpi_summary"]["input_schema"]["required"] == ["quarter"]


def test_search_and_unknown_name():
    assert registry.search("churn")[0]["tool"] == "query_kpi_summary"
    with pytest.raises(KeyError):
        registry.get("no-such-server")


def test_lookalike_server_is_flagged():
    d = asyncio.run(registry.register_mcp("sales-kpi-mcp", ["sales_kpi_mcp.py"], "sales-ops", "Sales KPIs"))
    assert d["overlaps"] == ["get_revenue_summary looks like customer-analytics-mcp/query_kpi_summary"]


def test_agent_code_has_no_paths_or_urls():
    src = inspect.getsource(agent)
    assert "customer-analytics-mcp" in src and "analytics_mcp.py" not in src and "http" not in src


def test_gateway_allows_listed_tools_and_denies_the_rest(store):
    out = asyncio.run(_through_gateway("revenue-insights-agent",
                                       [("query_kpi_summary", {"quarter": "2026-Q3"}), ("purge_customer_table", {})]))
    assert "purge_customer_table" in out["list"]  # discovery allowed (rule 1)
    assert out["query_kpi_summary"][0] is False and "1240000" in out["query_kpi_summary"][1]
    assert out["purge_customer_table"] == (True, "403 PERMISSION_DENIED by Agent Gateway: tool not on this agent's allowlist")
    audit = [json.loads(x) for x in (store / "gateway_audit.jsonl").read_text().splitlines()]
    assert [(a["tool"], a["allowed"]) for a in audit if a["method"] == "tools/call"] == [
        ("query_kpi_summary", True), ("purge_customer_table", False)]


def test_other_agent_and_forged_token_get_nothing():
    other = asyncio.run(_through_gateway("intern-agent", [("query_kpi_summary", {"quarter": "2026-Q3"})]))
    assert other["query_kpi_summary"][0] is True
    forged = asyncio.run(_through_gateway("revenue-insights-agent", [("query_kpi_summary", {"quarter": "2026-Q3"})],
                                          token="forged.token"))
    assert forged["list"] == [] and "identity rejected" in forged["query_kpi_summary"][1]
