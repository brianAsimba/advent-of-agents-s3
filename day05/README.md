# Day 5 on Claude: one identity per agent (local model of Agent Identity)

The course deploys to Google's Agent Runtime with `--agent-identity`, grants BigQuery roles to the agent's SPIFFE principal, and checks Cloud Logging. Those are Google Cloud services, so this folder builds the **same three steps** locally:

| Course step | Google Cloud | Here |
|---|---|---|
| Give each agent its own identity | SPIFFE ID + X.509 cert rotated every 24 h | `iam_lib.mint()`: signed `spiffe://brian.local/agents/<name>` token, expires in 24 h, held in memory only |
| New identity has no access | Default roles only | `iam.json` starts empty: deny by default |
| Grant to the agent, not a shared account | `gcloud ... --member="principal://..."` | `uv run python day05/iam.py grant weather_agent` |
| Prove which agent acted | Cloud Logging `principalSubject` | `uv run python day05/iam.py audit` |
| Data | BigQuery `sample_data.cities_weather` | SQLite `warehouse.db`, same 3 rows, read-only |

Two agents (`weather_agent`, `ops_agent`) use the **same code**; only their identity differs.

## Run it (repo root unless noted)
```bash
uv run python day05/setup_data.py
```
```bash
cd day05
uv run adk web --port 8000
```

1. **Watch it fail first.** Pick `weather_agent`, new session: `Return all rows from cities_weather.` → permission denied (missing both roles). Also ask `Who are you?` to see its identity.
2. **Grant to this agent only** (second terminal, repo root):
   ```bash
   uv run python day05/iam.py grant weather_agent
   ```
   Ask again in the same session → 3 rows. Nothing about the agent changed; only what its identity may reach.
3. **Same code, different identity.** Switch to `ops_agent`, ask the same question → still denied.
4. **Prove who did it:**
   ```bash
   uv run python day05/iam.py audit
   ```
   Every line names the exact agent, and whether it was allowed.
5. **Containment** (Day 4's Response layer): `uv run python day05/iam.py revoke weather_agent`, ask again → denied, and `ops_agent` was never affected.

## What this is and isn't
A teaching model: an HMAC-signed token, not mTLS certificates; a JSON file, not Google IAM. The *design* is the real lesson: identity per agent, deny by default, grants to the identity, every access attributed.

**Still shared:** both agents use one Anthropic API key. For full Foundation-layer identity, give each agent its own key (the Anthropic Console allows several) via a `.env` inside each agent folder.
