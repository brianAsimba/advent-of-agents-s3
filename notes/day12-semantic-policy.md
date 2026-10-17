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

## Connections
- **Trading desk (Camp VI):** "Only place orders the risk manager approved for this session's analysis" is a semantic rule; max shares stays in code.
- **Barber pilot:** "Only cancel an appointment the customer asked to cancel, for their own booking."
- **GM governance forum:** plain-English policies that business owners can read and sign off are easier to govern than code-only rules, with dry-run as the rollout step.

## Check yourself
- What can a semantic policy express that a gateway IAM rule can't?
- Why should the $100 cap also live in code?
- What is dry-run mode for?
