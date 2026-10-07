# Day 1 on Claude: the ADLC loop with Google ADK

The course scaffolds this with `agents-cli` on Gemini. Here it's plain Google ADK on your PC, with **Claude** as the model (via LiteLLM and the Anthropic API). No Google Cloud needed.

| ADLC phase | Where it is here |
|---|---|
| Scope | `DESIGN_SPEC.md` |
| Build | `adlc_day1/agent.py` (Claude + two tools), run with `adk run` |
| Optimize | `tests/test_tools.py` (free, deterministic) + reading the tool-call trace |
| Scale / Govern | Later days |

## One-time setup
1. Get an Anthropic API key at https://console.anthropic.com (Settings → API keys). Add a few dollars of credit; Day 1 costs cents.
2. Copy `adlc_day1/.env.example` to `adlc_day1/.env` and paste the key. `.env` is gitignored, so never paste the key anywhere else.

## Run it (from the repo root, PowerShell or Git Bash)
```bash
uv run pytest day01 -q
```
```bash
cd day01
uv run adk run adlc_day1
```
Ask: `What's the weather in San Francisco?` then `What time is it in Detroit?` then `Weather in Atlantis?`

Prefer a browser view with the full trace? From `day01/`:
```bash
uv run adk web --port 8000
```
Open http://localhost:8000, pick `adlc_day1`, and click each event to see the tool call, its arguments and the result. **That trace is your audit trail**: check that every call matches the DESIGN_SPEC.

## What to look for
- Weather question → exactly one `get_weather(city="San Francisco")` call.
- Time question → `get_current_time`, not `get_weather`.
- Unknown city → the tool returns an error and Claude says the city isn't supported, rather than inventing weather. That's the spec's "Do not answer from memory".
