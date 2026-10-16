# Day 7 — Offline Delegation: Acting for Users While They Sleep
[Page](https://adventofagents.com/2026/10/07) · [Video (6 min)](https://www.youtube.com/watch?v=fuxdAw4S13I) · [Auth Manager overview](https://g.dev/cloud/adventofagents-season3-day6-docs-authmanager) · [RFC 6749 §6 refresh tokens](https://datatracker.ietf.org/doc/html/rfc6749#section-6)

## Core idea
Day 6's on-behalf-of flow opens a consent screen, which only works with a human present. A 2:00 AM incident summarizer has nobody to click "Approve". Giving it a shared **super-admin key** breaks least privilege: it could read everyone's data, not just the person who scheduled it.

**Offline token delegation** fixes this with two layers of identity:
1. **Daytime, once:** the user consents with `offline_access` → a long-lived **refresh token** goes into a vault.
2. **2:00 AM, unattended:** the agent authenticates to the vault **as itself** (Day 5 SPIFFE identity), exchanges the refresh token for a **short-lived (15-min) access token** scoped to that user, and calls the API.

## Two ways to vault and refresh
| | DIY: Secret Manager | Managed: Auth Manager |
|---|---|---|
| Storage | Secret versions you manage | Google-managed vault |
| Exchange | Your code posts `grant_type=refresh_token` | `retrieve_credentials(user_id=…)` does it |
| Rotation | You add the new token as a version and **disable the old one** | Automatic |
| Client secret | Must be vaulted by you | Held by the broker |
| Simplest form | — | Attach `GcpAuthProviderScheme` to an `McpToolset`; ADK injects the header |

The scheduler binds `user_id` when it invokes the agent (e.g., `async_stream_query(user_id="alice@…")`), which is how the job knows whose token to use.

## Why rotate and disable
Refresh tokens are long-lived, so they're worth stealing. Rotation means each token works **once**. If an old one is ever replayed, the provider knows a copy exists, and revokes the whole chain. A theft becomes a detectable event that costs one re-login, instead of a silent, permanent leak.

## Running it without Google Cloud
`day07/demo.py`: an overnight summarizer on Claude acting for alice with no human present. It shows fail-closed without consent, one-time consent, two nights of rotation, an attacker replaying the day-1 token (family revoked), and night 3 failing closed. 7 tests.

## Connections to my work
- **Trading agent:** it already runs unattended every day. Today it holds a static Alpaca key forever. The Day 7 pattern is short-lived tokens, a vault the agent reads as itself, and rotation.
- **summit-sync:** a scheduled job too. If it ever needed a user's account, it should use offline delegation, never a master key.
- **Barber pilot:** night-before appointment reminders are exactly this: the job sends as the barber, with the barber's offline consent, and fails closed (and tells him) if consent lapses.
- **GM:** overnight batch agents (reports, data pulls) should run as the person who scheduled them, not as a super-user service account.

## Check yourself
- Why is a super-admin key the wrong fix for unattended jobs?
- What does refresh-token rotation buy you if a token is stolen?
- Why should an unattended job fail closed instead of falling back to a shared key?
