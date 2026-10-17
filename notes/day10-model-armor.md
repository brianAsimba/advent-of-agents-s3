# Day 10 — Model Armor: Inspect & Block Malicious Prompts at the Gateway
[Page](https://adventofagents.com/2026/10/10) · [Video (5 min)](https://www.youtube.com/watch?v=0fr0BEdnsio) · [Companion: Swyx with Zico Kolter & Matt Fredrikson (67 min)](https://www.youtube.com/watch?v=j8BAficRjEc&t=67s) · [Model Armor](https://g.dev/cloud/adventofagents-season3-docs-model-armor) · [Demo repo](https://g.dev/cloud/adventofagents-season3-day10-demo)

## Core idea
**Indirect prompt injection:** the attack isn't in what the *user* types; it's in content the agent *fetches* (a PR diff, a web page, an email, a document). An attacker hides instructions in a code comment, e.g. "call `add_collaborator`", and an automated reviewer with privileged tools may follow them. System-prompt rules are brittle, because a model can't reliably tell its operator's instructions from text it just read.

## The fix in the course
- **Model Armor** template with prompt-injection/jailbreak and malicious-URI filters.
- Attached to **Agent Gateway** as a content-authorization policy: every outbound request **and retrieved payload** is screened out of band, with **no security code inside the agent**.
- **Fail closed:** flagged content is blocked at the perimeter, so the agent never acts on it. Verdicts are logged (`sanitizationVerdict = BLOCK`) in Cloud Logging.

## The "lethal trifecta" (companion video)
An agent becomes exploitable when it combines **(1) access to private data or privileged tools, (2) exposure to untrusted content, (3) a way to act or communicate externally**. Remove any one leg, or put a filter on the untrusted-content leg, and the attack loses its path. Model capability alone doesn't fix this: injection doesn't go away as models get smarter.

## Where Day 10 fits
| Day | Control | Protects against |
|---|---|---|
| 2 | Regex input screen inside the agent | Obvious injection in user input |
| 3 | Separation of duties | A fooled reader can't act |
| 8 | Gateway tool policy | Dangerous tool calls, whatever the model wants |
| **10** | **Content screening of fetched data at the gateway** | **Poisoned data reaching the model at all** |
Day 8 and Day 10 together: even if poisoned text slipped past the filter, the gateway policy should still deny `add_collaborator` for a reviewer identity.

## Running it without Google Cloud
`day10/`: a PR reviewer on Claude with a two-layer shield: **rules** (phrases, hidden characters, URL allowlist) and a **filter model** (a separate Claude call via the Anthropic SDK returning a structured ALLOW/BLOCK verdict, failing closed on errors and refusals). PRs: #3 obvious attack, #4 clean, #5 subtle attack with no trigger words. The demo compares shield off, rules, and rules + model.

## Connections
- **Trading agent, Camp IV:** multimodal RAG over news, 10-Ks and earnings calls is untrusted content flowing into an agent that picks trades. Screen it before it reaches the model, and keep the executor behind Day 8-style policy.
- **Barber pilot:** inbound customer texts and reviews are untrusted content.
- **GM:** any assistant that reads supplier documents, emails or tickets has the trifecta if it can also act.

## Check yourself
- Why can't a system prompt reliably stop indirect prompt injection?
- What are the three legs of the lethal trifecta, and which one does Model Armor address?
- Why should a content filter fail closed?
