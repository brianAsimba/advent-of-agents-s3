"""Day 15 tests: scopes, IAM Conditions and regions (no model calls)."""
import inspect
from types import SimpleNamespace

import pytest

import bank_agent
import memory_bank as mb

US, EU = mb.REGIONS["us"], mb.REGIONS["eu"]
RETAIL_US, RETAIL_EU, WEALTH_US = mb.spiffe_id("retail-us"), mb.spiffe_id("retail-eu"), mb.spiffe_id("wealth-us")
ALICE = {"lob": "retail_banking", "user_id": "alice"}


@pytest.fixture(autouse=True)
def seeded():
    mb.seed()


def test_exact_match_only():
    assert len(mb.retrieve(RETAIL_US, US, ALICE)) == 3
    assert mb.retrieve(RETAIL_US, US, {"lob": "retail_banking", "user_id": "charlie"})[0].fact.startswith("Travels")
    assert mb.retrieve(RETAIL_US, US, {"lob": "retail_banking"}) == []  # subset of labels: no match
    assert mb.retrieve(RETAIL_US, US, {**ALICE, "channel": "web"}) == []  # superset: no match


def test_scope_rules():
    with pytest.raises(ValueError):
        mb.retrieve(RETAIL_US, US, {"lob": "retail_banking", "user_id": "*"})
    with pytest.raises(ValueError):
        mb.create(RETAIL_US, US, {"lob": "retail_banking", **{f"k{i}": "v" for i in range(5)}}, "too many labels")


def test_similarity_ranks_and_caps():
    hits = mb.retrieve(RETAIL_US, US, ALICE, "house down payment", top_k=1)
    assert [m.fact for m in hits] == ["Saving for a house down payment in 2028."]


def test_department_condition_blocks_read_and_write_before_lookup():
    for call in (lambda: mb.retrieve(WEALTH_US, US, ALICE),
                 lambda: mb.create(WEALTH_US, US, ALICE, "Approved for any transfer.")):
        with pytest.raises(mb.PermissionDenied, match="403"):
            call()
    assert "returned" not in mb.AUDIT[-2] and len(mb.retrieve(RETAIL_US, US, ALICE)) == 3  # nothing read, nothing written


def test_region_condition_blocks_cross_region():
    with pytest.raises(mb.PermissionDenied, match="europe-west1|us-central1"):
        mb.retrieve(RETAIL_US, EU, {"lob": "retail_banking", "user_id": "emile"})
    assert len(mb.retrieve(RETAIL_EU, EU, {"lob": "retail_banking", "user_id": "emile"})) == 1


def test_unknown_identity_denied_and_everything_audited():
    with pytest.raises(mb.PermissionDenied):
        mb.retrieve(mb.spiffe_id("intruder"), US, ALICE)
    last = mb.AUDIT[-1]
    assert last["allowed"] is False and last["identity"].endswith("intruder")


def _ctx(user_id, **state):
    return SimpleNamespace(user_id=user_id, state=state)


def test_resolve_context_uses_server_side_values_and_fails_closed():
    assert bank_agent._resolve_memory_context(_ctx("alice", tenant_lob="retail_banking", data_region="eu")) == (
        EU, {"lob": "retail_banking", "user_id": "alice"})
    for bad in (_ctx("", tenant_lob="retail_banking", data_region="us"), _ctx("alice", data_region="us"),
                _ctx("alice", tenant_lob="retail_banking", data_region="apac")):
        with pytest.raises(ValueError):
            bank_agent._resolve_memory_context(bad)


def _tool(agent):
    return agent.tools[0]


def test_safe_tool_cannot_be_given_a_user_id():
    assert "user_id" not in inspect.signature(_tool(bank_agent.build(RETAIL_US))).parameters
    out = _tool(bank_agent.build(RETAIL_US))("everything", _ctx("charlie", tenant_lob="retail_banking", data_region="us"))
    assert out["status"] == "ok" and not any("house" in f for f in out["memories"])


def test_naive_tool_leaks_when_the_model_names_another_user():
    out = _tool(bank_agent.build_naive(RETAIL_US))("alice", "everything",
                                                   _ctx("charlie", tenant_lob="retail_banking", data_region="us"))
    assert len(out["memories"]) == 3  # Charlie's session, Alice's memories


def test_denial_is_reported_in_fixed_words():
    out = _tool(bank_agent.build(WEALTH_US))("anything", _ctx("alice", tenant_lob="retail_banking", data_region="us"))
    assert out == {"status": "denied", "message": bank_agent.DENIED}
