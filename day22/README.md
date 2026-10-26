# Day 22 locally: one audit trail for every agent (OpenTelemetry, two dialects, one locked table)

Agents built in different frameworks all emit **OpenTelemetry spans** (same tree: trace, span, parent, timings) but with **different attribute names**. Auditors want one immutable record of every model call and tool call, for every agent. The course captures the spans, bridges and normalizes the dialects, and stores them in one locked, PII-scrubbed BigQuery table. Here: two real frameworks on Claude, SQLite instead of BigQuery.

| Course | Here |
|---|---|
| ADK, native OTel (GenAI conventions `gen_ai.*`) | `capture.py adk`: ADK on Claude, in-memory exporter |
| LangGraph + OpenInference instrumentor | `capture.py anthropic`: a plain Anthropic SDK tool loop + **Arize's real OpenInference instrumentor** |
| Content capture `EVENT_ONLY`, ADK's words kept off spans | same settings (`ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false`) |
| `genai_bridge.py`: `GenAIBridgeSpanProcessor` (session id, operation names, tokens, OK→UNSET) | `genai_bridge.py`, prepended to the tracer provider |
| `_Trace` bucket linked to BigQuery, one SQL view for both dialects | `warehouse.py`: table `spans` + view `v_spans` (kind, session, model, tokens, dedup flag, tool, args, values, duration) |
| Email regex in SQL; SDP on ingestion recommended for production | scrubbed **on ingestion** with Day 11's `deid` |
| Locked retention (`--locked`) | triggers refuse UPDATE/DELETE before `retain_until` (see limitation in `warehouse.py`) |

## Run (repo root)
```bash
uv run pytest day22 -q
```
```bash
uv run python day22/demo.py
```
Single captures: `uv run python day22/capture.py adk` / `anthropic [--no-bridge] [--question serial]` → `day22/traces/` (gitignored: it contains prompts).

## What my run showed (2026-10-25)
- **Same tree, different names:** ADK `gen_ai.usage.input_tokens` vs OpenInference `llm.token_count.prompt`. The bridge added `gen_ai.conversation.id` to 2 OpenInference spans (0 without it).
- **One table:** both frameworks' `order_status` calls side by side with session, args and timing.
- **Words are opt-in, and that cuts both ways:** with ADK's content capture off, its audit row says *which* tool ran and *when*, but **not the arguments** (`(not captured)`). OpenInference recorded `{"order_id": "A-17"}`. Decide per agent what an auditor needs.
- **Double counting:** ADK puts usage on `call_llm` *and* its `generate_content` child. A naive SUM said 2,202 tokens; the deduplicated answer is 1,101.
- **PII:** the customer's email appeared in 0 stored spans (scrubbed on ingestion). But Claude **inferred the name "Jane" from the email** and wrote it into its reply, so 2 spans contain it. Pattern scrubbing catches what was typed, not what a model derives. Production needs entity detection (SDP person names) on outputs too.
- **Tamper attempts:** DELETE and UPDATE both refused by the retention lock.
