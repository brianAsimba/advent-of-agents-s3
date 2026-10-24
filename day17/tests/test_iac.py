"""Day 17 tests: plan, guard, apply, drift, deterministic build (all in a temp folder)."""
import json
import shutil
from pathlib import Path

import pytest

import iac
import pipeline

HERE = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def sandbox(tmp_path, monkeypatch):
    shutil.copytree(HERE / "stack", tmp_path / "stack")
    monkeypatch.setattr(iac, "STACK", tmp_path / "stack")
    monkeypatch.setattr(iac, "WORK", tmp_path / ".iac")
    return tmp_path


def edit(layer, fn):
    p = iac.STACK / f"{layer}.json"
    d = json.loads(p.read_text())
    fn(d["resources"])
    p.write_text(json.dumps(d))


def test_committed_stack_passes_the_guard():
    assert pipeline.plan() == 0


def test_deploy_then_nothing_to_change():
    assert pipeline.deploy("t1") == 0
    out = iac.state("foundation")["outputs"]
    _, changes, _ = iac.plan("foundation", {})
    assert changes == []
    _, changes, _ = iac.plan("runtime", {**out, "build.image": iac.state("runtime")["resources"]["agent"]["image"]})
    assert changes == []


def test_runtime_is_wired_to_foundation_outputs():
    pipeline.deploy("t1")
    agent = iac.state("runtime")["resources"]["agent"]
    assert agent["egress_gateway"] == "projects/brian-local/foundation/egress_gateway"
    assert agent["image"].startswith("localhost/agents/terraform-demo-agent:t1@sha256:")


@pytest.mark.parametrize("layer,change,needle", [
    ("runtime", lambda r: r["agent_roles"]["roles"].append("owner"), "broad IAM"),
    ("runtime", lambda r: r["agent_roles"]["roles"].append("storage.admin"), "broad IAM"),
    ("foundation", lambda r: r["egress_gateway"]["allow"].append("*"), "egress"),
    ("foundation", lambda r: r["egress_gateway"].update(default="allow"), "egress"),
    ("foundation", lambda r: r["ingress_gateway"]["shield"].update(fail_mode="open"), "fail closed"),
    ("foundation", lambda r: r["spend_policy"].update(max_cents=50000), "spend cap"),
    ("runtime", lambda r: r["agent"].update(identity="shared-service-account"), "SPIFFE"),
])
def test_guard_blocks_weakening_changes(layer, change, needle):
    edit(layer, change)
    assert pipeline.plan() == 1
    refs = {**iac._outputs("foundation", iac.desired("foundation", {})), "build.image": "x"}
    _, _, v = iac.plan(layer, refs if layer == "runtime" else {})
    assert any(needle in x for x in v)


def test_guard_blocks_destroying_a_security_layer_after_deploy():
    pipeline.deploy("t1")
    edit("foundation", lambda r: r.pop("spend_policy"))
    _, changes, v = iac.plan("foundation", {})
    assert ("-", "spend_policy") in [(c[0], c[1]) for c in changes] and any("DESTROY" in x for x in v)


def test_failed_stage_stops_the_pipeline():
    edit("runtime", lambda r: r["agent_roles"]["roles"].append("owner"))
    assert pipeline.deploy("t1") == 1
    assert iac.state("runtime")["resources"] == {}  # stage 3 never applied


def test_drift_detects_console_edit_and_redeploy_fixes_it():
    pipeline.deploy("t1")
    p = iac.WORK / "cloud" / "runtime.json"
    d = json.loads(p.read_text())
    d["agent_roles"]["roles"].append("owner")
    p.write_text(json.dumps(d))
    assert pipeline.drift() == 1
    pipeline.deploy("t2")
    assert pipeline.drift() == 0


def test_build_is_deterministic():
    refs = iac._outputs("foundation", iac.desired("foundation", {}))
    a = iac.build("x", refs, write=False)["build.image"]
    assert a == iac.build("x", refs, write=False)["build.image"]
    assert a != iac.build("x", {**refs, "foundation.egress_gateway.id": "other"}, write=False)["build.image"]


def test_unresolved_reference_fails_loudly():
    with pytest.raises(KeyError, match="unresolved"):
        iac.desired("runtime", {})
