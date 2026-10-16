# Day 7 on Claude: offline delegation (acting for users while they sleep)

Day 6's consent prompt needs a human at the keyboard. A 2:00 AM job has none. The wrong fix is a super-admin key; the right one is **offline delegation**:

1. While online, the user consents **once** with the `offline_access` scope, which yields a long-lived **refresh token**, stored in a vault.
2. At 2:00 AM the agent reads it **as itself** (Day 5 identity), exchanges it for a **15-minute access token** scoped to that user, stores the **rotated** refresh token as a new vault version, and **disables** the old one.

| Course (Google Cloud) | Here |
|---|---|
| OAuth provider with `offline_access` | `reports_api.py`: refresh tokens, 15-min access tokens, rotation, reuse detection |
| Cloud Secret Manager (versions, disable) | `vault.py`: versioned secrets, only `overnight_summarizer` may read |
| Cloud Scheduler invoking the agent with `user_id` | `demo.py` starts a session as alice, with no human involved |

## Run
```bash
uv run pytest day07 -q
```
```bash
uv run python day07/demo.py
```
Six scenes: no consent → the job fails closed · alice consents once · night 1 (rotation) · night 2 (rotation) · an attacker replays the day-1 token → **reuse detected, whole token family revoked** · night 3 fails closed until alice signs in again. Then the vault audit shows the agent's identity on every read.

## Why rotation matters
A refresh token lives for weeks. If it's stolen, rotation turns the theft into a **detectable event**: the first time either the thief or the job uses an already-used token, the provider kills the whole family. The cost is one morning where alice must sign in again, instead of a silent leak.
