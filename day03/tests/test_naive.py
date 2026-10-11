"""The naive desk loses its prompt rules but keeps the same code-level limits."""
from desk_day3.agent import enforce_limits
from desk_naive.agent import executor, root_agent


def test_naive_desk_prompt_has_no_limits():
    text = root_agent.instruction.lower()
    assert "50" not in text and "watchlist" not in text


def test_naive_executor_still_enforces_hard_limits():
    assert executor.before_tool_callback is enforce_limits
