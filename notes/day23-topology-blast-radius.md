# Day 23 — Agent Topology: See What Breaks Before You Delete a Tool
[Page](https://adventofagents.com/2026/10/23) · [Video: Dani Zamora & Nikhil Jethava (8 min)](https://www.youtube.com/watch?v=CJlc5-MCyMA) · [App Topology overview](https://g.dev/cloud/adventofagents-season3-docs-app-topology-overview) · [API](https://g.dev/cloud/adventofagents-season3-docs-app-topology-api) · [Queries](https://g.dev/cloud/adventofagents-season3-docs-app-topology-queries) · [Remote MCP server](https://g.dev/cloud/adventofagents-season3-docs-app-topology-mcp)

## Core idea
Retiring an MCP server or shipping a breaking change to one of its tools needs two answers: **who declared a dependency** (registry bindings) and **who is calling it now** (traces). App Topology builds one graph of the estate (nodes: Cloud Run, GKE, Reasoning Engines, registry agents, MCP servers, skills, bindings; edges: `DEPENDS_ON`, `Observability/SENDS_TRAFFIC`) and you query it with a small JSON pattern.

## How it works
- **Static blast radius (the contract):** MCP server ← `DEPENDS_ON` ← Binding ← `DEPENDS_ON` ← Agent.
- **Live blast radius (the reality):** MCP server ← `SENDS_TRAFFIC` ← Agent, with error rate and p95 from Cloud Trace. This catches **shadow consumers** that never registered a binding.
- **Verdict:** SAFE if neither query finds anything; otherwise STOP and contact the owners.
- **Same pattern everywhere:** `gcloud app-topology resources-graph generate`, REST, or the App Topology MCP server, so an agent can check impact before it changes anything.

## What I built (2026-10-29, on Claude)
Graph from the registry (Days 18–20 servers) and OpenTelemetry tool-call spans (Day 22 shape), the course's two patterns, `blast_radius.py` with SAFE/STOP exit codes, and a read-only topology MCP server queried by Claude.
- `legacy-search-mcp`: registry and traces disagree. **Shadow** `nightly-report-job` (12 calls, 17% errors, no binding) and **stale** `revenue-insights-agent` (bound, no traffic). STOP: cx-team, data-eng, finance-analytics.
- Claude's plain-English answer was right, named the shadow caller and flagged the 24 h window's limits (weekly/monthly jobs).
- **Tool design lesson:** a bare `[]` for a non-matching pattern made Claude report "lookups came back empty". Returning a count plus a hint with the edge model fixed it.

## Lessons
- **Registry = intent, traces = reality.** You need both: shadow consumers only show up in traces, idle-but-critical jobs only show up in the registry.
- **Look-back windows hide periodic jobs.** 24 h misses the month-end report; widen the window before retiring anything.
- **Make "nothing found" informative.** Empty results need context, or models (and people) misread them.
- **Gate it in CI.** Exit code 1 on STOP lets Day 17's pipeline refuse to destroy a server that still has callers.

## Connections
- **SMB clients:** before changing a shared n8n sub-workflow or tool, list every client workflow that calls it (n8n execution logs = traces), not just the ones in my docs.
- **Trading agent:** before changing a data tool's output schema, check which strategy agents consume it.
- **Day 17 + Day 18 + Day 22:** IaC plans the change, the registry declares dependencies, traces show live use; topology joins them.

## Check yourself
- Why can't the registry alone tell you whether a server is safe to retire?
- What's a shadow consumer, and where does it show up?
- Why is a stale binding still worth a conversation?
- What would you change before trusting a SAFE verdict for a server used by monthly jobs?
