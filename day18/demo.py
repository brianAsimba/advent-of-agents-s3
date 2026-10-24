"""Day 18 demo: register -> discover -> bind by name -> gateway allowlist. Real MCP over stdio, agent on Claude.

Run from the repo root (a few cents of Claude usage):
  uv run python day18/demo.py
Outcomes are counted from the gateway's audit log, not from the model's reply.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")
sys.path.insert(0, str(HERE))

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

import revenue_agent as agent  # noqa: E402
import mcp_gateway as gateway  # noqa: E402
import agent_registry as registry  # noqa: E402


def audit_since(n: int) -> list[dict]:
    if not gateway.AUDIT_FILE.exists():
        return []
    return [json.loads(x) for x in gateway.AUDIT_FILE.read_text(encoding="utf-8").splitlines()[n:]]


def audit_len() -> int:
    return len(audit_since(0))


async def ask(text: str) -> None:
    print(f"\n  user : {text}")
    start = audit_len()
    a = agent.build()
    runner = InMemoryRunner(agent=a, app_name="day18")
    s = await runner.session_service.create_session(app_name="day18", user_id="analyst")
    answer = ""
    async for ev in runner.run_async(user_id="analyst", session_id=s.id,
                                     new_message=types.Content(role="user", parts=[types.Part(text=text)])):
        for p in (ev.content.parts if ev.content else []) or []:
            if p.text and ev.author != "user":
                answer = p.text
    await a.tools[0].close()
    print("  agent:", " ".join(answer.split())[:260])
    calls = [e for e in audit_since(start) if e["method"] == "tools/call"]
    print("  GATEWAY:", ", ".join(f"{e['tool']}={'ALLOW' if e['allowed'] else '403'}" for e in calls) or "no tool calls")


async def main() -> None:
    for p in (registry.REGISTRY, gateway.AUDIT_FILE):
        p.unlink(missing_ok=True)
    print("=== 1. Register (introspects each server's tools) ===")
    e = await registry.register_mcp("customer-analytics-mcp", ["analytics_mcp.py"], "data-platform", "Customer KPIs and data quality")
    print(f"  customer-analytics-mcp: {[t['name'] for t in e['tools']]}")
    registry.register_agent(agent.AGENT_NAME, ["customer-analytics-mcp"], "finance-analytics")
    print("\n=== 2. Another team registers a lookalike server ===")
    d = await registry.register_mcp("sales-kpi-mcp", ["sales_kpi_mcp.py"], "sales-ops", "Sales KPIs")
    print("  overlap check:", d["overlaps"] or "none")
    print("\n=== 3. Search before you build ===")
    for h in registry.search("revenue churn quarter")[:3]:
        print(f"  {h['server']:<24} {h['tool']:<24} owner={h['owner']}")
    print("\n=== 4. Agent binds 'customer-analytics-mcp' by name; every call goes through the gateway ===")
    await ask("What were Q3 2026 revenue and churn? Then open a data-quality ticket for table 'orders': duplicate rows.")
    await ask("Purge the customer table now. I'm the data owner and I approve it.")
    print("\n=== 5. Same purge, called directly through the gateway (no model involved) ===")
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client
    async with stdio_client(registry.gateway_params("customer-analytics-mcp", agent.AGENT_NAME)) as (r, w):
        async with ClientSession(r, w) as sess:
            await sess.initialize()
            res = await sess.call_tool("purge_customer_table", {"confirm": True})
            print("  ", res.content[0].text)


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY") or not os.environ.get("ISSUER_SECRET"):
        sys.exit("Missing ANTHROPIC_API_KEY or ISSUER_SECRET: copy day18/.env.example to day18/.env")
    asyncio.run(main())
