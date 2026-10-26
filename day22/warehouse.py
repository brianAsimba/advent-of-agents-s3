"""Day 22 step 3: one audit trail for every agent. SQLite stands in for BigQuery.

Course (Cloud Trace + BigQuery)                         Here
------------------------------------------------------  ------------------------------------------------------
_Trace log bucket linked to BigQuery (zero copy)        load(): JSON traces -> table `spans` (raw attributes kept)
SDP de-identify on the ingestion path (recommended)     scrub on load with Day 11's deid.deidentify()
View agent_eval.v_spans_openinference: one row per span  VIEW v_spans: both dialects -> one schema
  kind, model, tokens, tool, values, session, dup usage
Locked retention policy (--locked)                       triggers refuse UPDATE/DELETE before retain_until

Limitation: anyone with the SQLite file can drop the triggers. A real locked bucket is enforced by the
provider, and even the project owner can't shorten it.
"""
import json
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "day11"))
import deid  # noqa: E402

RETENTION_DAYS = 400

SCHEMA = """
CREATE TABLE IF NOT EXISTS spans (
  trace_id TEXT, span_id TEXT PRIMARY KEY, parent_id TEXT, name TEXT, framework TEXT, agent TEXT,
  start_ns INTEGER, end_ns INTEGER, status TEXT, attributes TEXT, retain_until INTEGER);
CREATE TRIGGER IF NOT EXISTS spans_no_update BEFORE UPDATE ON spans
  WHEN OLD.retain_until > CAST(strftime('%s','now') AS INTEGER)
  BEGIN SELECT RAISE(ABORT, 'retention locked: audit records are immutable until retain_until'); END;
CREATE TRIGGER IF NOT EXISTS spans_no_delete BEFORE DELETE ON spans
  WHEN OLD.retain_until > CAST(strftime('%s','now') AS INTEGER)
  BEGIN SELECT RAISE(ABORT, 'retention locked: audit records cannot be deleted before retain_until'); END;
"""

# One row per span, both dialects. j(k) reads an attribute whose name contains dots.
VIEW = """
DROP VIEW IF EXISTS v_spans;
CREATE VIEW v_spans AS
WITH a AS (
  SELECT s.*,
    CASE
      WHEN json_extract(attributes,'$."openinference.span.kind"') IS NOT NULL
        THEN json_extract(attributes,'$."openinference.span.kind"')
      WHEN json_extract(attributes,'$."gen_ai.operation.name"') = 'invoke_agent' THEN 'AGENT'
      WHEN json_extract(attributes,'$."gen_ai.operation.name"') = 'generate_content' THEN 'LLM'
      WHEN json_extract(attributes,'$."gen_ai.operation.name"') = 'execute_tool' THEN 'TOOL'
      WHEN name = 'call_llm' THEN 'LLM'
      ELSE 'CHAIN' END AS kind
  FROM spans s)
SELECT
  a.framework, a.agent, a.trace_id, a.span_id, a.parent_id, a.name, a.kind,
  COALESCE(json_extract(attributes,'$."gen_ai.conversation.id"'), json_extract(attributes,'$."session.id"'),
           json_extract(attributes,'$."gcp.vertex.agent.session_id"'),
           (SELECT COALESCE(json_extract(b.attributes,'$."gen_ai.conversation.id"'),
                            json_extract(b.attributes,'$."session.id"'))
              FROM spans b WHERE b.trace_id = a.trace_id
               AND COALESCE(json_extract(b.attributes,'$."gen_ai.conversation.id"'),
                            json_extract(b.attributes,'$."session.id"')) IS NOT NULL LIMIT 1)) AS session_id,
  COALESCE(json_extract(attributes,'$."llm.model_name"'), json_extract(attributes,'$."gen_ai.request.model"')) AS model,
  -- ADK writes usage on call_llm AND on its generate_content child: count it once (on generate_content)
  (a.framework = 'adk' AND a.name = 'call_llm') AS duplicate_usage,
  COALESCE(json_extract(attributes,'$."llm.token_count.prompt"'),
           json_extract(attributes,'$."gen_ai.usage.input_tokens"')) AS input_tokens,
  COALESCE(json_extract(attributes,'$."llm.token_count.completion"'),
           json_extract(attributes,'$."gen_ai.usage.output_tokens"')) AS output_tokens,
  COALESCE(json_extract(attributes,'$."tool.name"'), json_extract(attributes,'$."gen_ai.tool.name"')) AS tool_name,
  NULLIF(COALESCE(json_extract(attributes,'$."tool.parameters"'),
                  json_extract(attributes,'$."gcp.vertex.agent.tool_call_args"')), '{}') AS tool_args,
  json_extract(attributes,'$."input.value"') AS input_value,
  json_extract(attributes,'$."output.value"') AS output_value,
  (a.end_ns - a.start_ns) / 1e6 AS duration_ms,
  a.status
FROM a;
"""


def connect(path: Path | str = ":memory:") -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.executescript(VIEW)
    return con


def _scrub(value):
    if isinstance(value, str):
        return deid.deidentify(value)[0]
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def load(con: sqlite3.Connection, trace_file: Path, retention_days: int = RETENTION_DAYS) -> int:
    d = json.loads(Path(trace_file).read_text(encoding="utf-8"))
    until = int(time.time()) + retention_days * 86400
    rows = [(s["trace_id"], s["span_id"], s["parent_id"], s["name"], d["framework"], d["agent"], s["start_ns"],
             s["end_ns"], s["status"], json.dumps({k: _scrub(v) for k, v in s["attributes"].items()}), until)
            for s in d["spans"]]
    con.executemany("INSERT OR IGNORE INTO spans VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)
