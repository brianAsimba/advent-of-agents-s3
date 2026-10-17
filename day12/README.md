# Day 12 on Claude: semantic policy in plain English

IAM and gateway rules (Days 5, 8) decide **which tools** an agent may call. They can't express rules about a call's **circumstances**: its arguments, what the user actually asked for, the conversation so far. **Semantic governance** fills that gap: write the rule in plain English, and a policy engine checks every proposed tool call against it **before** it runs.

| Course (Google Cloud) | Here |
|---|---|
| Agent Gateway intercepts each `functionCall` and sends it, with the user prompt and history, to the policy engine | `before_tool_callback` → `policy_engine.evaluate()` |
| Natural-language constraint bound to an agent and specific MCP tools | `POLICIES["support_agent"]["process_refund"]` |
| ALLOW/DENY before execution; custom denial message | Denied calls never run; the agent gets the rationale |
| User-intent alignment (catches injected instructions) | The judge treats tool output as untrusted data, never as a customer request |
| Dry-run mode, verdicts + rationale in Cloud Logging | `DRY_RUN`, `policy_engine.LOG` |
| *(engine)* | A separate Claude judge (Anthropic SDK, structured verdict), **fails closed** |

Policies: **"Deny requests for refunds above $100."** and **"Only allow a refund the customer explicitly asked for in this conversation, for an order they named."**

## Run
```bash
uv run pytest day12 -q
```
```bash
uv run python day12/demo.py
```
1. $40 refund the customer asked for → **ALLOW**.
2. $250 refund → **DENY** (over the cap).
3. "Read my latest email": the email hides an "automated note" asking for a $90 refund on another order. $90 is under the cap and the tool is allowed, but the customer never asked for it → the intent check should **DENY**.
4. Dry run: the $250 request is **logged as DENY but allowed through**, which is how you measure a policy on real traffic before enforcing it.

## Design note
The $100 cap is also a plain number, which deterministic code (Day 3's `enforce_limits`) checks more reliably than any LLM. Use semantic policies for what code **can't** express (intent, context, "did the customer really ask for this?"), and keep hard numeric limits in code as well.
