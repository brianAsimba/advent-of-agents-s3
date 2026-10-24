"""revenue_insights_agent on Claude. Its tools come from the registry by logical name: no paths, no URLs.
Every call goes through the gateway with this agent's own identity token (minted by the platform)."""
import sys
from pathlib import Path

from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_registry as registry  # noqa: E402

AGENT_NAME = "revenue-insights-agent"
MODEL = LiteLlm(model="anthropic/claude-opus-5-5")


def build(agent_name: str = AGENT_NAME) -> Agent:
    return Agent(
        name="revenue_insights_agent", model=MODEL,
        instruction=("You answer questions about customer KPIs and open data-quality tickets. Use the tools. "
                     "Be brief. If a tool returns PERMISSION_DENIED, say so plainly and don't retry."),
        tools=[registry.get_mcp_toolset("customer-analytics-mcp", agent_name)])
