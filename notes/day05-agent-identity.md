# Day 5 — Agent Identity: One SPIFFE ID Per Agent
[Page](https://adventofagents.com/2026/10/05) · [Video (10 min)](https://www.youtube.com/watch?v=0z7kizuaB0M) · [Agent Identity overview](https://g.dev/cloud/adventofagents-season3-gemini-enterprise-agent-identity)

## Core idea
Three agents share one service account. One of them read a bucket of customer records. **Which one?** With a shared identity you can't answer that, and every control in later days (gateways, alerts, revocation) depends on that answer. Day 5 fixes the identity layer: Day 4's **Foundation**.

## Service account vs Agent Identity vs user identity
| | Service account | Agent Identity | User identity (Day 6) |
|---|---|---|---|
| Who it represents | Any workload running under it | Exactly one agent | The human who asked |
| Can be shared? | Yes, by many agents | No | n/a: borrowed through delegation |
| Key material | Downloadable JSON key that never expires | X.509 cert rotated every 24 h, nothing to download | The user's own login |
| Least privilege possible? | Hard: permissions are the union of what every agent needs | Yes: grant each agent only its own needs | Agent can't exceed the user |

## The three moves
1. **Turn it on:** deploy with `--agent-identity` (`identity_type=AGENT_IDENTITY`). The platform mints a SPIFFE ID tied to the agent's lifecycle.
2. **Grant to the agent, not an account:** IAM roles go on `principal://<agent identity>`. A new identity starts with no data access, so it fails first (the course makes you watch it fail on purpose).
3. **Verify who acted:** Cloud Logging's `principalSubject` shows the agent's SPIFFE ID on every access.

## Running it without Google Cloud
`day05/` builds the same three moves locally: signed per-agent tokens, an empty-by-default `iam.json`, a `grant`/`revoke` CLI, and an audit log naming the agent. Two agents with identical code get different access purely through identity.

## Connections
- Day 4: this raises the **identity** area of Foundation, and `revoke` demonstrates the Response layer's containment.
- Day 3: the warranty system's lateral A2A calls were verified by exactly this kind of identity.
- Trading agent: today it uses one Alpaca key for everything. Camp VI's executor should be the only identity holding broker credentials.
- GM / interviews: "With a shared service account you can't tell which agent touched the data, so you can't contain one without stopping all of them."

## Check yourself
- Why does a shared service account make least privilege nearly impossible?
- Why does the course make the agent fail *before* granting access?
