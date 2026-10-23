"""Day 16 tests: red-team suite, gateway, spend cap, approval wiring (no model calls)."""
from types import SimpleNamespace

import pytest

import cineagent
import redteam


@pytest.fixture(autouse=True)
def fresh():
    cineagent.reset()


@pytest.mark.parametrize("name,want,got", redteam.run(), ids=lambda v: v if isinstance(v, str) else "")
def test_redteam(name, want, got):
    assert got == want, name


def _ctx():
    return SimpleNamespace(state={})


def _checkout(ctx, qty=2, ticket="standard"):
    return cineagent.create_checkout("meridian", "Oppenheimer", "9:30 PM", ticket, qty, ctx)


def test_gateway_blocks_unlisted_merchant():
    assert "403" in cineagent.list_showtimes("starlight")["message"]
    assert cineagent.list_showtimes("meridian")["status"] == "ok"


def test_honest_purchase_and_wrong_amount():
    ctx = _ctx()
    co = _checkout(ctx)
    assert cineagent.complete_purchase(co["checkout_id"], co["total_cents"] - 1, ctx)["status"] == "refused"
    done = cineagent.complete_purchase(co["checkout_id"], co["total_cents"], ctx)
    assert done["status"] == "completed" and len(done["tickets"]) == 2
    assert cineagent.complete_purchase(co["checkout_id"], co["total_cents"], ctx)["message"] == "checkout_already_completed"


def test_unknown_checkout_is_refused():
    assert cineagent.complete_purchase("co_madeup", 100, _ctx())["status"] == "error"


def test_spend_cap_runs_before_the_tool():
    tool = SimpleNamespace(name="complete_purchase")
    assert cineagent.spend_cap(tool, {"total_cents": 11880}, _ctx()) == {"status": "denied", "message": cineagent.CAP_DENIED}
    assert cineagent.spend_cap(tool, {"total_cents": 3240}, _ctx()) is None
    assert cineagent.spend_cap(SimpleNamespace(name="create_checkout"), {"total_cents": 99999}, _ctx()) is None


def test_payment_tool_requires_confirmation_and_others_do_not():
    tools = {getattr(t, "name", getattr(t, "__name__", "")): t for t in cineagent.build().tools}
    assert tools["complete_purchase"]._require_confirmation is True
    assert callable(tools["create_checkout"])  # plain function: no approval needed to build a cart


def test_tool_outputs_never_carry_signing_material():
    ctx = _ctx()
    co = _checkout(ctx)
    outputs = [cineagent.list_showtimes("meridian"), co, cineagent.complete_purchase(co["checkout_id"], co["total_cents"], ctx)]
    text = repr(outputs)
    assert "merchant_authorization" not in text and "mandate" not in text.lower()
