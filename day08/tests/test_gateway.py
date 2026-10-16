"""Day 8 gateway policy tests (no model calls)."""
import pytest

import agents
import gateway
import iam_lib

SUPPORT = "spiffe://brian.local/agents/support_agent"
REFUNDS = "spiffe://brian.local/agents/refunds_agent"


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setenv("ISSUER_SECRET", "test-secret")
    gateway.AUDIT.clear(); gateway.BACKEND_CALLS.clear()


def test_read_tool_allowed():
    assert gateway.decide(SUPPORT, "orders-mcp", "lookup_order")[0] == "ALLOW"


def test_delete_denied_for_every_agent():
    assert gateway.decide(SUPPORT, "orders-mcp", "delete_account")[0] == "DENY"
    assert gateway.decide(REFUNDS, "orders-mcp", "delete_account")[0] == "DENY"


def test_refund_depends_on_identity():
    assert gateway.decide(SUPPORT, "orders-mcp", "issue_refund")[0] == "DENY"
    assert gateway.decide(REFUNDS, "orders-mcp", "issue_refund")[0] == "ALLOW"


def test_unregistered_destination_is_default_denied():
    verdict, reason = gateway.decide(SUPPORT, "https://collector.example/upload", "http_post")
    assert verdict == "DENY" and "default deny" in reason


def test_deny_wins_over_allow():
    # issue_refund on a registered server matches the ALLOW rule too; DENY is evaluated first.
    assert gateway.decide(SUPPORT, "orders-mcp", "issue_refund")[1] == "The support agent may not move money"


def test_blocked_calls_never_reach_the_backend():
    tools = {t.__name__: t for t in agents.support_agent().tools}
    assert tools["delete_account"]("C-77")["status"] == 403
    assert tools["issue_refund"]("O-1001", 500)["status"] == 403
    assert tools["lookup_order"]("O-1001")["status"] == 200
    assert gateway.BACKEND_CALLS == ["lookup_order"]


def test_forged_identity_is_denied():
    out = gateway.call("not-a-token", "orders-mcp", "lookup_order", {"order_id": "O-1001"})
    assert out["status"] == 403 and gateway.BACKEND_CALLS == []
