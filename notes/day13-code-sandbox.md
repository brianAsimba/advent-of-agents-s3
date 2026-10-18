# Day 13 — Code Execution Sandbox: Run Untrusted Agent Code Safely
[Page](https://adventofagents.com/2026/10/13) · [Video (8 min)](https://www.youtube.com/watch?v=2lqh-yA_Lv0) · [Companion: Jaymin West, "Agents Are An Environment Problem" (13 min)](https://www.youtube.com/watch?v=aUNSTO6rED0) · [Code Execution overview](https://g.dev/cloud/adventofagents-season3-docs-code-execution-overview) · [Sandboxes overview](https://g.dev/cloud/adventofagents-season3-docs-sandbox-overview)

## Core idea
Days 10–12 screened prompts and governed **pre-built** tools. But many tasks need the agent to **write and run its own code** (amortization schedules, CSV analysis, simulations). Running LLM-generated code on your host or a shared container exposes you to **credential harvesting from environment variables, infinite loops, and lateral network movement**. Give the agent a sandbox instead.

## Google's Code Execution sandbox
- **Air-gapped, isolated:** own file system, default 2 vCPU / 1.5 GB RAM (or 4 vCPU / 4 GB), **no network**, no host access.
- **Locked dependencies:** 50+ preinstalled packages (numpy, pandas, scipy, scikit-learn, matplotlib); arbitrary `pip`/`npm` installs are blocked, to prevent supply-chain injection.
- **Stateful per session:** one sandbox per user session, its name stored in `tool_context.state` and reused, so **variables and up to 100 MB of files** persist until a TTL (30 min in the kata, up to 14 days). A cleanup tool deletes it.
- Other sandbox types: Computer Use (browser), Shell Execution (CLI), custom containers.
- Callable from any framework (including ADK), on a laptop or in the cloud.

## Running it on Claude
Anthropic's **code execution tool** (`code_execution_20260521`) runs code in an isolated container on Anthropic's servers; the response carries a `container.id` you pass back to reuse it. In practice Claude ran `python3` via **bash**, a fresh process per call, so **variables did not persist but files did**: the pattern is "save working state to a file in the container, reload it next turn". `day13/demo.py` runs a harmless reach probe on the PC versus in the sandbox, then the course's mortgage example across three turns.

## Connections
- **Trading agent, Camps II/IV:** the strategy-proposer agent will write backtest code. Run it in a sandbox, never on the PC that holds the Alpaca key.
- **Claude Code itself** is "an agent running code on my machine". Its permission prompts are the same idea at the tool level.
- **Day 4:** the Prevention layer's "sandboxes deny egress by default".

## Check yourself
- Name three things LLM-written code could do on your host that a sandbox prevents.
- Why does a sandbox block `pip install`?
- What persisted between turns in my Claude sandbox, and what didn't?
