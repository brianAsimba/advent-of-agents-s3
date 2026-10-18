"""Day 13 demo: what model-written code can reach on your PC vs in a sandbox, then a stateful sandbox session.

Run from the repo root (a few cents of Claude usage plus a little code-execution container time):
  uv run python day13/demo.py
"""
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")
sys.path.insert(0, str(HERE))

import sandbox  # noqa: E402
from probe import PROBE  # noqa: E402


def show(runs):
    for r in runs:
        code = (r["code"] or "").strip().splitlines()
        print(f"    ran: {code[0][:90] if code else '?'}{' …' if len(code) > 1 else ''}")
        for line in (r["stdout"] or r["stderr"] or str(r["error"])).strip().splitlines():
            print(f"      | {line}")


def main() -> None:
    print("=== 1. The same 'what can I reach?' code, run directly on YOUR PC (the unsafe way) ===")
    out = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True, env=os.environ, timeout=30)
    for line in out.stdout.strip().splitlines():
        print(f"      | {line}")

    print("\n=== 2. The same code, run by Claude in Anthropic's code execution sandbox ===")
    s = sandbox.Session()
    _, runs = sandbox.ask(s, "Run exactly this Python code, unmodified, and show its output:\n```python\n" + PROBE + "\n```")
    show(runs)

    print("\n=== 3. Stateful sandbox: three turns, one container; state kept in the container's files ===")
    m = sandbox.Session()
    for q in ["What is the monthly payment on a 450000 dollar, 30-year mortgage at 6.375% APR? "
              "Use Python in the sandbox, and save P (principal), r (monthly rate), n (payments) and M (payment) "
              "to /tmp/mortgage_state.json so later turns can reuse them.",
              "Load P, r, n and M from /tmp/mortgage_state.json in the sandbox (do not recompute them) and "
              "compute the total interest paid.",
              "In the sandbox, list the files in /tmp and print the contents of /tmp/mortgage_state.json."]:
        answer, runs = sandbox.ask(m, q)
        print(f"\n  Q: {q[:100]}{'…' if len(q) > 100 else ''}")
        show(runs)
        print(f"    container: {m.container_id}  (expires {m.container_expires})")
        print(f"    A: {' '.join(answer.split())[:200]}")
    print("\n  Expected: payment $2,807.41; total interest ≈ $560,669 (the course's numbers).")


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Missing ANTHROPIC_API_KEY: copy day13/.env.example to day13/.env")
    main()
