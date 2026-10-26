"""Day 22 tests: GenAI bridge, normalized view, dedup, scrubbing, retention lock (synthetic spans, no model)."""
import json
import sqlite3

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Status, StatusCode

import capture
import genai_bridge
import warehouse


def _oi_spans(bridge: bool):
    exp, tp = InMemorySpanExporter(), TracerProvider()
    tp.add_span_processor(SimpleSpanProcessor(exp))
    if bridge:
        genai_bridge.install_genai_bridge(tp)
    t = tp.get_tracer("t")
    with t.start_as_current_span("agent", attributes={"openinference.span.kind": "AGENT", "session.id": "s1"}) as root:
        with t.start_as_current_span("messages.create", attributes={
                "openinference.span.kind": "LLM", "session.id": "s1", "llm.model_name": "claude-opus-5-5",
                "llm.token_count.prompt": 100, "llm.token_count.completion": 20}) as llm:
            llm.set_status(Status(StatusCode.OK))
        with t.start_as_current_span("order_status", attributes={
                "openinference.span.kind": "TOOL", "tool.name": "order_status",
                "tool.parameters": json.dumps({"order_id": "A-17"})}):
            pass
        root.set_attribute("input.value", "I'm jane.doe@example.com, where is A-17?")
    return [capture._span_json(s) for s in exp.get_finished_spans()]


def test_bridge_adds_genai_keys_and_keeps_openinference():
    plain = {s["name"]: s for s in _oi_spans(False)}
    bridged = {s["name"]: s for s in _oi_spans(True)}
    assert "gen_ai.conversation.id" not in plain["messages.create"]["attributes"]
    llm = bridged["messages.create"]
    assert llm["attributes"]["gen_ai.operation.name"] == "generate_content"
    assert llm["attributes"]["gen_ai.usage.input_tokens"] == 100 and llm["attributes"]["llm.token_count.prompt"] == 100
    assert llm["status"] == "UNSET" and plain["messages.create"]["status"] == "OK"
    assert bridged["order_status"]["attributes"]["gen_ai.operation.name"] == "execute_tool"
    assert bridged["agent"]["attributes"]["gen_ai.operation.name"] == "invoke_agent"


def _adk_spans():
    def sp(name, sid, parent, attrs):
        return {"name": name, "trace_id": "t-adk", "span_id": sid, "parent_id": parent, "start_ns": 0,
                "end_ns": 5_000_000, "status": "UNSET", "attributes": attrs}
    usage = {"gen_ai.usage.input_tokens": 400, "gen_ai.usage.output_tokens": 50,
             "gen_ai.request.model": "anthropic/claude-opus-5-5"}
    return [sp("invoke_agent support", "a1", None, {"gen_ai.operation.name": "invoke_agent",
                                                    "gen_ai.conversation.id": "adk-s"}),
            sp("call_llm", "a2", "a1", usage),
            sp("generate_content m", "a3", "a2", {**usage, "gen_ai.operation.name": "generate_content"}),
            sp("execute_tool order_status", "a4", "a1", {"gen_ai.operation.name": "execute_tool",
                                                         "gen_ai.tool.name": "order_status",
                                                         "gcp.vertex.agent.tool_call_args": "{}"})]


@pytest.fixture
def con(tmp_path):
    c = warehouse.connect(tmp_path / "audit.db")
    for agent, fw, spans in (("anthropic", "openinference", _oi_spans(True)), ("adk", "adk", _adk_spans())):
        p = tmp_path / f"{agent}.json"
        p.write_text(json.dumps({"agent": agent, "framework": fw, "question": "q", "spans": spans}))
        warehouse.load(c, p)
    return c


def test_one_view_for_both_dialects(con):
    tools = con.execute("SELECT framework, tool_name, tool_args FROM v_spans WHERE kind='TOOL' ORDER BY framework").fetchall()
    assert tools == [("adk", "order_status", None), ("openinference", "order_status", '{"order_id": "A-17"}')]
    kinds = dict(con.execute("SELECT framework, GROUP_CONCAT(DISTINCT kind) FROM v_spans GROUP BY framework"))
    assert set(kinds["adk"].split(",")) == {"AGENT", "LLM", "TOOL"}


def test_session_propagates_to_child_spans(con):
    assert {r[0] for r in con.execute("SELECT session_id FROM v_spans WHERE framework='openinference'")} == {"s1"}
    assert {r[0] for r in con.execute("SELECT session_id FROM v_spans WHERE framework='adk'")} == {"adk-s"}


def test_adk_usage_counted_once(con):
    dedup, naive = con.execute(
        "SELECT SUM(CASE WHEN duplicate_usage THEN 0 ELSE input_tokens + output_tokens END), "
        "SUM(input_tokens + output_tokens) FROM v_spans WHERE kind='LLM' AND framework='adk'").fetchone()
    assert (dedup, naive) == (450, 900)


def test_email_scrubbed_on_ingestion(con):
    assert con.execute("SELECT COUNT(*) FROM spans WHERE attributes LIKE '%jane.doe@%'").fetchone()[0] == 0
    assert "[EMAIL_ADDRESS]" in con.execute("SELECT input_value FROM v_spans WHERE input_value IS NOT NULL").fetchone()[0]


def test_retention_lock_blocks_update_and_delete(con):
    for sql in ("DELETE FROM spans", "UPDATE spans SET status='OK'"):
        with pytest.raises(sqlite3.DatabaseError, match="retention locked"):
            con.execute(sql)
    assert con.execute("SELECT COUNT(*) FROM spans").fetchone()[0] == 7


def test_expired_records_can_be_removed(tmp_path):
    c = warehouse.connect(tmp_path / "old.db")
    p = tmp_path / "adk.json"
    p.write_text(json.dumps({"agent": "adk", "framework": "adk", "question": "q", "spans": _adk_spans()}))
    warehouse.load(c, p, retention_days=-1)
    c.execute("DELETE FROM spans")
    assert c.execute("SELECT COUNT(*) FROM spans").fetchone()[0] == 0
