"""Day 16 demo: CineAgent on Claude books tickets; paying needs an approval card and signed mandates.

Run from the repo root (a few cents of Claude usage). Test money only: the merchants are local fakes.
  uv run python day16/demo.py                 scripted: approve scene 1, decline scene 2
  uv run python day16/demo.py --interactive   you answer the approval cards yourself
What was charged is read from the merchants' own records, not from the model's reply.
"""
import argparse
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

import cineagent  # noqa: E402

CONFIRM = "adk_request_confirmation"


def charged() -> int:
    return sum(s["total_cents"] for shop in cineagent.MERCHANTS.values()
               for cid, s in shop.sessions.items() if cid in shop.completed)


async def scene(title: str, prompt: str, approve: bool | None, interactive: bool) -> None:
    print(f"\n=== {title} ===\n  user : {prompt}")
    before, log_start = charged(), len(cineagent.LOG)
    runner = InMemoryRunner(agent=cineagent.build(), app_name="day16")
    s = await runner.session_service.create_session(app_name="day16", user_id="brian")
    msg = types.Content(role="user", parts=[types.Part(text=prompt)])
    cards, said_yes = 0, False
    while msg is not None:
        pending, answer = None, ""
        async for ev in runner.run_async(user_id="brian", session_id=s.id, new_message=msg):
            for p in (ev.content.parts if ev.content else []) or []:
                if p.function_call and p.function_call.name == CONFIRM:
                    pending = p.function_call
                elif p.text and ev.author != "user":
                    answer = p.text
        if answer:
            print("  agent:", " ".join(answer.split())[:240])
        msg = None
        if not pending and not said_yes and "?" in answer:
            # A "yes" in chat is only the user's words. It is NOT the approval: the card below still is.
            said_yes = True
            print("  user : Yes, go ahead and pay.")
            msg = types.Content(role="user", parts=[types.Part(text="Yes, go ahead and pay.")])
        elif pending:
            cards += 1
            orig = (pending.args or {}).get("originalFunctionCall", {})
            args = orig.get("args", {})
            print(f"  ┌ APPROVAL CARD: {orig.get('name')}  checkout {args.get('checkout_id')}  "
                  f"total ${int(args.get('total_cents', 0)) / 100:.2f}")
            ok = (input("  └ Approve? [y/N] ").strip().lower() == "y") if interactive else bool(approve)
            if not interactive:
                print(f"  └ {'Approve' if ok else 'Decline'} (scripted)")
            msg = types.Content(role="user", parts=[types.Part(function_response=types.FunctionResponse(
                id=pending.id, name=CONFIRM, response={"confirmed": ok}))])
    blocked = [f"{e['layer']}" for e in cineagent.LOG[log_start:] if not e["allowed"]]
    print(f"  RESULT: approval cards shown: {cards}; charged by merchants: ${(charged() - before) / 100:.2f}; "
          f"blocked by: {', '.join(blocked) or 'nothing'}")


async def main(interactive: bool) -> None:
    cineagent.reset()
    await scene("1. Book and approve", "Book 2 standard tickets for Oppenheimer at 9:30 PM at Meridian.", True, interactive)
    await scene("2. Book and decline", "Book 2 standard tickets for Oppenheimer at 9:30 PM at Meridian.", False, interactive)
    await scene("3. Over the spend cap", "Book 4 IMAX tickets for Oppenheimer at 9:30 PM at Meridian.", True, interactive)
    await scene("4. Merchant not on the allowlist", "Book 2 standard tickets for Oppenheimer at 9:30 PM at StarLight.",
                True, interactive)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--interactive", action="store_true")
    a = ap.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Missing ANTHROPIC_API_KEY: copy day16/.env.example to day16/.env")
    asyncio.run(main(a.interactive))
