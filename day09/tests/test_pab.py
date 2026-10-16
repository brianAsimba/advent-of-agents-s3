"""Day 9 Principal Access Boundary tests (no model calls)."""
import pytest

import cloud
import iam_lib

AGENT = "spiffe://brian.local/agents/storage_inspector"


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setenv("ISSUER_SECRET", "test-secret")
    cloud.reset()


def read(bucket):
    return cloud.list_objects(iam_lib.mint("storage_inspector"), bucket)


def test_folder_grant_is_inherited_by_sibling_projects():
    cloud.grant("folders/manufacturing", AGENT, "storage.objectViewer")
    assert read("stamping-press-data")["status"] == 200
    assert read("hr-payroll-exports")["status"] == 200  # the blast-radius problem


def test_pab_contains_agent_to_home_project():
    cloud.grant("folders/manufacturing", AGENT, "storage.objectViewer")
    cloud.create_pab("p", ["projects/stamping"]); cloud.bind_pab("p", "projects/stamping")
    assert read("stamping-press-data")["status"] == 200
    out = read("hr-payroll-exports")
    assert out["status"] == 403 and "Principal Access Boundary" in out["error"]


def test_pab_holds_even_against_a_direct_grant():
    cloud.create_pab("p", ["projects/stamping"]); cloud.bind_pab("p", "projects/stamping")
    cloud.grant("projects/hr-payroll", AGENT, "storage.objectViewer")
    assert read("hr-payroll-exports")["status"] == 403


def test_pab_alone_grants_nothing():
    # A boundary is a fence, not a permission: without IAM, even the home project is denied.
    cloud.create_pab("p", ["projects/stamping"]); cloud.bind_pab("p", "projects/stamping")
    assert read("stamping-press-data")["error"] == "Forbidden: no IAM permission"


def test_audit_records_both_checks():
    cloud.grant("folders/manufacturing", AGENT, "storage.objectViewer")
    cloud.create_pab("p", ["projects/stamping"]); cloud.bind_pab("p", "projects/stamping")
    read("hr-payroll-exports")
    e = cloud.AUDIT[-1]
    assert e["iam"].startswith("ALLOW (granted on folders/manufacturing)") and "violation" in e["pab"]
