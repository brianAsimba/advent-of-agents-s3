"""Day 20 tests: mediation, Spike Arrest, body limit, REST->MCP translation, egress allowlist (no model calls)."""
import json

import httpx
import pytest
from starlette.testclient import TestClient

import billing_agent
import ingress_gateway as ig
import legacy_crm

H = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


@pytest.fixture
def fake_backend(monkeypatch):
    def get(url, timeout=10):
        cid = url.rsplit("/", 1)[-1]
        rec = legacy_crm.account(cid)
        return httpx.Response(200 if rec else 404, json=rec or {"error": "not found"})
    monkeypatch.setattr(ig.httpx, "get", get)


def call(i, cid="CUST-9921"):
    return {"jsonrpc": "2.0", "id": i, "method": "tools/call",
            "params": {"name": "lookup_customer_account", "arguments": {"customer_id": cid}}}


def client(app):
    return TestClient(app, base_url="http://127.0.0.1:8300")  # the MCP app rejects unknown Host headers


def test_mediation_keeps_only_agreed_fields():
    rec = legacy_crm.account("CUST-9921")
    lean = ig.mediate(rec)
    assert set(lean) == set(ig.KEEP) and len(json.dumps(rec)) > 100 * len(json.dumps(lean))


def test_spike_arrest_window_and_per_client():
    clock = Clock()
    sa = ig.SpikeArrest(rate=2, window=10, clock=clock)
    assert [sa.allow("a") for _ in range(3)] == [True, True, False]
    assert sa.allow("b")  # another client has its own budget
    clock.t = 10.0
    assert sa.allow("a")  # window passed


def test_rest_to_mcp_burst_and_discovery(fake_backend):
    app = ig.build_app("http://backend", arrest=ig.SpikeArrest(rate=2, window=10, clock=Clock()))
    with client(app) as c:
        codes = [c.post("/v1/mcp", json=call(i), headers={**H, "x-client-id": "loop"}).status_code for i in range(5)]
        assert codes == [200, 200, 429, 429, 429]
        r = c.post("/v1/mcp", json=call(9), headers={**H, "x-client-id": "loop"})
        assert r.headers["retry-after"] == "10" and r.json()["error"]["code"] == -32029
        listed = c.post("/v1/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, headers=H)
        assert listed.status_code == 200  # discovery isn't rate limited
        assert [t["name"] for t in listed.json()["result"]["tools"]] == ["lookup_customer_account"]


def test_tool_returns_lean_record_or_pass_through(fake_backend):
    for mediation, keys in ((True, set(ig.KEEP)), (False, None)):
        with client(ig.build_app("http://backend", mediation=mediation)) as c:
            text = c.post("/v1/mcp", json=call(1), headers=H).json()["result"]["content"][0]["text"]
            got = set(json.loads(text))
            assert got == keys if mediation else {"activity_log", "raw_xml"} <= got


def test_oversized_request_body_is_rejected():
    with client(ig.build_app("http://backend")) as c:
        big = {**call(1), "params": {"name": "lookup_customer_account", "arguments": {"customer_id": "x" * 20000}}}
        assert c.post("/v1/mcp", json=big, headers=H).status_code == 413


def test_egress_allows_only_governed_endpoints():
    billing_agent.egress_toolset("http://127.0.0.1:8300/v1/mcp", "t")
    with pytest.raises(billing_agent.EgressDenied, match="8301"):
        billing_agent.egress_toolset("http://127.0.0.1:8301/crm/v2/accounts", "t")
