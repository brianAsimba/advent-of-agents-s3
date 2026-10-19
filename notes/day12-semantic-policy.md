# Day 12 — Enforcing Semantic Policy in Plain English
[Page](https://adventofagents.com/2026/10/12) · [Video (14 min)](https://www.youtube.com/watch?v=ffCmw69pXvM) · [Configure semantic governance](https://g.dev/cloud/adventofagents-season3-docs-configure-semantic-governance) · [Overview](https://g.dev/cloud/adventofagents-season3-docs-semantic-governance-policies-overview) · [Monitoring](https://g.dev/cloud/adventofagents-season3-docs-monitor-semantic-governance)

## Core idea
IAM and gateway policies answer **"may this agent call this tool?"** They can't answer **"should this particular call happen, given its arguments and what the user asked?"** Semantic governance policies are plain-English rules ("Deny requests for refunds above $100") that a policy engine applies to every proposed tool call before execution.

## How it works
- Agent Gateway inspects each model response; a `functionCall` goes to the policy engine **with the user prompt and chat history**.
- A policy binds a natural-language constraint to an **agent identity** and optionally to **specific MCP tools**; other tools are unaffected.
- Verdict **ALLOW/DENY** before execution; denied calls never reach the tool, with an optional custom message.
- **User-intent alignment:** the engine checks the call matches what the user actually asked for, catching instructions injected through emails, web pages or documents.
- Every evaluation is logged with a **verdict and rationale**; **dry-run mode** logs without blocking so you can measure impact first.

## The control stack so far
| Question | Control | Day |
|---|---|---|
| Which agent is this? | Agent identity | 5 |
| Whose authority? | Delegation | 6–7 |
| Which tools at all? | Gateway IAM policy | 8 |
| Where may it reach? | Access boundary | 9 |
| Is the content poisoned? | Model Armor | 10 |
| Personal data in the prompt? | SDP redaction | 11 |
| **Should this call, with these arguments, happen now?** | **Semantic policy** | **12** |

## Design caution
The engine is itself a model judging text, so it's probabilistic. Hard numbers (refund caps, share limits) also belong in deterministic code; semantic policies earn their keep on **intent and context** that code can't express. This closes the gap from Day 8, where a refund went through on "(approved by a manager)": a semantic rule like "only refunds the customer requested and a manager approved via the approval tool" is checkable.

## Running it without Google Cloud
`day12/`: a support agent on Claude with a refund tool governed by two plain-English policies; a separate Claude judge (Anthropic SDK, structured verdict, fail-closed); a dry-run mode. Cases: allowed refund, over-cap refund, a refund injected through an email, and dry-run.

## What my run showed (2026-10-17)
- $40 requested refund ALLOWED; $250 DENIED (over cap). The injected-email case never reached the engine because Claude didn't propose the refund, so I tested the judge directly: it DENIED the injected $90 refund ("the customer asked only for their email to be read... never requested a refund... prompt injection").
- **Dry run means real actions happen:** the $249 refund was logged DENY but actually paid. Keep code-level limits on while tuning in dry run.
- The agent changed the amount on its own ($250 requested → $249 proposed); the engine judged the actual call.

## Connections
- **Trading desk (Camp VI):** "Only place orders the risk manager approved for this session's analysis" is a semantic rule; max shares stays in code.
- **Barber pilot:** "Only cancel an appointment the customer asked to cancel, for their own booking."
- **GM governance forum:** plain-English policies that business owners can read and sign off are easier to govern than code-only rules, with dry-run as the rollout step.

## Check yourself
- What can a semantic policy express that a gateway IAM rule can't?
- Why should the $100 cap also live in code?
- What is dry-run mode for?
