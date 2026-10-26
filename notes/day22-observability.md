# Day 22 — Agent Observability: One Audit Trail for Every Agent
[Page](https://adventofagents.com/2026/10/22) · [Video: Dani Zamora & Jesse Carah (16 min)](https://www.youtube.com/watch?v=MvbkDLsIqqk) · [AI Agent Clinic (26 min)](https://www.youtube.com/watch?v=wPdoZRbvaF4) · [Repo: agent-telemetry-side-by-side](https://g.dev/cloud/adventofagents-season3-day22-demo) · [Agent Runtime tracing](https://g.dev/cloud/adventofagents-season3-docs-agent-runtime-tracing) · [Trace analytics](https://g.dev/cloud/adventofagents-season3-docs-trace-analytics)

## Core idea
Every framework emits **OpenTelemetry spans**: the same tree (trace → spans with parents and timings) in different **dialects**. ADK uses the GenAI conventions (`gen_ai.*`); LangGraph via OpenInference uses `llm.*`, `tool.*`, `session.id`. Auditors want **one immutable record** of every model decision and tool call. Fix: capture spans, **bridge** the console-facing keys, **normalize** in one SQL view, store in **one locked, scrubbed** table. The same data then feeds evals, quality alerts and governance.

## How it works
- **Bridge:** a 15-line `SpanProcessor` copies `session.id` → `gen_ai.conversation.id`, sets operation names and token keys, and resets OK → UNSET (the console counts non-UNSET as errors), so LangGraph sessions show up in Agent Runtime's Session view.
- **Words are opt-in:** with content capture on, ADK writes prompts and responses as separate log records linked by trace and span ID; OpenInference stores them on the span.
- **One table:** link the `_Trace` log bucket to BigQuery (zero copy), one view for both dialects (span kind, duplicate usage, tokens, tool, values, session propagated from the root), and lock the bucket's retention.

## What I built (2026-10-25, two real frameworks on Claude)
ADK (native OTel) and a plain Anthropic SDK tool loop with **Arize's real OpenInference instrumentor**, the bridge, and a SQLite warehouse (scrub on ingestion with Day 11's `deid`, a normalizing view, triggers as a retention lock).

Findings:
- Token keys really differ (`gen_ai.usage.input_tokens` vs `llm.token_count.prompt`); the bridge added `gen_ai.conversation.id` where it was missing.
- **ADK with content off doesn't record tool arguments**: the audit row has which tool and when, but not what with. OpenInference had the args.
- **ADK double-reports usage** (`call_llm` + `generate_content` child): naive SUM 2,202 vs real 1,101 tokens.
- **Email scrubbed (0 spans), but Claude inferred "Jane" from the email** and wrote it into its reply (2 spans). Pattern scrubbing misses what models derive.
- DELETE/UPDATE refused by the lock.

## Lessons
- **Normalize at read time, keep raw at write time.** Store the original attributes; let SQL translate. New dialects = a new CASE branch, not a re-ingest.
- **Count once.** Hierarchical spans repeat usage; dashboards that SUM blindly overstate cost.
- **Decide what auditors need before turning content off.** Tool arguments are often the evidence.
- **Scrub outputs too.** Models generate personal data they were never given verbatim.

## Connections
- **Claude Architect cert (Camp II) and Camp roadmap "tracing" task:** this is the hands-on version of agent tracing; the same spans work with any OTel backend (Langfuse, Arize Phoenix, Honeycomb).
- **Barber pilot / SMB clients:** one audit table across n8n + Claude agents per client answers "what did the bot do on Tuesday?"; token totals per client become the basis for billing.
- **Trading agent:** every model decision and tool call (data pulls, paper orders) in one locked log is the backtest/paper audit trail; deduplicated token cost per strategy run.
- **Day 11 / Day 15:** redaction and memory isolation protect inputs; this day shows outputs need the same care.

## Check yourself
- What's the same across frameworks' telemetry, and what differs?
- Why does the bridge reset OK to UNSET?
- Why can a naive SUM of tokens double the real number in ADK?
- Why wasn't scrubbing the email on ingestion enough?
