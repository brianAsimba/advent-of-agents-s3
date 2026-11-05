# Day 26 — Self-Evolving Agents: Gate Every Change, Keep a Kill-Switch
[Page](https://adventofagents.com/2026/10/26) · [Video (13 min)](https://www.youtube.com/embed/LyzLDjrycnw) · [Sample](https://github.com/GoogleCloudPlatform/generative-ai/tree/main/agents/self-evolving-ai) · [Blog](https://developers.googleblog.com/architecting-governed-self-evolving-ai-agents-on-gemini-agent-platform/) · [Model Armor](https://g.dev/cloud/adventofagents-season3-docs-model-armor-overview) · [KMS signatures](https://g.dev/cloud/adventofagents-season3-docs-kms-digital-signatures) · [ADK confirmations](https://g.dev/cloud/adventofagents-season3-docs-adk-tool-confirmation)

## Core idea
A self-evolving agent changes its own code at runtime (recursive self-improvement). "Trust the model" is not a control. **The agent can change its tactics, but not the gates, policies or keys that constrain it,** and an operator can undo everything with one call.

## The chain (course)
1. **Ingress shield:** screens alerts before the model reads them (a local regex stand-in for Model Armor).
2. **AST sandbox:** rejects disallowed imports and built-ins; then a restricted compile and five behavior tests, with repair attempts.
3. **Policy as code:** rate floor, burst ceiling, deny-list of destructive actions.
4. **Signed provenance:** a KMS signature over the code; the gateway verifies the exact source before mounting, so one changed byte is refused.
5. **Tiered approval:** Tier 0 read-only; Tier 1 auto within policy; Tier 2 (changing the agent graph) waits for an on-call engineer.
- **Kill-switch:** `POST /admin/reset` detaches the patch, removes evolved agents, clears principles, expires tickets, and refuses in-flight steps. The audit trail stays.

## What I built (2026-11-04, Claude)
Claude writes a rate limiter for a simulated stampede. Its code only ever runs in a child process with no secrets.
- Availability went from 30% to 100% through all gates, at 1.5 req/s with a burst of 1.
- A hostile alert was stopped with 0 model calls.
- Claude's self-approval of a new agent was refused; the on-call person's approval worked.
- The reset removed everything, voided in-flight work and old signatures, and **the outage came back**.
- 24 of 24 scripted attacks blocked. 2 model calls.

## Lessons
- **Measure, don't believe.** A limiter can declare 2 req/s and really run 50. The policy checks what the code does (my addition, and the most useful one).
- **Later gates must not rely on earlier ones.** The shield only knows patterns, so a paraphrase gets past it, and the policy still holds whatever the model was persuaded to write.
- **The kill-switch needs a clock.** "Undo" isn't enough: a slow model call or an old signature can land after the reset. An epoch on every proposal, ticket and signature kills them all.
- **Resetting restores the old problems too.** It's containment, not a fix, so an operator should know what comes back before calling it.
- **Learned notes are a persistence channel.** They reach future prompts, so screen and cap them, and clear them on reset.
- **Limits of the sandbox:** Python can't sandbox Python. AST rules are depth; the boundary is the process, and in production a VM.
- **Gates get things wrong too.** My replay wrongly rejected a good patch. A gate that's too strict teaches people to bypass it, so check that honest changes can pass (I added a test for that).
- **Field names are prompts.** Claude put the root cause in a field called `source` (see Day 19's `served_by`).

## Connections
- **Day 16:** signed mandates; here, signatures bound to an epoch.
- **Day 17:** plan/guard/apply is this same chain for infrastructure.
- **Day 24:** anomaly detection is how you'd know to pull the switch; Day 25 gates code from people, and this gates code from the agent.
- **Trading agent:** the closest real use. Let the agent tune parameters inside hard limits (Tier 1), require a person for strategy or new agents (Tier 2), and keep a reset that returns to the last approved state. It stays paper-only.
- **SMB clients:** "one call turns the automation off and puts things back" is a concrete promise; pair it with what happens to the old problem.

## Check yourself
The course page has no questions, so these are mine.
- Why isn't the shield enough on its own?
- Why does the policy measure the limiter instead of reading its declared limits?
- What does the epoch protect against that detaching the patch doesn't?
- Why does the reset bring the outage back, and is that a bug?
- Which of these controls would stop working if the agent had a shell?
