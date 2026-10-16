"""Day 7 demo: a 2 AM job acting for alice while she sleeps.

Run from the repo root (a few cents of Claude usage):
  uv run python day07/demo.py
"""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")
sys.path.insert(0, str(HERE))

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

import overnight  # noqa: E402
import reports_api  # noqa: E402
import vault  # noqa: E402


async def run_job(runner: InMemoryRunner, user: str) -> None:
    """What the 2:00 AM scheduler does: start a session for a user and send one message."""
    session = await runner.session_service.create_session(app_name=runner.app_name, user_id=user)
    msg = types.Content(role="user", parts=[types.Part(text="Generate my overnight incident summary.")])
    got, answer = None, ""
    async for ev in runner.run_async(user_id=user, session_id=session.id, new_message=msg):
        for p in (ev.content.parts if ev.content else []) or []:
            if p.function_response:
                r = p.function_response.response or {}
                got = [x["id"] for x in r.get("reports", [])] or r.get("status")
            elif p.text and ev.author != "user":
                answer = p.text
    print(f"    data received : {got}")
    print(f"    briefing      : {' '.join(answer.split())[:260]}")


def show_vault(user: str) -> None:
    print(f"    vault versions for refresh-token-{user}: {vault.versions(f'refresh-token-{user}')}")


async def main() -> None:
    runner = InMemoryRunner(agent=overnight.build_overnight_agent(), app_name="overnight")

    print("\n=== 1. 2:00 AM job for alice, but she never granted offline access ===")
    await run_job(runner, "alice")

    print("\n=== 2. Daytime: alice is online and consents ONCE with offline_access ===")
    tokens = reports_api.authorize("alice", ["reports:read", "offline_access"])
    vault.add_version("refresh-token-alice", tokens["refresh_token"])
    stolen_copy = tokens["refresh_token"]  # pretend an attacker copies this today
    show_vault("alice")

    print("\n=== 3. 2:00 AM job runs again: nobody is awake ===")
    await run_job(runner, "alice")
    show_vault("alice")

    print("\n=== 4. The next night: rotation again ===")
    await run_job(runner, "alice")
    show_vault("alice")

    print("\n=== 5. An attacker replays the refresh token copied on day 1 ===")
    print(f"    attacker gets: {reports_api.refresh(stolen_copy)}")

    print("\n=== 6. Night 3: the job now fails closed (the token family was revoked) ===")
    await run_job(runner, "alice")

    print("\n=== Vault audit (agent identity on every read) ===")
    for e in vault.AUDIT:
        print(f"    {e['ts']}  {e['event']:<20} agent={e.get('agent', '-').rsplit('/', 1)[-1]}  "
              f"secret={e.get('secret', '-')}  version={e.get('version', '-')}")


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Missing ANTHROPIC_API_KEY: copy day07/.env.example to day07/.env")
    asyncio.run(main())
