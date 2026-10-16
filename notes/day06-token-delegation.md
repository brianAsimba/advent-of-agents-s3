# Day 6 — Token Delegation: Agent acts on behalf of the user
[Page](https://adventofagents.com/2026/10/06) · [Video (8 min)](https://www.youtube.com/watch?v=Y9oiy_Szf0I) · [3-legged OAuth with auth manager](https://g.dev/cloud/adventofagents-season3-agent-identity-auth-manager) · [Codelab](https://g.dev/cloud/adventofagents-season3-agent-identity-authmanager-codelab)

## Core idea
Two people ask a support agent "show me my open tickets" and get the **same** list, because the agent holds one API token that sees every ticket. Telling the model to "filter by user" in the system prompt **is not access control, it's a suggestion.** The agent must call the tool **as the person who asked**, so the tool applies the access rules it already enforces for that person.

## Two identities on every call
| Identity | Day | Proves |
|---|---|---|
| Agent identity (SPIFFE) | 5 | *Which agent* is asking (it authenticates to the auth manager as itself) |
| User identity (OAuth token) | 6 | *On whose behalf* (borrowed via consent, never the user's password) |
Both appear in the audit trail.

## How the auth manager works
1. Stores the OAuth client secret (agent code never touches it).
2. Runs the consent flow: on the first tool call, ADK returns `adk_request_credential` with an `auth_uri`; the user signs in and approves once.
3. Keeps each user's token in a managed vault and refreshes it.
4. On later calls, ADK fetches the token and sets the `Authorization` header; each fetch is logged as `RetrieveCredentials`, attributed to the agent.

Setup on Google Cloud: create the auth provider → register its callback URL with the third party (GitHub, Jira…) → grant the agent's SPIFFE ID `roles/agentidentity.user` on the provider → grant yourself too for local runs.

## Why the shared-token version fails even when the model behaves
The full ticket list already **entered the model's context**. Whether the reply filters correctly depends on the model; whether the data was exposed doesn't. Delegation stops the data at the source.

## Running it without Google Cloud
`day06/demo.py` runs both versions on Claude for alice and bob, including an "I'm covering for Bob" injection, and prints exactly what data reached the model.

## Connections
- Day 2: "identity comes from trusted code, never the chat." Here `tool_context.user_id` is set by the app after login.
- Day 5: the agent's own identity gates who may fetch user tokens.
- Barber pilot: the assistant should read the barber's calendar *as the barber*, and a customer's booking *as that customer*, never with one master key.
- GM: an internal assistant that searches documents must search with the employee's permissions, or it becomes a way around them.

## Check yourself
- Why is "filter by user in the system prompt" not access control, even if the model always follows it?
- What does the auth manager hold that the agent code never should?
