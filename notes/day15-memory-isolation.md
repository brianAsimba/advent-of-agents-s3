# Day 15 — Agent Memory: Stop Leaks Across Users, Teams & Regions
[Page](https://adventofagents.com/2026/10/15) · [Video: Joyce Chen (15 min)](https://www.youtube.com/watch?v=ZVGaoOG0y3Y) · [Demo repo](https://github.com/chjoyce/advent-of-agents-day15) · [Memory Bank overview](https://g.dev/cloud/adventofagents-season3-docs-memory-bank-overview) · [IAM Conditions](https://g.dev/cloud/adventofagents-season3-docs-memory-bank-iam-conditions) · [Exact-match scopes](https://g.dev/cloud/adventofagents-season3-docs-memory-bank-fetch-memories)

## Core idea
Chat history lasts one conversation; **memory** keeps durable facts about a user across sessions. Kept in one shared pool, it leaks three ways: **across users** (an injected model asks for another customer's facts), **across departments** (Wealth reads or poisons Retail) and **across regions** (a US agent reads EU data, a GDPR problem). The model can't enforce these boundaries, so a prompt can't either.

## Three layers, all outside the model
1. **Exact-match scope from server-side context.** Each memory has up to 5 labels; retrieval needs every label to match exactly, with no wildcards. The backend builds the scope from the authenticated user ID and department in `ToolContext`; the tool takes **no user ID argument**, so the model can't ask for someone else.
2. **IAM Condition per department.** Each department's agent has its own identity (Day 5); a condition on its Memory Bank role pins the `lob` label. Wealth asking for `retail_banking` → `403` before Memory Bank runs. That blocks writes too, so it stops poisoning as well as reads.
3. **One Memory Bank per region.** Project-level roles apply in every region, so the department check alone would let a US agent into the EU bank. The condition also checks the bank's location in `resource.name`.

## What my run showed (2026-10-22, on Claude)
- Alice recalled her 3 facts; Charlie's injection returned 0 of Alice's memories (counted from the audit log).
- Wealth read and write of Retail memories → `403`; US Retail into the EU bank → `403`.
- With the **naive tool** (the model passes `user_id`), Claude refused both the crude injection and a plausible "my wife Alice and I share finances" request. Good model behavior, but it's the only thing protecting that design: the tests show the tool leaks as soon as the model calls it with `user_id="alice"`.

## The control stack so far
| Question | Control | Day |
|---|---|---|
| Which agent is this? | Agent identity | 5 |
| Whose authority? | Delegation | 6–7 |
| Which tools at all? | Gateway IAM policy | 8 |
| Where may it reach? | Access boundary | 9 |
| Is the content poisoned? | Model Armor | 10 |
| Personal data in the prompt? | SDP redaction | 11 |
| Should this call happen now? | Semantic policy | 12 |
| Is model-written code contained? | Sandbox | 13 |
| Are the skills it loads safe? | Skill scanning | 14 |
| **Whose memories can it see, from which team and region?** | **Scoped memory + IAM Conditions + regional banks** | **15** |

## Connections
- **Barber pilot (Camp III):** customer memories ("prefers a fade, Tuesdays") scoped by verified customer ID from the booking session, never from the chat text. If I serve several shops, add a `shop` label, and give each shop's agent a condition pinned to it.
- **SMB clients:** one memory store per client with per-client identities, a direct use of layers 1 and 2.
- **Website chatbot (Camp IIb):** anonymous visitors get no long-term memory, or one scoped to a signed session ID only.
- **GM governance forum:** department-scoped memory (plant, function) and data residency are the questions a global OEM will ask first.

## Check yourself
- Why must the user ID come from the session, not a tool argument?
- What does the department condition stop besides reads?
- Why isn't the department condition enough for GDPR?
