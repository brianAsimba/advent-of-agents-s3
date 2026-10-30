"""Day 23 demo: static vs live blast radius, SAFE/STOP verdicts, then the same question in plain English.

Run from the repo root (one short Claude run at the end):
  uv run python day23/demo.py
"""
import asyncio
import logging
import os
import sys
import warnings
from pathlib import Path

from dotenv import load_dotenv

warnings.filterwarnings("ignore", message=r"\[EXPERIMENTAL\]", category=UserWarning)
for name in ("google_adk", "mcp", "httpx", "LiteLLM"):
    logging.getLogger(name).setLevel(logging.CRITICAL)
HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")
sys.path.insert(0, str(HERE))

from google.adk.agents.llm_agent import Agent  # noqa: E402
from google.adk.models.lite_llm import LiteLlm  # noqa: E402
from google.adk.runners import InMemoryRunner  # noqa: E402
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams  # noqa: E402
from google.genai import types  # noqa: E402
from mcp import StdioServerParameters  # noqa: E402

import blast_radius as br  # noqa: E402
import topology as t  # noqa: E402


async def ask(question: str) -> str:
    tools = McpToolset(connection_params=StdioConnectionParams(server_params=StdioServerParameters(
        command=sys.executable, args=[str(HERE / "topology_mcp.py")]), timeout=30))
    agent = Agent(name="change_reviewer", model=LiteLlm(model="anthropic/claude-opus-5-5"), tools=[tools],
                  instruction=("You review proposed changes to MCP servers. Use the topology tools; never guess. "
                               "Answer in at most 5 short bullet points, naming teams to contact."))
    runner = InMemoryRunner(agent=agent, app_name="day23")
    s = await runner.session_service.create_session(app_name="day23", user_id="platform")
    answer = ""
    try:
        async for ev in runner.run_async(user_id="platform", session_id=s.id, new_message=types.Content(
                role="user", parts=[types.Part(text=question)])):
            for p in (ev.content.parts if ev.content else []) or []:
                if p.text and ev.author != "user":
                    answer = p.text
    finally:
        await tools.close()
    return answer


def main() -> None:
    g = t.build(t.load_estate(), t.sample_traffic())
    print("=== 1. Static vs live, for legacy-search-mcp ===")
    static = [p[-1][1].name for p in t.query(g, br.dependents_pattern("legacy-search-mcp"))]
    live = [p[1][1].name for p in t.query(g, br.callers_pattern("legacy-search-mcp"))]
    print(f"  registry says (DEPENDS_ON):      {sorted(static)}")
    print(f"  traces say (SENDS_TRAFFIC):      {sorted(live)}")
    print(f"  only in traces (shadow):         {sorted(set(live) - set(static))}")
    print(f"  only in registry (stale):        {sorted(set(static) - set(live))}")

    print("\n=== 2. Verdicts ===")
    for server in ("weather-mcp", "legacy-search-mcp", "crm-accounts-mcp"):
        print(br.report(br.blast_radius(g, server)) + "\n")

    print("=== 3. Plain English, through the topology MCP server ===")
    q = ("We want to retire legacy-search-mcp next Friday. Is that safe? Who do we need to talk to first, "
         "and is anything calling it that isn't registered?")
    print(f"  question: {q}\n")
    print("  " + asyncio.run(ask(q)).replace("\n", "\n  "))


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Missing ANTHROPIC_API_KEY: copy day23/.env.example to day23/.env")
    main()
