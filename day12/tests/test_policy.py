"""Day 12 policy-engine tests (no real model calls: the judge is faked)."""
import json
from types import SimpleNamespace

import policy_engine
import support


class FakeJudge:
    def __init__(self, verdict="ALLOW", stop_reason="end_turn", raw=None, boom=False):
        self.messages = self
        self.v, self.stop, self.raw, self.boom = verdict, stop_reason, raw, boom
        self.seen = None

    def create(self, **kw):
        if self.boom:
            raise TimeoutError("engine down")
        self.seen = kw["messages"][0]["content"]
        text = self.raw if self.raw is not None else json.dumps({"verdict": self.v, "rationale": "test"})
        return SimpleNamespace(stop_reason=self.stop, content=[SimpleNamespace(type="text", text=text)])


def setup_function():
    policy_engine.DRY_RUN = False
    policy_engine.LOG.clear()


def test_ungoverned_tools_are_not_judged():
    assert policy_engine.evaluate("support_agent", "lookup_order", {}, "", FakeJudge("DENY")) is None


def test_policies_are_bound_to_the_agent():
    assert policy_engine.evaluate("refunds_agent", "process_refund", {}, "", FakeJudge("DENY")) is None


def test_judge_sees_policies_call_and_conversation():
    j = FakeJudge()
    policy_engine.evaluate("support_agent", "process_refund", {"amount": 250}, "CUSTOMER: refund me", j)
    assert "refunds above $100" in j.seen and '"amount": 250' in j.seen and "CUSTOMER: refund me" in j.seen


def test_fail_closed_on_error_refusal_and_garbage():
    for judge in (FakeJudge(boom=True), FakeJudge(stop_reason="refusal"), FakeJudge(raw="??")):
        assert policy_engine.evaluate("support_agent", "process_refund", {}, "", judge).verdict == "DENY"


def test_dry_run_logs_but_does_not_enforce():
    policy_engine.DRY_RUN = True
    v = policy_engine.evaluate("support_agent", "process_refund", {}, "", FakeJudge("DENY"))
    assert v.verdict == "DENY" and v.enforced is False and policy_engine.LOG[-1]["dry_run"] is True


def test_denied_call_never_runs(monkeypatch):
    monkeypatch.setattr(policy_engine, "_judge", lambda *a, **k: ("DENY", "over the cap"))
    ctx = SimpleNamespace(session=SimpleNamespace(events=[]), user_content=None)
    out = support.govern(SimpleNamespace(name="process_refund"), {"amount": 250}, ctx)
    assert out["status"] == "denied_by_policy"
