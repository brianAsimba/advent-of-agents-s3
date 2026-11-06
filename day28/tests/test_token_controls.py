"""Day 28 tests: pricing, cost per success, the prefix rule, loop bounds, the cap, alerts (fake model client, no API calls)."""
from types import SimpleNamespace

import pytest

import cost_analyst as a
import stuck_agent as s
from token_meter import PRICES, Budget, BudgetExceeded, Limits, Meter, run_bounded, usd_for


def _usage(input=100, output=50, write=0, read=0):
    return SimpleNamespace(input_tokens=input, output_tokens=output, cache_creation_input_tokens=write, cache_read_input_tokens=read)


def _msg(stop="end_turn", content=(), model="claude-opus-5-5", **usage):
    return SimpleNamespace(stop_reason=stop, content=list(content), model=model, usage=_usage(**usage))


def _text(t):
    return SimpleNamespace(type="text", text=t)


def _use(name, **args):
    return SimpleNamespace(type="tool_use", id=f"t{name}", name=name, input=args)


class FakeClient:
    """Replies from a queue; a callable reply decides per request."""

    def __init__(self, *replies, boom=False):
        self.replies, self.boom, self.seen = list(replies), boom, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.seen.append(kw)
        if self.boom:
            raise ConnectionError("down")
        r = self.replies.pop(0)
        return r(kw) if callable(r) else r


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def meter():
    return Meter()


# ---------- pricing ----------

def test_all_four_usage_fields_are_priced():
    p = PRICES["claude-opus-5-5"]
    tokens = {"input": 1_000_000, "output": 1_000_000, "cache_write": 1_000_000, "cache_read": 1_000_000}
    assert usd_for(tokens, p) == pytest.approx(p["input"] + p["output"] + p["cache_write_5m"] + p["cache_read"])


def test_record_uses_the_response_usage(meter):
    usd = meter.record("s", "a", "v", _msg(input=1000, output=100, write=2000, read=5000))
    assert usd == pytest.approx((1000 * 4 + 100 * 20 + 2000 * 5 + 5000 * 0.2) / 1e6) and meter.spent() == pytest.approx(usd)


def test_missing_cache_fields_count_as_zero(meter):
    msg = SimpleNamespace(model="claude-opus-5-5", usage=SimpleNamespace(input_tokens=10, output_tokens=1,
                                                                         cache_creation_input_tokens=None))
    assert meter.record("s", "a", "v", msg) == pytest.approx((10 * 4 + 20) / 1e6)


def test_a_model_missing_from_the_price_table_is_flagged(meter):
    meter.record("s", "a", "v", _msg(model="some-fallback-model"))
    assert meter.unpriced_calls() == 1


# ---------- cost per success ----------

def test_cost_per_success_includes_failed_attempts(meter):
    for session, ok in (("a", True), ("b", False)):
        meter.record(session, "x", "v", _msg(input=1_000_000, output=0))
        meter.finish_task(session, "x", "v", ok, "done")
    assert meter.cost_per_success("v") == {"usd": pytest.approx(8.0), "tasks": 2, "successes": 1, "usd_per_success": pytest.approx(8.0)}


def test_zero_successes_has_no_cost_per_success(meter):
    meter.finish_task("a", "x", "v", False, "done")
    assert meter.cost_per_success("v")["usd_per_success"] is None


def test_burn_rate_query_ranks_and_attributes(meter):
    meter.record("a", "cheap", "v", _msg(input=10, output=1))
    meter.record("b", "hungry", "v", _msg(input=500, output=10, read=1500))
    rows = meter.burn_rate()
    assert rows[0]["agent"] == "hungry" and rows[0]["cache_hit_pct"] == 75.0 and rows[0]["input_tokens"] == 2000


# ---------- the prefix rule ----------

def _layer():
    return a.semantic_layer(a.build_db(orders=10))


def test_baseline_prefix_changes_with_the_timestamp_and_static_first_does_not():
    layer = _layer()
    base = a.VARIANTS["baseline"]
    assert a.build_system(layer, base, "t1", "n") != a.build_system(layer, base, "t2", "n")
    best = a.VARIANTS["best"]
    assert a.build_system(layer, best, "t1", "n") == a.build_system(layer, best, "t2", "n")


def test_static_first_moves_the_timestamp_into_the_user_message():
    client = FakeClient(_msg(content=[_text("ANSWER: 1")]))
    conn = a.build_db(orders=10)
    meter = Meter()
    a.run_question(client, conn, _layer(), a.VARIANTS["best"], "Q?", 1.0, "s", "n", meter, Budget(meter, 5), Limits(), stamp="STAMP")
    assert "STAMP" in client.seen[0]["messages"][0]["content"] and "STAMP" not in client.seen[0]["system"][0]["text"]
    assert client.seen[0]["fallbacks"] == "default" and client.seen[0]["output_config"]["effort"] == "low"


def test_no_glossary_removes_only_the_definitions():
    conn = a.build_db(orders=10)
    full, bare = a.semantic_layer(conn), a.semantic_layer(conn, glossary=False)
    assert "Net revenue" in full and "Net revenue" not in bare and "## Tables" in bare


def test_semantic_layer_is_long_enough_to_cache():
    assert len(_layer()) / 4 > 512  # the minimum for Opus 5.5; shorter prefixes silently don't cache


def test_variants_change_one_thing_at_a_time():
    v = a.VARIANTS
    assert (v["baseline"].effort, v["baseline"].static_first) == ("high", False)
    assert (v["low_effort"].effort, v["low_effort"].static_first) == ("low", False)
    assert (v["static_first"].effort, v["static_first"].static_first) == ("high", True)
    assert (v["best"].effort, v["best"].static_first) == ("low", True) and not v["no_glossary"].glossary


# ---------- data and judge ----------

def test_data_is_deterministic_and_definitions_change_the_answers():
    conn = a.build_db()
    assert a.expected_answers(conn) == a.expected_answers(a.build_db())
    assert a.expected_answers(conn)[1] == 8  # 12 stores, minus 2 pilots, 1 closed, 1 opened too late
    gross = conn.execute("SELECT SUM(qty * unit_price) FROM orders WHERE substr(order_date, 1, 4) = '2025'").fetchone()[0]
    assert gross > a.expected_answers(conn)[0] * 1.3


@pytest.mark.parametrize("text,expected,ok", [
    ("Done.\nANSWER: 100.2", 100.0, True), ("ANSWER: $1,000.00", 1000.0, True), ("**ANSWER: 8**", 8.0, True),
    ("ANSWER: 110", 100.0, False), ("The answer is 100", 100.0, False), ("", 100.0, False),
    ("ANSWER: 100\nwait\nANSWER: 50", 50.0, True)])
def test_judge(text, expected, ok):
    assert a.judge(text, expected) is ok


def test_sql_tool_is_read_only_and_capped():
    conn = a.build_db(orders=100)
    assert "error" in a.run_sql(conn, "DELETE FROM orders")
    assert "error" in a.run_sql(conn, "WITH x AS (SELECT 1) DELETE FROM orders")
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 100
    result = a.run_sql(conn, "SELECT order_id FROM orders")
    assert len(result["rows"]) == a.ROW_CAP and result["truncated"] is True


def test_sql_error_comes_back_as_data():
    assert "no such" in a.run_sql(a.build_db(orders=1), "SELECT nope FROM missing_table")["error"]


def test_runaway_query_is_stopped():
    q = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT MAX(x) FROM c"
    assert "error" in a.run_sql(a.build_db(orders=1), q)


# ---------- bound the loop ----------

def _kwargs(meter, budget, limits, handler=None):
    return dict(agent="a", session="s", variant="v", system=[{"type": "text", "text": "x"}], tools=[],
                handler=handler or (lambda n, i: {"ok": True}), task="go", effort="low", meter=meter, budget=budget, limits=limits)


def test_call_limit_stops_with_a_polite_answer(meter):
    counter = iter(range(100))

    def varied(_kw):
        return _msg("tool_use", [_use("t", n=next(counter))])

    client = FakeClient(*[varied] * 100)
    r = run_bounded(client, **_kwargs(meter, Budget(meter, 100), Limits(max_calls=8, max_repeats=99)))
    assert r.status == "call_limit" and r.calls == 8 and len(client.seen) == 8 and "step limit" in r.text


def test_stuck_tool_stops_early_without_waiting_for_the_limit(meter):
    client = FakeClient(*[_msg("tool_use", [_use("check_report_status", report_id="R-42")])] * 40)
    r = s.run_stuck(client, "s", "v", meter, Budget(meter, 100), Limits(max_calls=40, max_repeats=3))
    assert r.status == "no_progress" and r.calls == 3


def test_without_the_guard_a_stuck_tool_runs_to_the_limit(meter):
    client = FakeClient(*[_msg("tool_use", [_use("check_report_status", report_id="R-42")])] * 40)
    r = s.run_stuck(client, "s", "v", meter, Budget(meter, 100), Limits(max_calls=40, max_repeats=99))
    assert r.status == "call_limit" and r.calls == 40


def test_a_normal_task_finishes(meter):
    client = FakeClient(_msg("tool_use", [_use("t", q=1)]), _msg(content=[_text("done")]))
    r = run_bounded(client, **_kwargs(meter, Budget(meter, 100), Limits()))
    assert r.status == "done" and r.text == "done" and r.calls == 2


@pytest.mark.parametrize("stop,status", [("refusal", "refusal"), ("max_tokens", "truncated")])
def test_other_stop_reasons_are_reported_and_metered(meter, stop, status):
    r = run_bounded(FakeClient(_msg(stop)), **_kwargs(meter, Budget(meter, 100), Limits()))
    assert r.status == status and meter.spent() > 0


def test_model_failure_is_a_stop_not_a_crash(meter):
    assert run_bounded(FakeClient(boom=True), **_kwargs(meter, Budget(meter, 100), Limits())).status == "error"


def test_failed_tasks_count_against_the_variant(meter):
    conn = a.build_db(orders=10)
    r = a.run_question(FakeClient(_msg(content=[_text("no answer line")])), conn, _layer(), a.VARIANTS["best"], "Q", 1.0, "s", "n",
                       meter, Budget(meter, 5), Limits())
    assert r.status == "done" and meter.cost_per_success("best")["successes"] == 0


# ---------- cap the spend ----------

def test_cap_refuses_before_calling_the_model(meter):
    client = FakeClient(_msg())
    budget = Budget(meter, 0.0001)
    r = run_bounded(client, **_kwargs(meter, budget, Limits()))
    assert r.status == "budget" and client.seen == [] and budget.refused == 1 and meter.spent() == 0


def test_cap_stops_a_run_partway_and_never_crosses_the_limit(meter):
    counter = iter(range(100))
    client = FakeClient(*[lambda _kw: _msg("tool_use", [_use("t", n=next(counter))], input=2000, output=1500)] * 100)
    r = run_bounded(client, **_kwargs(meter, Budget(meter, 0.2), Limits(max_calls=100, max_repeats=99)))
    assert r.status == "budget" and 0 < meter.spent() <= 0.2 and len(client.seen) > 1


def test_worst_case_covers_the_whole_output_allowance(meter):
    budget = Budget(meter, 1)
    assert budget.worst_case(0, 1000) == pytest.approx(0.02)
    assert budget.worst_case(3000, 0) == pytest.approx(1000 * 5 / 1e6)


def test_check_raises_with_the_numbers(meter):
    with pytest.raises(BudgetExceeded, match="cap is"):
        Budget(meter, 0.001).check(0, 1000)


# ---------- alerts ----------

def test_token_burn_alert_uses_a_time_window():
    clock = Clock()
    meter = Meter(now=clock)
    meter.record("s", "hungry", "v", _msg(input=15000, output=0, read=10000))
    meter.record("s", "small", "v", _msg(input=10, output=0))
    assert [x.split()[2] for x in meter.token_burn_alerts()] == ["hungry:"]
    clock.t += 301
    assert meter.token_burn_alerts() == []


def test_runaway_alert_is_per_session_average():
    meter = Meter(now=Clock())
    for _ in range(11):
        meter.record("one", "loopy", "v", _msg())
    meter.record("x", "fine", "v", _msg())
    alerts = meter.runaway_alerts()
    assert len(alerts) == 1 and "loopy" in alerts[0] and "11.0" in alerts[0]


def test_stuck_tool_never_reports_an_error():
    assert s.check_report_status("check_report_status", {"report_id": "R-42"}) == {"status": "PENDING"}
