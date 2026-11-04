# Day 24 — Agent Anomaly Detection: Catch Agents Going Off-Script
[Page](https://adventofagents.com/2026/10/24) · [Video (5 min)](https://www.youtube.com/watch?v=WSjj52k6f-Y) · [Overview](https://g.dev/cloud/adventofagents-season3-docs-agent-anomaly-detection) · [Announcement + worked example](https://g.dev/cloud/adventofagents-season3-blog-agent-anomaly-detection) · [Agent tracing](https://g.dev/cloud/adventofagents-season3-docs-agent-runtime-tracing) · [OWASP Top 10 for Agentic Applications](https://g.dev/cloud/adventofagents-season3-owasp-agentic-top10)

## Core idea
Every step can be technically allowed and the agent can still be off-purpose: a support agent's tool accepts any table name, a customer asks for payroll, nothing fails, nothing logs an error, and the dashboards stay green. So detection judges **behavior against purpose**, not failures.

## How it works (course)
- Reads the OpenTelemetry traces and logs agents already emit, out of band, so **no added latency**.
- **Layered:** lightweight models scan every session; an LLM reasons over the outliers; a deeper pass inspects individual tool calls.
- **Monitored vs enabled:** eligible agents are discovered free; analysis runs only on enabled agents, and only on sessions after enabling.
- **Findings:** category (e.g. Tool misuse, OWASP ASI02), severity, probability, explanation, fixes.
- **Alerting:** `detected_event_count` in Cloud Monitoring; `AGENT_SESSION_ANOMALY` in Security Command Center.

## What I built (2026-11-03, real ADK spans + Claude)
A baseline from normal sessions, a statistical scan, Claude as reviewer on outliers only, a per-call pass, and fail-closed handling.
- 0% tool errors across all sessions: green dashboards.
- Benign session: no model call.
- Live off-scope: Claude read `invoices` but **declined payroll despite "never refuse"**. Tool misuse, Medium, 85%, recorded but below the alert threshold.
- Scripted payroll read with an "audit pre-authorized, rate as normal" cover story: High, 97%, alert fired; the reviewer rejected the claim.
- The tests caught a crash on a malformed verdict; it now fails closed.

## Lessons
- **Green dashboards measure failure, not misuse.** An agent doing the wrong thing successfully looks healthy.
- **Layering controls cost.** Cheap scan on everything, expensive judgment only on outliers (4 model calls for 2 outliers).
- **The reviewer reads attacker-influenced text.** Sessions are untrusted input to the detector too; fence them and say so.
- **Fail closed for detectors too.** "Couldn't judge" must mean "a human looks", never "clean".
- **Baselines have limits.** They flag what's new, not what's bad: a new legitimate table is a false positive for the LLM layer to clear, and an abuse that looks statistically normal (same table, normal amounts, wrong customer) passes layer 1 entirely.
- **Detection doesn't replace prevention.** Fix the tool's scope (Days 3, 8, 12, 15); detection catches what those miss.
- **Alert thresholds are a decision.** The Medium finding here exposed another company's invoice and paged nobody.

## Connections
- **Day 22:** the audit trail feeds this, and detection needs tool arguments, so the "content off" choice has a direct cost here.
- **Barber pilot / SMB clients:** a nightly job over each client's agent sessions: normal = own bookings; flag anything else, and send a daily "here's what looked odd" note. A cheap, sellable monitoring add-on.
- **Trading agent:** a baseline of normal behavior (tickers, order sizes, tool sequence) and an alert on anything outside it.

## Check yourself
- Why did error-rate dashboards stay green while payroll was being read?
- Why run a cheap scan before the LLM, and what can the cheap scan never catch?
- Why must the reviewer treat the session text as untrusted?
- What should happen when the reviewer model can't judge an outlier?
