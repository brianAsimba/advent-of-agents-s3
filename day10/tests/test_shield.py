"""Day 10 shield tests. No real model calls: the filter model is replaced by fakes."""
import json
from types import SimpleNamespace

import prs
import reviewer
import shield


def pr_text(n):
    return f"{prs.PRS[n]['title']}\n{prs.PRS[n]['diff']}"


class FakeClient:
    """Mimics anthropic.Anthropic().messages.create with a canned reply."""
    def __init__(self, verdict=None, stop_reason="end_turn", raw=None, boom=False):
        self.messages = self
        self._v, self._stop, self._raw, self._boom = verdict, stop_reason, raw, boom

    def create(self, **kw):
        if self._boom:
            raise ConnectionError("network down")
        text = self._raw if self._raw is not None else json.dumps({"verdict": self._v, "reason": "test"})
        return SimpleNamespace(stop_reason=self._stop, content=[SimpleNamespace(type="text", text=text)])


def test_rules_catch_the_obvious_attack():
    assert shield.screen_rules(pr_text(3)).action == "BLOCK"


def test_rules_pass_the_clean_pr():
    assert shield.screen_rules(pr_text(4)).action == "ALLOW"


def test_rules_miss_the_subtle_attack():
    assert shield.screen_rules(pr_text(5)).action == "ALLOW"  # why a filter MODEL is needed


def test_rules_block_non_allowlisted_urls():
    v = shield.screen_rules("See https://rel-notes.example-cdn.net/r/x9 for details")
    assert v.action == "BLOCK" and "URL" in v.reason


def test_filter_model_verdict_is_used():
    assert shield.inspect(pr_text(5), "rules+model", FakeClient("BLOCK")).layer == "model"


def test_fail_closed_on_refusal_error_and_garbage():
    assert shield.screen_model("x", FakeClient(stop_reason="refusal")).action == "BLOCK"
    assert shield.screen_model("x", FakeClient(boom=True)).action == "BLOCK"
    assert shield.screen_model("x", FakeClient(raw="not json")).action == "BLOCK"


def test_quarantined_content_never_reaches_the_agent():
    read = {t.__name__: t for t in reviewer.build("rules").tools}["read_pull_request"]
    out = read(3)
    assert out["status"] == "quarantined" and "diff" not in out
