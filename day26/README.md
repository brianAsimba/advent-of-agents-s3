# Day 26 locally: self-evolving agents (gate every change, keep a kill-switch)

A self-evolving agent changes its own code at runtime, and "trust the model" is not a control. So every change passes a fixed chain of gates, an operator can undo it all with one call, and the agent can change its tactics but never the gates, policy or keys that constrain it. This rebuilds the course's Chrysalis sample on Claude. The traffic, gateway and backend are all simulated.

| Course (Chrysalis, Gemini 4.0 Argon) | Here |
|---|---|
| Agent diagnoses a cache stampede and writes a rate limiter | `propose_fix()`: Claude returns code and declared limits; it has no tools, so proposing is all it can do |
| 1. Ingress shield (regex stand-in for Model Armor) | `ingress_shield()`, also applied to learned principles |
| 2. AST check, restricted compile, 5 behavior tests, repair attempts | `ast_gate()`, then `evolve_runner.py` in a child process; one repair attempt with the reasons |
| 3. Policy as code: rate floor, burst ceiling, action deny-list | `policy_gate()`, on declared **and measured** behavior, plus a traffic replay |
| 4. KMS signature, verified against the exact source before mounting | Ed25519; `Gateway.mount()` verifies, and the gateway holds only the public key |
| 5. Tier 1 auto within policy; Tier 2 waits for a person | single-use tickets for new agents; the on-call person must approve |
| `POST /admin/reset` | `admin_reset()`: operator only, no model involved, audit kept |
| In-flight steps get a 409 after reset | an epoch on every proposal, ticket and signature |
| Credit attribution, Dream-RSI, chaos probe | before/after replay and screened principles only; `chaos_probe.py` (scripted attempts) |
| *(my additions)* | measured behavior; gate code and policy pinned by hash at startup; a mounted patch re-verified before every run; screening of learned principles |

Model calls use `claude-opus-5-5` with server-side `fallbacks: "default"`, so a safety decline retries on another model. If a call still fails, nothing changes.

## Where Claude's code runs
Only in `evolve_runner.py`, a child process with no secrets in its environment, restricted builtins and a timeout. The main process, which holds the signing key and API key, only ever parses that code. **This is not a real sandbox.** Python can't reliably sandbox Python, so the AST rules are depth, not a boundary. Production needs a VM or gVisor.

## Run (repo root)
```bash
uv run pytest day26 -q
```
```bash
uv run python day26/demo.py
```
```bash
uv run python day26/chaos_probe.py
```

## What my run showed (2026-11-04)
- **The outage:** with no limiter, surge availability was 30%.
- **Hostile alert:** stopped at the shield with 0 model calls.
- **The self-patch:** Claude diagnosed the stampede and chose 1.5 req/s with a burst of 1. Availability went from **30% to 100%**, with no calm traffic blocked, through every gate.
- **Tier 2:** Claude asked for a monitoring agent with the two read-only tools. Its own approval was refused; the on-call person's worked.
- **Kill-switch:** the agent's attempt was refused. An operator's call removed the patch, the new agent, the learned principle and the open ticket. **The outage came back at 30%**: a reset restores the old state, including its problems.
- **Chaos probe:** 24 of 24 scripted attempts blocked.
- **Cost:** 2 model calls.

## Three failures on the way, all useful
- **My replay was unfair.** It counted the first second after the stampede as calm traffic, when any limiter has just been drained, so it rejected a working patch for blocking 2.5%. That second no longer counts as calm. The 1% limit is unchanged, and a new test confirms a limiter that really does block calm traffic still fails.
- **An ambiguous field name.** Claude put the outage's root cause in a field called `source`. The gate refused it as not being Python. Renamed to `python_code`, with a description.
- **Both failed safely.** Each time, the gateway stayed as it was and the audit trail said why.

## Limits
- **The shield only knows patterns.** Paraphrased injection gets through it, which is why no later gate relies on it.
- **A green patch can still be the wrong fix.** A limiter contains this stampede; it doesn't repair the cache. The replay also only measures this traffic pattern.
- **"Can't edit the gates" holds here because the agent has no tools.** Give a real agent a shell or repo write access and that needs IAM, not a Python boundary.
- **The hash pin detects a change; it doesn't prevent one.** Anyone who can edit the files can also edit the code that checks them, so production needs the pin outside the process.
- **The deny-list only checks declared actions.** Here, an action is just a string the agent lists; in production it must be enforced where the action runs.
- **Dream-RSI and credit attribution aren't rebuilt.** Before/after replay and a short list of principles are the local stand-ins.
