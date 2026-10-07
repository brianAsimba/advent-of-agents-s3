"""Deterministic tests for the Day 1 tools (no model calls, no API cost)."""
from adlc_day1.agent import get_current_time, get_weather, root_agent


def test_weather_known_city():
    out = get_weather("San Francisco")
    assert out["status"] == "success"
    assert "San Francisco" in out["report"]


def test_weather_unknown_city_is_error():
    assert get_weather("Atlantis")["status"] == "error"


def test_time_known_city():
    out = get_current_time("detroit")
    assert out["status"] == "success"
    assert "Detroit" in out["report"]


def test_agent_only_has_spec_tools():
    # DESIGN_SPEC: "May not: call any other tool"
    names = sorted(t.__name__ for t in root_agent.tools)
    assert names == ["get_current_time", "get_weather"]
