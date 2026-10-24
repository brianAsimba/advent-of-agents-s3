"""Day 20 demo: the ingress gateway (Apigee role) in front of a legacy REST CRM, plus the egress check.

Run from the repo root (a few cents of Claude usage):
  uv run python day20/demo.py
Starts: legacy CRM :8301, ingress gateway :8300 (Spike Arrest 2/10 s), and two gateways for the token
comparison: :8302 mediated, :8303 pass-through (rate 50). All stopped at the end.
"""
import asyncio
import logging
import os
import socket
import subprocess
import sys
import time
import warnings
from pathlib import Path

import httpx
from dotenv import load_dotenv

warnings.filterwarnings("ignore", message=r"\[EXPERIMENTAL\]", category=UserWarning)
for name in ("google_adk", "mcp", "google.auth", "httpx", "LiteLLM"):
    logging.getLogger(name).setLevel(logging.CRITICAL)
HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")
sys.path.insert(0, str(HERE))

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

import billing_agent  # noqa: E402

PY = sys.executable
H = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
GW, CRM = "http://127.0.0.1:8300/v1/mcp", "http://127.0.0.1:8301"


def start(*args) -> subprocess.Popen:
    p = subprocess.Popen([PY, *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    port = int(args[args.index("--port") + 1])
    for _ in range(80):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return p
        time.sleep(0.2)
    raise RuntimeError(f"port {port} did not open")


def rpc(i: int, method: str, params: dict, client: str = "curl") -> httpx.Response:
    return httpx.post(GW, json={"jsonrpc": "2.0", "id": i, "method": method, "params": params},
                      headers={**H, "x-client-id": client}, timeout=10)


def backend_calls() -> int:
    return httpx.get(f"{CRM}/_stats").json()["n"]


async def ask(agent, text: str) -> tuple[str, int]:
    runner = InMemoryRunner(agent=agent, app_name="day20")
    s = await runner.session_service.create_session(app_name="day20", user_id="ops")
    answer, prompt_tokens = "", 0
    try:
        async for ev in runner.run_async(user_id="ops", session_id=s.id,
                                         new_message=types.Content(role="user", parts=[types.Part(text=text)])):
            if ev.usage_metadata and ev.usage_metadata.prompt_token_count:
                prompt_tokens += ev.usage_metadata.prompt_token_count
            for p in (ev.content.parts if ev.content else []) or []:
                if p.text and ev.author != "user":
                    answer = p.text
    except Exception as e:
        answer = f"RUN FAILED: {type(e).__name__}: {str(e).splitlines()[0][:100]}"
    finally:
        for t in agent.tools:
            await t.close()
    return " ".join(answer.split())[:230], prompt_tokens


async def main() -> None:
    procs = [start(str(HERE / "legacy_crm.py"), "--port", "8301"),
             start(str(HERE / "ingress_gateway.py"), "--port", "8300", "--backend", CRM),
             start(str(HERE / "ingress_gateway.py"), "--port", "8302", "--backend", CRM, "--rate", "50"),
             start(str(HERE / "ingress_gateway.py"), "--port", "8303", "--backend", CRM, "--rate", "50", "--no-mediation")]
    try:
        print("=== 1. Discover: the legacy REST API is now an MCP tool (no backend rewrite) ===")
        tools = rpc(1, "tools/list", {}).json()["result"]["tools"]
        print("  tools/list ->", [t["name"] for t in tools])

        print("\n=== 2. Governed call: schema mediation ===")
        raw = len(httpx.get(f"{CRM}/crm/v2/accounts/CUST-9921").content)
        r = rpc(2, "tools/call", {"name": "lookup_customer_account", "arguments": {"customer_id": "CUST-9921"}})
        lean = len(r.json()["result"]["content"][0]["text"])
        print(f"  backend returns {raw:,} bytes; the agent receives {lean:,} bytes ({raw // lean}x smaller)")

        print("\n=== 3. Runaway loop: 5 rapid calls from one client (Spike Arrest 2 per 10 s) ===")
        before = backend_calls()
        for i in range(1, 6):
            r = rpc(10 + i, "tools/call", {"name": "lookup_customer_account",
                                           "arguments": {"customer_id": "CUST-9921"}}, client="looping-agent")
            print(f"  Request {i}: HTTP {r.status_code}")
        print(f"  RESULT: requests that reached the backend: {backend_calls() - before} of 5")

        print("\n=== 4. Context bloat, measured with Claude (same question, two gateways) ===")
        q = "What tier is customer CUST-9921 and how much do they owe?"
        for label, url in (("mediated   ", "http://127.0.0.1:8302/v1/mcp"), ("pass-through", "http://127.0.0.1:8303/v1/mcp")):
            ans, tok = await ask(billing_agent.build(url, client_id=f"bloat-{label.strip()}"), q)
            print(f"  {label}: {tok:>6,} prompt tokens -> {ans[:120]}")

        print("\n=== 5. Claude asks for five accounts through the rate-limited gateway ===")
        ans, _ = await ask(billing_agent.build(GW, client_id="billing-agent"),
                           "Give me the balance due for CUST-0001, CUST-0002, CUST-0003, CUST-0004 and CUST-0005.")
        print("  agent:", ans)

        print("\n=== 6. Egress: the agent tries to reach the backend directly, skipping the ingress gateway ===")
        try:
            billing_agent.build(f"{CRM}/crm/v2/accounts")
            print("  ALLOWED (this should not happen)")
        except billing_agent.EgressDenied as e:
            print(f"  {e}")
    finally:
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Missing ANTHROPIC_API_KEY: copy day20/.env.example to day20/.env")
    asyncio.run(main())
