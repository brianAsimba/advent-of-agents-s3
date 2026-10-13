"""Builds an ADK agent that holds its own identity token.

The token is minted when the agent starts and lives only inside the tool's closure:
the model never sees it and can't hand it to another agent.
"""
from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm

import iam_lib

MODEL = LiteLlm(model="anthropic/claude-opus-5-5")


def build_agent(name: str, purpose: str) -> Agent:
    token = iam_lib.mint(name)

    def query_weather_data(sql: str) -> dict:
        """Runs a read-only SQL query on the sample_data warehouse.

        Table: cities_weather(city TEXT, state TEXT, temp_f INTEGER, condition TEXT).

        Args:
            sql: A single SELECT statement.
        """
        return iam_lib.run_query(token, sql)

    def whoami() -> dict:
        """Returns this agent's own identity (its SPIFFE ID)."""
        return {"identity": iam_lib.verify(token)}

    return Agent(
        model=MODEL,
        name=name,
        description=purpose,
        instruction=(
            f"{purpose} Use query_weather_data to read the cities_weather table. "
            "If access is denied, say so plainly and quote the error; do not guess the data."
        ),
        tools=[query_weather_data, whoami],
    )
