# Day 28 — Cost & Token Controls: Price the Task, Cap the Spend
[Page](https://adventofagents.com/2026/10/28) · [Video (12 min)](https://www.youtube.com/embed/sbOWPWAcLTE) · [Repo](https://github.com/danielazamorah/agent-cost-controls) · [Context caching](https://g.dev/cloud/adventofagents-season3-docs-context-cache-overview) · [Trace analytics](https://g.dev/cloud/adventofagents-season3-docs-trace-analytics) · [Spend cap](https://g.dev/cloud/adventofagents-season3-docs-billing-spend-cap)

## Core idea
Measure what each task costs, alert on token burn within minutes, and cap loops and spend. The author's agent made 40 model calls and used 49,325 input tokens without answering anyone, and ADK's default limit would have allowed 500.

## How it works (course)
- **Build:** price the *task*, not the token. Put cost next to quality, changing one thing at a time. Bound the loop (`max_llm_calls=8`) with a polite fallback.
- **Run:** alert on token metrics, because billing data arrives hours late. Label each call so spend splits by agent. Cap the spend, because alerts only notify; set the cap below your real limit. Limit Cloud Run instances so a loop can't scale out.
- **Billing:** self-built agents pay for tokens, including thinking, plus runtime. Partner models like Claude bill per token on the same Google Cloud bill. Gemini Enterprise is per seat.

## What I built (2026-11-05, real tokens, $0.35)
| Variant | Correct | Cache hit | $/success | Index |
|---|---|---:|---:|---:|
| baseline | 4/4 | 46.0% | 0.0216 | 100 |
| low_effort | 4/4 | 46.5% | 0.0198 | 91 |
| static_first | 4/4 | 80.4% | 0.0127 | 59 |
| best | 4/4 | 80.6% | 0.0106 | 49 |
| no_glossary | 1/4 | 78.0% | 0.0497 | 230 |

A stuck agent stopped at 8 calls with the cap and 3 with a no-progress check. The spend cap refused a call before it reached the model.

## Lessons
- **Price the task.** `no_glossary` had a lower total bill than the baseline and 2.3 times the cost per correct answer. Tokens and totals both miss that.
- **Caching is a prefix match.** One timestamp at the front cost about 40%. Keep what changes at the end. A cache marker on a changing prefix pays the write premium for little return.
- **Context is cheap to remove and expensive to lose.** Removing definitions saved tokens and lost three correct answers.
- **Limits and alerts are different jobs.** A cap stops, and an alert tells you. They can interfere: a cap at 8 means a runaway alert at 10 never fires.
- **Stuck isn't failing.** The tool returned `PENDING` with no error, so every health check was green while money went out (Day 24 again). Repeating the same call with the same result is a cheap signal.
- **Budget the worst case, before the call.** After-the-fact accounting can overshoot; `max_tokens` tells you the most a call can cost.
- **Tool output is billed on every later call,** so a row cap is a cost control as well as a safety one.

## Connections
- **Day 22:** this ledger is a cost view of the same telemetry.
- **Days 24, 26:** a stuck loop looks healthy, and a spend cap is another kill-switch.
- **Barber pilot / SMB clients:** quote from cost per successful task, cache the shared instructions, and give each client their own key and a cap, so one bad loop can't surprise anyone. The price of a pilot can't be set without this number.
- **Trading agent:** put a daily spend cap and a no-progress stop on overnight runs before they run unattended.
- **Claude Certified Architect:** caching order, effort and cost per task are all likely exam material.

## Check yourself
The course page has no questions, so these are mine.
- Why did `no_glossary` look like a saving, and what showed it wasn't?
- Why does moving a timestamp change the bill?
- Why did the runaway alert stay silent while an agent looped?
- Why does the cap check before the call, using `max_tokens`?
- What can this cap not see?
