# Day 28 locally: cost and token controls (price the task, cap the spend)

An agent can spend money for a long time without answering anyone. So measure the cost of each *successful task*, alert within minutes, and put hard limits on loops and spend. Unlike the last few days, this one is real: real Claude tokens, real prices and a real cap. Only the coffee chain's data is fake.

| Course (ADK + Google Cloud) | Here |
|---|---|
| `after_model_callback` meters tokens | `Meter.record()`, from the API's own usage fields, all four priced |
| `static_instruction` + context cache | `cache_control` on a system prompt that stays the same, with the timestamp moved to the user message |
| `thinking_level="LOW"` | `output_config.effort: "low"` |
| 8 questions, same judge, one change at a time | 4 questions, a judge comparing to ground-truth SQL, 5 variants |
| `RunConfig(max_llm_calls=8)` + polite fallback | `Limits.max_calls` in `run_bounded()` |
| Billing labels by agent | `agent` and `variant` on each ledger row (the Claude API has no per-call labels) |
| BigQuery burn-rate query over traces | `burn_rate_by_agent.sql` over the ledger |
| Token burn and runaway loop alerts | `token_burn_alerts()`, `runaway_alerts()` |
| Cloud Billing spend cap | `Budget`: refuses a call whose worst case could cross the cap |
| *(my additions)* | no-progress stop; a row cap on tool output; a judge with no model in it |

Calls use `claude-opus-5-5` with server-side `fallbacks: "default"`. A fallback model missing from `prices.json` is flagged, not priced silently.

## Run (repo root)
```bash
uv run pytest day28 -q
```
**The demo spends real money,** about $0.35, and caps itself at $3:
```bash
uv run python day28/demo.py
```

## What my run showed (2026-11-05)
| Variant | Correct | Cache hit | Total | Per success | Index |
|---|---|---:|---:|---:|---:|
| `baseline` (timestamp first, high effort) | 4/4 | 46.0% | $0.0865 | $0.0216 | 100 |
| `low_effort` | 4/4 | 46.5% | $0.0791 | $0.0198 | 91 |
| `static_first` (cacheable, high effort) | 4/4 | 80.4% | $0.0509 | $0.0127 | 59 |
| `best` (cacheable, low effort) | 4/4 | 80.6% | $0.0423 | $0.0106 | 49 |
| `no_glossary` | **1/4** | 78.0% | $0.0497 | **$0.0497** | **230** |

- **Moving one timestamp saved about 40%,** with no change in quality. Combined with low effort, about 51%.
- **`no_glossary` is the lesson.** Its total bill was 43% *below* the baseline's, and it looks like a saving until you price the task: each correct answer cost 2.3 times as much. The course's version passed its quality check and cost more; mine failed the check and looked cheap. Either way, you need cost and quality side by side.
- **Stuck loop:** Claude was told not to stop, and kept polling. The call cap stopped it at 8 calls ($0.0313); the no-progress stop ended it at 3 ($0.0094).
- **Spend cap:** with $0.001 left, the call was refused before reaching the model.
- **Token burn alert:** fired at 110,381 tokens in 5 minutes. That's five experiments run back to back against the course's example threshold, so it shows the mechanism, not a real incident.
- **Total:** $0.35.

## Corrections and caveats
- **The baseline hit the cache 46%, not the 0% I expected.** The timestamp here changes per task, so a task's second call still reads. A timestamp on every call would do worse.
- **The runaway alert didn't fire, and the cap is why.** A threshold of 10 calls per session can't trip when a cap stops at 8. Keep the alert threshold below the cap, or alert on sessions hitting it.

## Limits
- **One run, 4 easy questions.** These numbers show direction, not a benchmark. Low effort saved little because the questions were easy and it could still hurt on harder ones, so sweep your own workload. The course saved 83% on an 8,500-token layer; this one is about 1,370, and savings grow with the size of what's cached.
- **The cache lasts 5 minutes by default.** These runs were back to back; traffic with long gaps pays more writes and gets fewer reads.
- **The cap only sees calls made through it.** Another process, or another key, bypasses this ledger entirely. Also set limits on the provider's side and read its usage reports.
- **Prices change.** They're in `prices.json`, from the docs on this date. Check them before quoting a client.
- **Not rebuilt:** Cloud Run limits and the managed-agents billing model.
