"""Deterministic checks of the Day 3 architecture (no model calls, no API cost)."""
from types import SimpleNamespace

from desk_day3.agent import analyst, enforce_limits, executor, root_agent


def tool_names(agent):
    return {getattr(t, "name", None) or t.__name__ for t in agent.tools}


# Boundary 1: separation of duties
def test_analyst_cannot_place_orders():
    assert tool_names(analyst) == {"get_price", "get_news"}


def test_executor_cannot_read_news():
    assert tool_names(executor) == {"place_paper_order"}


def test_desk_holds_no_data_or_order_tools_directly():
    assert tool_names(root_agent) == {"analyst", "executor"}


# Hard limits: hold even if every model is fooled
ORDER = SimpleNamespace(name="place_paper_order")


def test_injected_order_is_rejected():
    out = enforce_limits(ORDER, {"ticker": "XYZ", "side": "buy", "shares": 10000}, None)
    assert out["status"] == "rejected"


def test_oversized_order_is_rejected():
    assert enforce_limits(ORDER, {"ticker": "NVDA", "side": "buy", "shares": 500}, None)["status"] == "rejected"


def test_short_sale_is_rejected():
    assert enforce_limits(ORDER, {"ticker": "PG", "side": "sell", "shares": 10}, None)["status"] == "rejected"


def test_valid_order_passes():
    assert enforce_limits(ORDER, {"ticker": "NVDA", "side": "buy", "shares": 20}, None) is None
