"""Day 19 demo: tools resolved at runtime through the registry, credentials bound centrally, results screened.

Run from the repo root (a few cents of Claude usage):
  uv run python day19/demo.py
Starts two local release-notes servers (v1 on 8191, v2 on 8192) and stops them at the end.
"""
import asyncio
import logging
import os
import socket
import subprocess
import sys
import tempfile
import time
import warnings
from pathlib import Path

from dotenv import load_dotenv

warnings.filterwarnings("ignore", message=r"\[EXPERIMENTAL\]", category=UserWarning)
for name in ("google_adk", "mcp", "google.auth", "httpx"):  # their tracebacks drown the demo; outcomes are checked below
    logging.getLogger(name).setLevel(logging.CRITICAL)
HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")
os.environ["DAY19_STATE"] = tempfile.mkdtemp(prefix="day19-")  # fresh registry + credential store per run
sys.path.insert(0, str(HERE))

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

import catalog  # noqa: E402
import platform_tools as pt  # noqa: E402

V1, V2 = 8191, 8192
SERVICE, BINDING = "release-notes-mcp", "release-notes-api-key"


def start(port: int, version: str) -> subprocess.Popen:
    p = subprocess.Popen([sys.executable, str(HERE / "release_mcp.py"), "--port", str(port), "--version", version],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return p
        time.sleep(0.2)
    raise RuntimeError(f"server on {port} did not start")


async def ask(agent, text: str) -> str:
    runner = InMemoryRunner(agent=agent, app_name="day19")
    s = await runner.session_service.create_session(app_name="day19", user_id="auditor")
    answer = ""
    try:
        async for ev in runner.run_async(user_id="auditor", session_id=s.id,
                                         new_message=types.Content(role="user", parts=[types.Part(text=text)])):
            for p in (ev.content.parts if ev.content else []) or []:
                if p.text and ev.author != "user":
                    answer = p.text
    except Exception as e:  # a dead endpoint or a rejected key surfaces here
        return f"FAILED: {type(e).__name__}: {str(e).splitlines()[0][:110]}"
    finally:
        for t in agent.tools:
            await t.close()
    return " ".join(answer.split())[:220]


async def tools_load(agent) -> str:
    """Checked by code, because ADK will otherwise start the agent with NO tools and only log a warning."""
    ctx = type("Ctx", (), {"state": {}, "user_id": "auditor"})()
    try:
        names = [t.name for t in await agent.tools[0].get_tools(ctx)]
        return f"tools loaded: {names}"
    except Exception as e:
        return f"TOOLS FAILED TO LOAD ({str(e).split(': ')[-1][:60]}); the agent would run without them"


async def hardcoded(text: str) -> None:
    probe = pt.hardcoded_agent()
    status = await tools_load(probe)
    await probe.tools[0].close()
    print(f"  hardcoded: {pt.HARDCODED_URL}: {status}")
    print(f"             -> {await ask(pt.hardcoded_agent(), text)}")


async def governed(text: str) -> None:
    try:
        agent, target = await pt.governed_agent("release")
    except pt.Unresolvable as e:
        print(f"  governed : NOT STARTED (fails closed): {e}")
        return
    print(f"  governed : resolved {target['name']} v{target['version']} at {target['url']}")
    print(f"             -> {await ask(agent, text)}")


async def main() -> None:
    q = "What changed in release 1.3.2?"
    v1 = start(V1, "1.3.2")
    v2 = start(V2, "1.3.3")
    try:
        catalog.bind_credential(BINDING)
        catalog.register_service(SERVICE, f"http://127.0.0.1:{V1}/mcp", "1.3.2", "Product release notes", BINDING)
        os.environ["RELEASE_API_KEY"] = catalog.credential(BINDING)  # the anti-pattern: a copy of the key in .env

        print("=== 1. Both agents work on day one ===")
        await governed(q)
        await hardcoded(q)

        print("\n=== 2. Security patch: v1 is vulnerable. Platform moves the service to v2 and rotates the key ===")
        catalog.update_endpoint(SERVICE, f"http://127.0.0.1:{V2}/mcp", "1.3.3")
        catalog.bind_credential(BINDING)  # rotation: new value, same binding name
        v1.terminate()
        await governed(q)
        await hardcoded(q)

        print("\n=== 3. Inline screening of tool results ===")
        start_log = len(pt.SCREEN_LOG)
        await governed("Show me the release notes for 1.4.0.")
        blocked = [e for e in pt.SCREEN_LOG[start_log:] if e["action"] == "BLOCK"]
        print(f"  RESULT: tool results blocked by screening: {len(blocked)}"
              + (f" ({blocked[0]['reason']})" if blocked else ""))

        print("\n=== 4. The integration is compromised: platform revokes it in the registry ===")
        catalog.revoke(SERVICE)
        await governed(q)
    finally:
        for p in (v1, v2):
            p.terminate()


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Missing ANTHROPIC_API_KEY: copy day19/.env.example to day19/.env")
    asyncio.run(main())
