"""Day 7 offline-delegation tests (no model calls)."""
from types import SimpleNamespace

import pytest

import iam_lib
import overnight
import reports_api
import vault


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setenv("ISSUER_SECRET", "test-secret")
    vault._secrets.clear(); vault.AUDIT.clear()


def consent(user, scopes=("reports:read", "offline_access")):
    t = reports_api.authorize(user, list(scopes))
    if "refresh_token" in t:
        vault.add_version(f"refresh-token-{user}", t["refresh_token"])
    return t


def job(user):
    tool = overnight.build_overnight_agent().tools[0]
    return tool(tool_context=SimpleNamespace(user_id=user))


def test_without_offline_access_there_is_no_refresh_token():
    assert "refresh_token" not in consent("alice", ("reports:read",))


def test_job_fails_closed_without_consent():
    assert job("alice")["status"] == "cannot_act"


def test_job_gets_only_that_users_reports():
    consent("alice")
    out = job("alice")
    assert out["user"] == "alice" and [r["id"] for r in out["reports"]] == ["INC-881", "INC-882"]


def test_each_run_rotates_and_disables_the_old_version():
    consent("alice"); job("alice"); job("alice")
    assert vault.versions("refresh-token-alice") == ["disabled", "disabled", "enabled"]


def test_replayed_refresh_token_revokes_the_family():
    stolen = consent("alice")["refresh_token"]
    job("alice")                                    # legit use rotates it
    assert "reuse detected" in reports_api.refresh(stolen)["error_description"]
    assert job("alice")["status"] == "cannot_act"   # all tokens in the family are dead


def test_access_token_expires_after_15_minutes():
    t = reports_api.authorize("bob", ["reports:read"], now=0)
    assert reports_api.get_reports(t["access_token"], now=60)["status"] == 200
    assert reports_api.get_reports(t["access_token"], now=16 * 60)["status"] == 401


def test_other_agents_cannot_read_the_vault():
    consent("alice")
    with pytest.raises(PermissionError):
        vault.access_latest(iam_lib.mint("helpdesk_delegated"), "refresh-token-alice")
