"""Day 27 tests: org policies, envelope encryption, kill switch, perimeter, lockout check, routes, the agent's tools."""
import json
from types import SimpleNamespace

import pytest

from backup_agent import run_agent, run_tool
from boundary_cloud import ADMIN, AGENT, DESTROYED, DISABLED, ENABLED, KEY, RECORDS, STOLEN, Caller, Denied, Perimeter, build_world
from boundary_kms import KMS, KeyUnavailable


def _denied(code, fn, *args, **kwargs):
    with pytest.raises(Denied) as e:
        fn(*args, **kwargs)
    assert e.value.code == code


@pytest.fixture
def c():
    return build_world()


# ---------- org policies ----------

def test_location_policy_blocks_a_bucket_in_europe(c):
    _denied("ORG_POLICY_LOCATION", c.create_bucket, ADMIN, "eu", "prod-data", "europe-west1", KEY)


def test_cmek_policy_requires_a_key(c):
    _denied("ORG_POLICY_CMEK", c.create_bucket, ADMIN, "plain", "prod-data", "us-central1")


def test_key_must_be_in_the_resource_region(c):
    _denied("KEY_REGION_MISMATCH", c.create_bucket, ADMIN, "other", "prod-data", "us-east1", KEY)


def test_compliant_bucket_is_created(c):
    c.create_bucket(ADMIN, "ok", "prod-data", "us-central1", KEY)
    assert c.buckets["ok"].key == KEY


def test_service_account_keys_are_disabled(c):
    _denied("ORG_POLICY_SA_KEYS", c.create_sa_key, ADMIN, "prod-agents")


@pytest.mark.parametrize("endpoint", ["europe-west4", "global"])
def test_model_endpoints_outside_the_us_are_blocked(c, endpoint):
    _denied("ORG_POLICY_ENDPOINT", c.call_model, AGENT, "prod-agents", endpoint)


def test_us_model_endpoint_is_allowed(c):
    assert c.call_model(AGENT, "prod-agents", "us-central1")


def test_the_agent_cannot_change_a_policy(c):
    _denied("IAM_DENIED", c.set_org_policy, AGENT, "prod-data", {})


# ---------- encryption ----------

def test_stored_bytes_are_ciphertext(c):
    blob = c.buckets["prod-records"].objects["customers.csv"]
    assert b"Ana Fake" not in blob["ciphertext"] and b"Ana Fake" not in blob["wrapped_dek"]
    assert c.get(AGENT, "prod-records", "customers.csv") == RECORDS


def test_each_object_gets_its_own_data_key(c):
    c.put(ADMIN, "prod-records", "again.csv", RECORDS)
    objs = c.buckets["prod-records"].objects
    assert objs["again.csv"]["ciphertext"] != objs["customers.csv"]["ciphertext"]
    assert objs["again.csv"]["wrapped_dek"] != objs["customers.csv"]["wrapped_dek"]


def test_ciphertext_cannot_be_moved_or_altered():
    kms = KMS()
    kms.create_key("k", "us")
    blob = kms.encrypt("k", b"secret", b"a/1")
    with pytest.raises(KeyUnavailable, match="altered or moved"):
        kms.decrypt(blob, b"a/2")
    with pytest.raises(KeyUnavailable, match="altered or moved"):
        kms.decrypt({**blob, "ciphertext": b"x" + blob["ciphertext"][1:]}, b"a/1")


def test_rotation_keeps_old_data_readable(c):
    c.kms.rotate(KEY)
    c.put(ADMIN, "prod-records", "new.csv", b"new")
    objs = c.buckets["prod-records"].objects
    assert objs["new.csv"]["version"] == 2 and objs["customers.csv"]["version"] == 1
    assert c.get(AGENT, "prod-records", "customers.csv") == RECORDS


# ---------- the kill switch ----------

def test_disabling_a_key_stops_reads_for_everyone_and_can_be_undone(c):
    c.set_key_state(ADMIN, "prod-data", KEY, 1, DISABLED)
    _denied("KEY_DISABLED", c.get, AGENT, "prod-records", "customers.csv")
    _denied("KEY_DISABLED", c.get, ADMIN, "prod-records", "customers.csv")
    _denied("KEY_DISABLED", c.put, ADMIN, "prod-records", "x.csv", b"x")
    c.set_key_state(ADMIN, "prod-data", KEY, 1, ENABLED)
    assert c.get(AGENT, "prod-records", "customers.csv") == RECORDS


def test_destroying_a_key_is_permanent(c):
    c.set_key_state(ADMIN, "prod-data", KEY, 1, DESTROYED)
    assert c.kms.keys[KEY]["versions"][1]["material"] is None
    _denied("KEY_DESTROYED", c.get, ADMIN, "prod-records", "customers.csv")
    _denied("KEY_DESTROYED", c.set_key_state, ADMIN, "prod-data", KEY, 1, ENABLED)


def test_the_agent_cannot_touch_keys(c):
    _denied("IAM_DENIED", c.set_key_state, AGENT, "prod-data", KEY, 1, ENABLED)


def test_a_copy_that_already_left_is_beyond_the_kill_switch():
    c = build_world(enforce=False)
    c.copy(AGENT, "prod-records", "customers.csv", "partner-drop")
    c.set_key_state(ADMIN, "prod-data", KEY, 1, DISABLED)
    assert c.buckets["partner-drop"].objects["customers.csv"] == RECORDS


# ---------- the perimeter ----------

def test_without_the_perimeter_iam_alone_lets_the_data_out():
    c = build_world(enforce=False)
    c.copy(AGENT, "prod-records", "customers.csv", "partner-drop")
    assert c.buckets["partner-drop"].objects["customers.csv"] == RECORDS


def test_perimeter_blocks_the_same_copy_with_the_same_grants(c):
    assert "storage.writer" in c.iam[AGENT.principal]["partner-external"]
    _denied("VPC_SC_EGRESS", c.copy, AGENT, "prod-records", "customers.csv", "partner-drop")
    assert c.buckets["partner-drop"].objects == {}


def test_inside_the_perimeter_still_works(c):
    c.create_bucket(ADMIN, "prod-backup", "prod-data", "us-central1", KEY)
    c.copy(AGENT, "prod-records", "customers.csv", "prod-backup")
    assert c.get(AGENT, "prod-backup", "customers.csv") == RECORDS


def test_copy_reencrypts_for_the_destination(c):
    c.create_bucket(ADMIN, "prod-backup", "prod-data", "us-central1", KEY)
    c.copy(AGENT, "prod-records", "customers.csv", "prod-backup")
    src, dst = c.buckets["prod-records"].objects["customers.csv"], c.buckets["prod-backup"].objects["customers.csv"]
    assert src["ciphertext"] != dst["ciphertext"]


def test_agent_cannot_write_directly_outside(c):
    _denied("VPC_SC_EGRESS", c.put, AGENT, "partner-drop", "x", b"x")
    _denied("VPC_SC_EGRESS", c.get, AGENT, "partner-drop", "x")


def test_stolen_credentials_from_outside_are_refused(c):
    _denied("VPC_SC_INGRESS", c.get, STOLEN, "prod-records", "customers.csv")


def test_stolen_credentials_work_without_the_perimeter():
    assert build_world(enforce=False).get(STOLEN, "prod-records", "customers.csv") == RECORDS


def test_admin_passes_through_the_access_level(c):
    assert c.get(ADMIN, "prod-records", "customers.csv") == RECORDS


def test_admin_from_the_wrong_network_is_refused(c):
    away = Caller(ADMIN.principal, "corp-admin", "internet", "203.0.113.9")
    _denied("VPC_SC_INGRESS", c.get, away, "prod-records", "customers.csv")


def test_even_an_admin_cannot_copy_across_the_line(c):
    c.grant(ADMIN.principal, "partner-external", "storage.writer")
    _denied("VPC_SC_EGRESS", c.copy, ADMIN, "prod-records", "customers.csv", "partner-drop")


# ---------- rollout ----------

def test_enforcing_without_an_access_level_is_refused_to_avoid_lockout():
    c = build_world(enforce=False, access_level=False)
    _denied("WOULD_LOCK_OUT", c.enforce_perimeter, ADMIN)
    assert c.perimeter.enforced is False


def test_only_a_perimeter_admin_can_enforce():
    _denied("IAM_DENIED", build_world(enforce=False).enforce_perimeter, AGENT)


def test_dry_run_logs_but_blocks_nothing():
    c = build_world(enforce=False)
    c.copy(AGENT, "prod-records", "customers.csv", "partner-drop")
    assert ("WOULD_DENY", "VPC_SC_EGRESS") in [r[:2] for r in c.audit_rows()]


def test_new_perimeter_starts_in_dry_run(c):
    c.set_perimeter(ADMIN, Perimeter({"prod-data"}, {"storage"}, [], enforced=True))
    assert c.perimeter.enforced is False


# ---------- routes ----------

@pytest.mark.parametrize("url", ["https://paste.example/upload", "https://storage.googleapis.com/x", "http://203.0.113.9/"])
def test_no_route_to_the_public_internet(c, url):
    _denied("NO_ROUTE", c.fetch, AGENT, url)


@pytest.mark.parametrize("url", ["https://restricted.googleapis.com/x", "https://crm.psc.internal/customers"])
def test_private_routes_exist(c, url):
    assert c.fetch(AGENT, url).startswith("simulated")


def test_lookalike_hosts_have_no_route(c):
    _denied("NO_ROUTE", c.fetch, AGENT, "https://restricted.googleapis.com.paste.example/x")
    _denied("NO_ROUTE", c.fetch, AGENT, "https://paste.example/?h=crm.psc.internal")


# ---------- the agent ----------

def test_tool_refusals_come_back_as_data(c):
    args = {"source_bucket": "prod-records", "name": "customers.csv", "destination_bucket": "partner-drop"}
    assert run_tool(c, "copy_object", args)["error"] == "VPC_SC_EGRESS"
    assert run_tool(c, "fetch_url", {"url": "https://paste.example"})["error"] == "NO_ROUTE"
    result = run_tool(c, "create_bucket", {"name": "eu", "location": "europe-west1", "key": ""})
    assert result["error"] == "ORG_POLICY_LOCATION"


def test_tool_schemas_offer_no_identity_or_project():
    from backup_agent import TOOLS
    fields = {p for t in TOOLS for p in t["input_schema"]["properties"]}
    assert not fields & {"caller", "principal", "project", "network", "ip"}


def _blocks(*items):
    return [SimpleNamespace(**i) for i in items]


class FakeClient:
    def __init__(self, *turns):
        self.turns, self.seen = list(turns), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.seen.append(kw)
        stop, content = self.turns.pop(0)
        return SimpleNamespace(stop_reason=stop, content=content)


def test_agent_loop_feeds_the_refusal_back():
    use = _blocks({"type": "tool_use", "id": "1", "name": "copy_object", "input": {
        "source_bucket": "prod-records", "name": "customers.csv", "destination_bucket": "partner-drop"}})
    done = _blocks({"type": "text", "text": "Blocked by VPC_SC_EGRESS."})
    client = FakeClient(("tool_use", use), ("end_turn", done))
    c = build_world()
    attempts, text = run_agent(c, "back it up", client)
    assert attempts[0]["result"]["error"] == "VPC_SC_EGRESS" and "VPC_SC_EGRESS" in text
    assert json.loads(client.seen[1]["messages"][-1]["content"][0]["content"])["error"] == "VPC_SC_EGRESS"
    assert client.seen[0]["fallbacks"] == "default" and c.buckets["partner-drop"].objects == {}


def test_agent_stops_on_a_refusal_without_changing_anything():
    c = build_world()
    attempts, text = run_agent(c, "back it up", FakeClient(("refusal", [])))
    assert attempts == [] and "refusal" in text and c.buckets["partner-drop"].objects == {}


# ---------- audit ----------

def test_audit_records_denials_and_cannot_be_rewritten(c):
    with pytest.raises(Denied):
        c.get(STOLEN, "prod-records", "customers.csv")
    assert ("DENIED", "VPC_SC_INGRESS", STOLEN.principal, "attacker-laptop/203.0.113.9") in [r[:4] for r in c.audit_rows()]
    for sql in ("UPDATE events SET code='x'", "DELETE FROM events"):
        with pytest.raises(Exception, match="append-only"):
            c.audit_db.execute(sql)
