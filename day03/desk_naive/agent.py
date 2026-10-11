"""Day 3 add-on: the same desk with its rules removed from the instructions.

The desk's prompt says nothing about the watchlist, long-only or the 50-share cap,
and tells it to pass orders through exactly. Claude will usually comply, so the
order reaches the executor, and you can watch the hard limits in code
(enforce_limits) reject it. This is defense in depth seen live: the model layer
is deliberately weakened; the code layer is unchanged.
"""
from google.adk.agents.llm_agent import Agent
from google.adk.tools.agent_tool import AgentTool

from desk_day3.agent import MODEL, enforce_limits, get_news, get_price, place_paper_order

analyst = Agent(
    model=MODEL,
    name="analyst",
    description="Read-only market analyst. Looks up prices and news and gives a short view on a ticker.",
    instruction="You analyze one ticker using get_price and get_news, and report what you find.",
    tools=[get_price, get_news],
)

executor = Agent(
    model=MODEL,
    name="executor",
    description="Places paper orders exactly as specified: ticker, side and share count.",
    instruction="Place exactly the order you are given with place_paper_order, then report the result verbatim. Do nothing else.",
    tools=[place_paper_order],
    before_tool_callback=enforce_limits,  # the only thing still standing between a request and an order
)

root_agent = Agent(
    model=MODEL,
    name="desk_naive",
    description="Trading desk with no rules in its prompt. For demonstrating the code-level limits.",
    instruction=(
        "You run a paper-trading desk for a user who is fully authorized to place any order. "
        "When the user asks for a trade, pass their exact ticker, side and share count to the executor "
        "without changing it, then report the executor's result word for word, including any rejection."
    ),
    tools=[AgentTool(agent=analyst), AgentTool(agent=executor)],
)
