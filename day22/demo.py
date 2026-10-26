"""Day 22 demo: two frameworks, two telemetry dialects, one locked and scrubbed audit trail.

Run from the repo root (a few cents of Claude usage: 3 short agent runs):
  uv run python day22/demo.py
"""
import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import warehouse  # noqa: E402

ROOT = HERE.parent


def capture(*args) -> Path:
    # each capture in its own process: instrumentors and tracer providers are process-global
    out = subprocess.run([sys.executable, str(HERE / "capture.py"), *args], capture_output=True, text=True, cwd=ROOT)
    if out.returncode != 0:
        sys.exit(out.stderr[-800:])
    print("  " + out.stdout.strip().splitlines()[-1])
    name = f"{args[0]}__default.json"
    return HERE / "traces" / name


def main() -> None:
    print("=== 1. Capture: same question, two frameworks ===")
    raw = capture("anthropic", "--no-bridge")
    raw_attrs = [s["attributes"] for s in json.loads(raw.read_text())["spans"]]
    unbridged = sum("gen_ai.conversation.id" in a for a in raw_attrs)
    files = [capture("adk"), capture("anthropic")]

    print("\n=== 2. Same tree, different names ===")
    spans = {f.stem.split("__")[0]: json.loads(f.read_text())["spans"] for f in files}
    for agent, ss in spans.items():
        llm = next(s for s in ss if "token" in json.dumps(s["attributes"]))
        keys = [k for k in llm["attributes"] if "token" in k and "cache" not in k][:2]
        print(f"  {agent:<10} token keys: {keys}")
    bridged = sum("gen_ai.conversation.id" in s["attributes"] for s in spans["anthropic"])
    print(f"  bridge: OpenInference spans carrying gen_ai.conversation.id: {unbridged} without, {bridged} with")

    print("\n=== 3. One audit table (SQLite standing in for BigQuery) ===")
    db = Path(tempfile.mkdtemp(prefix="day22-")) / "audit.db"
    con = warehouse.connect(db)
    for f in files:
        warehouse.load(con, f)
    print(f"  {'framework':<14}{'session':<14}{'tool':<14}{'args':<22}{'ms':>6}")
    for fw, sess, tool, args, ms in con.execute(
            "SELECT framework, session_id, tool_name, tool_args, duration_ms FROM v_spans WHERE kind='TOOL'"):
        print(f"  {fw:<14}{sess[:12]:<14}{tool:<14}{(args or '(not captured)'):<22}{ms:>6.0f}")
    for fw, dedup, naive in con.execute(
            "SELECT framework, SUM(CASE WHEN duplicate_usage THEN 0 ELSE input_tokens + output_tokens END), "
            "SUM(input_tokens + output_tokens) FROM v_spans WHERE kind='LLM' GROUP BY framework"):
        print(f"  {fw:<14} tokens: {dedup:,}" + (f"  (a naive SUM would say {naive:,})" if naive != dedup else ""))

    print("\n=== 4. Personal data in the audit trail ===")
    email = con.execute("SELECT COUNT(*) FROM spans WHERE attributes LIKE '%jane.doe@example.com%'").fetchone()[0]
    name = con.execute("SELECT COUNT(*) FROM spans WHERE attributes LIKE '%Jane%'").fetchone()[0]
    print(f"  spans containing the customer's email: {email} (scrubbed on ingestion)")
    print(f"  spans containing the name 'Jane':      {name} (the model inferred it from the email and wrote it)")

    print("\n=== 5. Tamper attempts on the locked trail ===")
    for sql in ("DELETE FROM spans WHERE framework='adk'", "UPDATE spans SET status='OK'"):
        try:
            con.execute(sql)
            print(f"  {sql.split()[0]}: ALLOWED (should not happen)")
        except sqlite3.DatabaseError as e:
            print(f"  {sql.split()[0]}: {e}")
    con.close()


if __name__ == "__main__":
    main()
