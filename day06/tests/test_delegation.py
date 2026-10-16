"""Day 6 delegation tests (no model calls)."""
import json
from types import SimpleNamespace

import pytest

import auth_manager
import helpdesk
import iam_lib
import tickets_api


@pytest.fixture(autouse=True)
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setenv("ISSUER_SECRET", "test-secret")
    monkeypatch.setattr(auth_manager, "VAULT_FILE", tmp_path / "vault.json")
    monkeypatch.setattr(auth_manager, "AUDIT_FILE", tmp_path / "audit.jsonl")


def tool(agent):
    return agent.tools[0]


def test_user_token_sees_only_own_tickets():
    ids = [t["id"] for t in tickets_api.list_tickets(tickets_api.oauth_authorize("alice"))["tickets"]]
    assert ids == ["T-101", "T-102"]


def test_shared_service_token_sees_everyone():
    # The anti-pattern: whatever the prompt says, ALL tickets reach the model.
    assert len(helpdesk.shared_list_tickets()["tickets"]) == 5


def test_forged_user_token_is_rejected():
    assert tickets_api.list_tickets("e30.deadbeef")["status"] == 401


def test_delegated_tool_requires_consent_first():
    out = tool(helpdesk.build_delegated_agent())(tool_context=SimpleNamespace(user_id="alice"))
    assert out["status"] == "consent_required" and "auth_uri" in out


def test_delegated_tool_returns_only_that_users_tickets():
    auth_manager.consent("alice"); auth_manager.consent("bob")
    agent = helpdesk.build_delegated_agent()
    alice = tool(agent)(tool_context=SimpleNamespace(user_id="alice"))
    bob = tool(agent)(tool_context=SimpleNamespace(user_id="bob"))
    assert {t["owner"] for t in alice["tickets"]} == {"alice"}
    assert {t["owner"] for t in bob["tickets"]} == {"bob"}


def test_unauthorized_agent_cannot_retrieve_user_credentials():
    auth_manager.consent("alice")
    with pytest.raises(PermissionError):
        auth_manager.retrieve_credentials(iam_lib.mint("some_other_agent"), "alice")


def test_audit_records_agent_and_user():
    auth_manager.consent("alice")
    auth_manager.retrieve_credentials(iam_lib.mint("helpdesk_delegated"), "alice")
    last = json.loads(auth_manager.AUDIT_FILE.read_text().splitlines()[-1])
    assert last["principalSubject"].endswith("/helpdesk_delegated") and last["onBehalfOf"] == "alice"


def test_revoked_consent_stops_access():
    auth_manager.consent("alice"); auth_manager.revoke("alice")
    with pytest.raises(auth_manager.ConsentRequired):
        auth_manager.retrieve_credentials(iam_lib.mint("helpdesk_delegated"), "alice")
