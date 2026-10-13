"""Day 5 identity, deny-by-default and audit tests (no model calls)."""
import json

import pytest

import iam_lib


@pytest.fixture(autouse=True)
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setenv("ISSUER_SECRET", "test-secret")
    monkeypatch.setattr(iam_lib, "IAM_FILE", tmp_path / "iam.json")
    monkeypatch.setattr(iam_lib, "AUDIT_FILE", tmp_path / "audit.jsonl")
    import sqlite3
    db = tmp_path / "warehouse.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE cities_weather (city TEXT, state TEXT, temp_f INTEGER, condition TEXT)")
    con.execute("INSERT INTO cities_weather VALUES ('Seattle','WA',58,'Rainy')")
    con.commit(); con.close()
    monkeypatch.setattr(iam_lib, "DB_FILE", db)


def audit_lines():
    return [json.loads(x) for x in iam_lib.AUDIT_FILE.read_text().splitlines()]


def test_each_agent_gets_its_own_identity():
    a, b = iam_lib.mint("weather_agent"), iam_lib.mint("ops_agent")
    assert iam_lib.verify(a) == "spiffe://brian.local/agents/weather_agent"
    assert iam_lib.verify(b) == "spiffe://brian.local/agents/ops_agent"


def test_tampered_token_is_rejected():
    body, sig = iam_lib.mint("ops_agent").split(".")
    forged = iam_lib.mint("weather_agent").split(".")[0] + "." + sig  # weather claims, ops signature
    with pytest.raises(PermissionError):
        iam_lib.verify(forged)


def test_expired_token_is_rejected():
    old = iam_lib.mint("weather_agent", ttl=10, now=1000)
    with pytest.raises(PermissionError, match="expired"):
        iam_lib.verify(old, now=2000)


def test_new_identity_is_denied_by_default_and_audited():
    out = iam_lib.run_query(iam_lib.mint("weather_agent"), "SELECT * FROM cities_weather")
    assert out["status"] == "error" and "Permission denied" in out["error_message"]
    assert audit_lines()[-1]["allowed"] is False


def test_grant_to_one_agent_does_not_help_another():
    iam_lib.grant(iam_lib.spiffe_id("weather_agent"), "warehouse.jobUser")
    iam_lib.grant(iam_lib.spiffe_id("weather_agent"), "warehouse.dataViewer")
    assert iam_lib.run_query(iam_lib.mint("weather_agent"), "SELECT * FROM cities_weather")["status"] == "success"
    assert iam_lib.run_query(iam_lib.mint("ops_agent"), "SELECT * FROM cities_weather")["status"] == "error"
    who = [(e["principalSubject"].rsplit("/", 1)[-1], e["allowed"]) for e in audit_lines()]
    assert who == [("weather_agent", True), ("ops_agent", False)]


def test_revoke_contains_one_agent():
    p = iam_lib.spiffe_id("weather_agent")
    for r in iam_lib.REQUIRED_ROLES:
        iam_lib.grant(p, r)
    iam_lib.revoke(p)
    assert iam_lib.run_query(iam_lib.mint("weather_agent"), "SELECT 1")["status"] == "error"


def test_writes_are_refused_even_with_roles():
    p = iam_lib.spiffe_id("weather_agent")
    for r in iam_lib.REQUIRED_ROLES:
        iam_lib.grant(p, r)
    out = iam_lib.run_query(iam_lib.mint("weather_agent"), "DROP TABLE cities_weather")
    assert out["status"] == "error"
