"""A local stand-in for Agent Identity auth manager.

Course (Google Cloud)                                   Here
------------------------------------------------------  ---------------------------------------------
Stores the OAuth client secret; runs the consent flow   consent(user) simulates "sign in and approve"
Keeps per-user tokens in a Google-managed vault          vault.json (gitignored); the model never sees it
Agent authenticates as itself (SPIFFE ID, Day 5)         retrieve_credentials() verifies the agent's Day 5 token
roles/agentidentity.user on the auth provider            ALLOWED_AGENTS
Each fetch logged as RetrieveCredentials                 audit.jsonl records BOTH the agent and the user

Command line (repo root):
  uv run python day06/auth_manager.py consent alice   # alice signs in and approves once
  uv run python day06/auth_manager.py revoke alice    # alice withdraws consent
  uv run python day06/auth_manager.py audit
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "day05"))
import iam_lib  # noqa: E402  (Day 5: per-agent identity)

import tickets_api  # noqa: E402

VAULT_FILE = HERE / "vault.json"
AUDIT_FILE = HERE / "audit.jsonl"
ALLOWED_AGENTS = {iam_lib.spiffe_id("helpdesk_delegated")}


class ConsentRequired(Exception):
    def __init__(self, user: str):
        super().__init__(f"{user} has not signed in to the ticket system yet")
        self.auth_uri = f"https://tracker.example/oauth/authorize?login_hint={user}&scope=tickets:read"


def _vault() -> dict:
    return json.loads(VAULT_FILE.read_text()) if VAULT_FILE.exists() else {}


def _audit(**entry) -> None:
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **entry}
    with AUDIT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def consent(user: str) -> None:
    """The user signs in to the ticket system and approves read access for the agent."""
    v = _vault()
    v[user] = tickets_api.oauth_authorize(user)
    VAULT_FILE.write_text(json.dumps(v, indent=2))
    _audit(event="ConsentGranted", onBehalfOf=user)


def revoke(user: str) -> None:
    v = _vault()
    v.pop(user, None)
    VAULT_FILE.write_text(json.dumps(v, indent=2))
    _audit(event="ConsentRevoked", onBehalfOf=user)


def retrieve_credentials(agent_token: str, user: str) -> str:
    """Returns the user's token to a verified, authorized agent. Raises if anything is missing."""
    agent = iam_lib.verify(agent_token)  # raises PermissionError if forged or expired
    if agent not in ALLOWED_AGENTS:
        _audit(event="RetrieveCredentials", principalSubject=agent, onBehalfOf=user, allowed=False, detail="agent lacks agentidentity.user")
        raise PermissionError(f"{agent} may not retrieve user credentials")
    token = _vault().get(user)
    if token is None:
        _audit(event="RetrieveCredentials", principalSubject=agent, onBehalfOf=user, allowed=False, detail="no consent yet")
        raise ConsentRequired(user)
    _audit(event="RetrieveCredentials", principalSubject=agent, onBehalfOf=user, allowed=True)
    return token


def print_audit() -> None:
    if not AUDIT_FILE.exists():
        print("No audit entries yet.")
        return
    for line in AUDIT_FILE.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        agent = e.get("principalSubject", "-").rsplit("/", 1)[-1]
        ok = {True: "ALLOW", False: "DENY ", None: "     "}[e.get("allowed")]
        print(f"{e['ts']}  {e['event']:<20} {ok}  agent={agent:<20} user={e.get('onBehalfOf', '-'):<6} {e.get('detail', '')}")


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:] or ["audit"]
    if cmd == "consent" and rest:
        consent(rest[0]); print(f"{rest[0]} signed in and approved read access to tickets.")
    elif cmd == "revoke" and rest:
        revoke(rest[0]); print(f"{rest[0]}'s consent revoked.")
    else:
        print_audit()
