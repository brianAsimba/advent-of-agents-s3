# Day 11 — Sensitive Data Protection: Redact PII from Agent Prompts
[Page](https://adventofagents.com/2026/10/11) · [Video (4 min)](https://www.youtube.com/watch?v=Edl3DyKUCU4) · [Companion: Karan Shingde, ADK guardrail callbacks (19 min)](https://www.youtube.com/watch?v=9QdbMFkPh74) · [SDP templates](https://g.dev/cloud/adventofagents-season3-docs-sdp-templates) · [ADK callbacks](https://g.dev/cloud/adventofagents-season3-docs-day11-adk-callbacks)

## Core idea
Users paste personal identifiers (emails, phone numbers, SSNs, names) into prompts. Without scrubbing, that data goes into the **model's context**, the **SQL the agent writes**, and **plain-text logs**. Day 11 redacts at the source: values are replaced with placeholders like `[US_SOCIAL_SECURITY_NUMBER]` before the model sees them.

## How the course does it
1. **Sensitive Data Protection templates:** an *inspect* template (which infoTypes to find, with a rule so an email isn't also flagged as a person's name) and a *de-identify* template (replace each finding with its infoType).
2. A **Model Armor template** linking both, plus prompt-injection detection.
3. Two **ADK callbacks**:
   - `before_agent_callback`: once per turn; ends the turn if Model Armor flags an injection.
   - `before_model_callback`: before every model call; swaps each user message (this turn **and history**) for its redacted text.
4. The agent's SQL tool is **read-only** (`WriteMode.BLOCKED`), and its instructions say never to try to unmask placeholders.
Test: "I'm Jane Doe, SSN …, email … repeat my message back": the reply echoes only placeholders.

## Day 2 vs Day 11
| | Day 2 (OUT) | Day 11 (IN) |
|---|---|---|
| Protects | What the agent *says* | What the model *receives* |
| Stops | Leaking data the agent found | The model, its SQL and its logs ever holding user PII |

## Gap my build found: model input ≠ storage
`before_model_callback` edits only the request to the model. ADK has **already stored the original message** in the session, which `adk web` persists and observability may export. An ADK **plugin** (`on_user_message_callback`) runs before that write, so its redacted version is what's stored. Redact at the **earliest** point data enters, not just at the model.

## Running it without Google Cloud
`day11/`: `deid.py` (regex stand-in for SDP), an HR analytics agent on Claude over a read-only SQLite table, both callbacks, and the ingress plugin. The demo prints what the model received, the reply, what the session stored, and whether raw PII remains there.

## What my run showed (2026-10-17)
- Course design: the model received only placeholders (and echoed them), but the stored session held Jane's name, SSN, email and phone in plain text.
- With the ingress plugin: model and storage both held placeholders; the answer (3 in Engineering) was unchanged.
- Injection ended before the model was called; the attack text itself is stored, which is useful evidence for detection (keep attacks, drop personal data).

## Connections
- **Barber pilot:** customers' names and phone numbers are exactly this data. Redact before the model where the model doesn't need them, and keep them out of logs.
- **GM:** employees pasting badge numbers, part numbers tied to suppliers, or HR data into assistants is the same pattern.
- **Trading agent:** keep account numbers and API keys out of prompts and logs.

## Check yourself
- Why redact *input*, when Day 2 already redacts output?
- Why must `before_model_callback` redact the history, not just the latest message?
- Where is the earliest point to redact, and why does it matter?
