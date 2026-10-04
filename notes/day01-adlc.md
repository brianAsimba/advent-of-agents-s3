# Day 1 — Five Phases of the Agent Development Lifecycle (ADLC)
[Page](https://adventofagents.com/2026/10/01) · [Video (7 min)](https://www.youtube.com/watch?v=ngNxiZhxJjI) · [Intro to Agents whitepaper](https://www.kaggle.com/whitepaper-introduction-to-agents)

## Core idea
Agents choose their own actions at runtime: they call tools, touch data, and keep changing after release. ADLC is the map every later control plugs into. **It's a loop, not a line.**

| Phase | What I do | Checkpoint |
|---|---|---|
| Scope | Write may / must never / data touched / owner | `DESIGN_SPEC.md` |
| Build | Scaffold with Agents CLI + ADK, iterate locally | Trace matches spec |
| Scale | Deploy (Agent Runtime / Cloud Run / GKE) as code | Repeatable deploy |
| Govern | Agent identity, Agent Registry, Agent Gateway, Model Armor | Identifiable, checked traffic |
| Optimize | Evals on every change, OpenTelemetry tracing | Findings back into Scope |

## Why not just SDLC or MLOps
- SDLC: deterministic code, so tests prove correctness.
- MLOps: adds drift, but a model only returns predictions.
- ADLC adds **(1) evaluating the tool trajectory**, not just the answer, and **(2) governing what the agent can reach**. A right answer reached via a forbidden tool is a failure.

## Code walkthrough (`adlc-in-300-seconds.sh`)
1. `gcloud auth application-default login`, `gcloud services enable aiplatform.googleapis.com`, then set `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION=us-central1`. This is plumbing.
2. **Scope:** a 5-line `DESIGN_SPEC.md` (owner, May, May not, Success).
3. **Build:** `uvx google-agents-cli setup` → `agents-cli scaffold create adlc-day1 --prototype --yes` → move the spec into the project → `agents-cli install` → `agents-cli run "What's the weather in San Francisco?"`. Find the `[tool_call: get_weather(...)]` line: that's the first audit trail.
4. **Optimize:** `agents-cli eval run` (LLM judge, billable).
5. **Scale + Govern:** deploy with `--agent-identity`, commented out until Day 5.

## Applied: DESIGN_SPEC for my trading agent
```markdown
# trading-agent
Owner: Brian
May: read account state, positions and scored candidates; propose buys within open_slots; explain each decision
May not: place, modify or cancel orders (Python does that); exceed 5 positions; trade fractional shares; use live money
Success: every buy cites real criteria from its candidate entry; zero buys when open_slots = 0
```
The "Success" line becomes an eval: does each rationale cite real numbers, or is it a generic template?

## Check yourself
- Why is grading the tool trajectory stricter than grading the final answer?
