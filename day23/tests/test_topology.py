"""Day 23 tests: graph, pattern queries, blast radius, verdicts, MCP tool hints (no model calls)."""
import pytest

import blast_radius as br
import topology as t
import topology_mcp


@pytest.fixture
def g():
    return t.build(t.load_estate(), t.sample_traffic())


def test_static_and_live_queries(g):
    deps = sorted(p[-1][1].name for p in t.query(g, br.dependents_pattern("legacy-search-mcp")))
    live = sorted(p[1][1].name for p in t.query(g, br.callers_pattern("legacy-search-mcp")))
    assert deps == ["revenue-insights-agent", "support-concierge"]
    assert live == ["nightly-report-job", "support-concierge"]


def test_direction_matters(g):
    to = {"start": {"type": "Agent", "name": "billing-agent"},
          "hops": [{"label": t.DEPENDS_ON, "direction": "TO", "types": ["Binding"]},
                   {"label": t.DEPENDS_ON, "direction": "TO", "types": ["MCPServer"]}]}
    assert [p[-1][1].name for p in t.query(g, to)] == ["crm-accounts-mcp"]
    wrong = {"start": {"type": "MCPServer", "name": "crm-accounts-mcp"},
             "hops": [{"label": t.DEPENDS_ON, "direction": "TO", "types": ["Binding"]}]}
    assert t.query(g, wrong) == []


def test_blast_radius_classifies_shadow_and_stale(g):
    r = br.blast_radius(g, "legacy-search-mcp")
    kinds = {row["agent"]: row["kind"] for row in r["rows"]}
    assert kinds == {"nightly-report-job": "SHADOW (live, no binding)",
                     "revenue-insights-agent": "stale binding (no traffic)",
                     "support-concierge": "registered + live"}
    assert r["verdict"] == "STOP" and r["contact"] == ["cx-team", "data-eng", "finance-analytics"]


def test_live_edge_metrics(g):
    row = next(x for x in br.blast_radius(g, "crm-accounts-mcp")["rows"] if x["agent"] == "billing-agent")
    assert row["calls"] == 410 and 0 <= row["error_rate"] < 0.1 and row["p95_ms"] > 0


def test_unregistered_caller_appears_even_if_unknown_to_the_estate():
    spans = [{"name": "x", "start_ns": 0, "end_ns": 1_000_000, "status": "UNSET",
              "attributes": {"gen_ai.operation.name": "execute_tool", "gen_ai.agent.name": "mystery-bot",
                             "mcp.server.name": "weather-mcp"}}]
    r = br.blast_radius(t.build(t.load_estate(), spans), "weather-mcp")
    assert r["verdict"] == "STOP" and r["rows"][0]["agent"] == "mystery-bot" and r["rows"][0]["owner"] == "unknown"


def test_exit_codes(capsys):
    assert br.main(["weather-mcp"]) == 0
    assert br.main(["legacy-search-mcp"]) == 1
    assert br.main(["no-such-mcp"]) == 2


def test_p95():
    assert t._p95([float(i) for i in range(1, 101)]) == 95.0


def test_mcp_tool_explains_empty_results():
    empty = topology_mcp.generate_resources_graph({"start": {"type": "MCPServer", "name": "legacy-search-mcp"},
                                                   "hops": [{"label": "DEPENDS_ON", "direction": "FROM",
                                                             "types": ["Agent"]}]})
    assert empty["count"] == 0 and "Binding" in empty["hint"]
    bad = topology_mcp.generate_resources_graph({"start": {"type": "MCPServer", "name": "nope"}, "hops": []})
    assert "not found" in bad["error"]
    ok = topology_mcp.generate_resources_graph(br.dependents_pattern("legacy-search-mcp"))
    assert ok["count"] == 2 and all("<-" in p for p in ok["paths"])
