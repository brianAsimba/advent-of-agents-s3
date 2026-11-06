"""Day 28 demo: price the task, bound the loop, cap the spend, all with real tokens and real prices.

Run from the repo root. THIS COSTS REAL MONEY: about $0.35 of Claude usage, with a hard cap at $3. The data is fake.
  uv run python day28/demo.py
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")
sys.path.insert(0, str(HERE))

import cost_analyst as a  # noqa: E402
import stuck_agent as s  # noqa: E402
from token_meter import Budget, Limits, Meter  # noqa: E402

DEMO_CAP_USD = 3.00


def main() -> None:
    import anthropic
    client = anthropic.Anthropic()
    meter = Meter()
    budget = Budget(meter, DEMO_CAP_USD)
    conn = a.build_db()
    print(f"Spend cap for this whole demo: ${DEMO_CAP_USD:.2f}. Semantic layer: about {len(a.semantic_layer(conn)) // 4} tokens.\n")

    print("=== Same 4 questions, same judge, one variable at a time ===")
    print(f"{'variant':14}{'correct':>8}{'calls':>7}{'input tok':>11}{'output':>8}{'cache hit':>11}{'total $':>10}{'$/success':>11}{'index':>7}")
    baseline_per_success = None
    for name, variant in a.VARIANTS.items():
        result = a.run_variant(client, conn, variant, meter, budget, Limits(max_calls=8))
        row = next(r for r in meter.burn_rate() if r["variant"] == name)
        per = result["usd_per_success"]
        baseline_per_success = baseline_per_success or per
        index = f"{100 * per / baseline_per_success:.0f}" if per and baseline_per_success else "-"
        print(f"{name:14}{result['successes']:>5}/{result['tasks']:<2}{row['llm_calls']:>7}{row['input_tokens']:>11}{row['output_tokens']:>8}"
              f"{row['cache_hit_pct']:>10}%{result['usd']:>10.4f}{(f'{per:.4f}' if per else 'none'):>11}{index:>7}")
        bad = [st for st in result["statuses"] if st != "done"]
        if bad:
            print(f"    not finished: {bad}")

    print("\n=== A job that never finishes, and an agent told not to stop ===")
    capped = s.run_stuck(client, "loop-capped", "call_cap_8", meter, budget, Limits(max_calls=8, max_repeats=99))
    capped_usd = meter.cost_per_success("call_cap_8")["usd"]
    print(f"  cap of 8 calls:     {capped.status}, {capped.calls} calls, ${capped_usd:.4f}\n    says: {' '.join(capped.text.split())[:160]}")
    guarded = s.run_stuck(client, "loop-guarded", "no_progress_stop", meter, budget, Limits(max_calls=8, max_repeats=3))
    guarded_usd = meter.cost_per_success("no_progress_stop")["usd"]
    print(f"  no-progress stop:   {guarded.status}, {guarded.calls} calls, ${guarded_usd:.4f}\n    says: {' '.join(guarded.text.split())[:160]}")

    print("\n=== A cap is not an alert ===")
    tiny = Budget(meter, meter.spent() + 0.001)
    stopped = s.run_stuck(client, "loop-capped-usd", "spend_cap", meter, tiny, Limits(max_calls=8))
    print(f"  with only $0.001 left: {stopped.status}, {stopped.calls} model calls made; says: {stopped.text}")

    print("\n=== Which agent is hungriest? (burn_rate_by_agent.sql) ===")
    print(f"  {'agent':15}{'variant':18}{'sessions':>9}{'calls':>7}{'per session':>13}{'input':>9}{'output':>8}{'cache':>8}{'usd':>9}")
    for r in meter.burn_rate():
        print(f"  {r['agent']:15}{r['variant']:18}{r['sessions']:>9}{r['llm_calls']:>7}{r['calls_per_session']:>13}{r['input_tokens']:>9}"
              f"{r['output_tokens']:>8}{r['cache_hit_pct']:>7}%{r['usd']:>9.4f}")

    print("\n=== Alerts, from the calls themselves, not from a bill that arrives hours later ===")
    alerts = meter.token_burn_alerts() + meter.runaway_alerts()
    for alert in alerts or ["none fired"]:
        print(f"  {alert}")

    print(f"\nTotal spent: ${meter.spent():.4f} of the ${DEMO_CAP_USD:.2f} cap.")
    if meter.unpriced_calls():
        print(f"Note: {meter.unpriced_calls()} calls used a fallback model missing from prices.json and were priced at Opus rates.")


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Missing ANTHROPIC_API_KEY: copy day28/.env.example to day28/.env")
    main()
