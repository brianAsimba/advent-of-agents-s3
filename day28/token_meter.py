"""Day 28 cost controls: meter every call, bound every loop, cap the spend, alert in minutes.

Course (ADK + Google Cloud)                            Here
-----------------------------------------------------  ---------------------------------------------------------
after_model_callback meters token usage                Meter.record(), from the API's real usage fields
labels={"agent": ...} on every model call              agent and variant on every ledger row
BigQuery over Cloud Trace spans                        burn_rate_by_agent.sql over the ledger
Token burn and runaway loop alerts                     token_burn_alerts(), runaway_alerts()
RunConfig(max_llm_calls=8) + a polite fallback         Limits.max_calls in run_bounded()
Cloud Billing spend cap, set below your real limit     Budget: refuses a call that could cross the cap
*(my addition)*                                        no-progress stop: the same tool result repeating ends the run

The Claude API has no per-call billing labels, so attribution here comes from this ledger. Across a whole account, split
agents by workspace or API key and read the provider's own usage reports, because this ledger only sees its own calls.
"""
import json
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
PRICES = {k: v for k, v in json.loads((HERE / "prices.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}
MODEL = "claude-opus-5-5"
CHARS_PER_TOKEN_LOW_ESTIMATE = 3  # deliberately pessimistic, so the budget errs toward refusing


class BudgetExceeded(Exception):
    pass


class Meter:
    def __init__(self, db: str = ":memory:", now: Callable[[], float] = time.time):
        self.now = now
        self.db = sqlite3.connect(db)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS calls (ts REAL, session TEXT, agent TEXT, variant TEXT, model TEXT, priced INTEGER,
                input INTEGER, output INTEGER, cache_write INTEGER, cache_read INTEGER, usd REAL);
            CREATE TABLE IF NOT EXISTS tasks (session TEXT, agent TEXT, variant TEXT, success INTEGER, status TEXT);
        """)

    def record(self, session: str, agent: str, variant: str, msg) -> float:
        """Prices all four usage fields. In the Messages API, input_tokens excludes cache reads and writes."""
        u = msg.usage
        tokens = {"input": u.input_tokens or 0, "output": u.output_tokens or 0,
                  "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0,
                  "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0}
        model = getattr(msg, "model", MODEL)
        priced = model in PRICES  # a fallback model may be missing from the table; flag it instead of guessing quietly
        usd = usd_for(tokens, PRICES.get(model, PRICES[MODEL]))
        self.db.execute("INSERT INTO calls VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (self.now(), session, agent, variant, model, int(priced), tokens["input"], tokens["output"],
                         tokens["cache_write"], tokens["cache_read"], usd))
        self.db.commit()
        return usd

    def finish_task(self, session: str, agent: str, variant: str, success: bool, status: str) -> None:
        self.db.execute("INSERT INTO tasks VALUES (?,?,?,?,?)", (session, agent, variant, int(success), status))
        self.db.commit()

    def spent(self) -> float:
        return self.db.execute("SELECT COALESCE(SUM(usd), 0) FROM calls").fetchone()[0]

    def unpriced_calls(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM calls WHERE priced = 0").fetchone()[0]

    def burn_rate(self, since: float = 0) -> list[dict]:
        sql = (HERE / "burn_rate_by_agent.sql").read_text(encoding="utf-8")
        cur = self.db.execute(sql, {"since": since})
        return [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    def cost_per_success(self, variant: str) -> dict:
        """Everything the variant spent, including failed attempts, divided by the tasks it got right."""
        usd = self.db.execute("SELECT COALESCE(SUM(usd), 0) FROM calls WHERE variant = ?", (variant,)).fetchone()[0]
        total, wins = self.db.execute("SELECT COUNT(*), COALESCE(SUM(success), 0) FROM tasks WHERE variant = ?",
                                      (variant,)).fetchone()
        return {"usd": usd, "tasks": total, "successes": wins, "usd_per_success": usd / wins if wins else None}

    def token_burn_alerts(self, threshold: int = 20000, window: int = 300) -> list[str]:
        """Billing data arrives hours late, and this comes from the calls themselves. Set the threshold from your normal."""
        rows = self.db.execute("SELECT agent, SUM(input + cache_write + cache_read + output) FROM calls WHERE ts >= ? "
                               "GROUP BY agent", (self.now() - window,)).fetchall()
        return [f"TOKEN BURN {agent}: {tokens} tokens in {window}s (threshold {threshold})"
                for agent, tokens in rows if tokens > threshold]

    def runaway_alerts(self, threshold: float = 10, window: int = 300) -> list[str]:
        rows = self.db.execute("SELECT agent, 1.0 * COUNT(*) / COUNT(DISTINCT session) FROM calls WHERE ts >= ? GROUP BY agent",
                               (self.now() - window,)).fetchall()
        return [f"RUNAWAY LOOP {agent}: {avg:.1f} model calls per session (threshold {threshold})"
                for agent, avg in rows if avg > threshold]


def usd_for(tokens: dict, price: dict) -> float:
    return (tokens["input"] * price["input"] + tokens["output"] * price["output"] +
            tokens["cache_write"] * price["cache_write_5m"] + tokens["cache_read"] * price["cache_read"]) / 1_000_000


class Budget:
    """A cap, not an alert. It refuses a call whose worst case could cross the limit, so set it below your real one."""

    def __init__(self, meter: Meter, limit_usd: float):
        self.meter, self.limit = meter, limit_usd
        self.refused = 0

    def worst_case(self, request_chars: int, max_tokens: int) -> float:
        price = PRICES[MODEL]
        tokens = {"input": 0, "output": max_tokens, "cache_read": 0,
                  "cache_write": request_chars // CHARS_PER_TOKEN_LOW_ESTIMATE}
        return usd_for(tokens, price)

    def check(self, request_chars: int, max_tokens: int) -> None:
        worst = self.worst_case(request_chars, max_tokens)
        if self.meter.spent() + worst > self.limit:
            self.refused += 1
            raise BudgetExceeded(f"spent ${self.meter.spent():.4f}; this call could cost up to ${worst:.4f}; cap is ${self.limit:.2f}")


@dataclass
class Limits:
    max_calls: int = 8
    max_repeats: int = 3  # the same tool call returning the same result this many times is not progress


@dataclass
class Result:
    status: str  # done | call_limit | no_progress | budget | refusal | truncated | error
    text: str
    calls: int
    tool_calls: list[dict] = field(default_factory=list)


FALLBACKS = {"call_limit": "I couldn't finish this within my step limit, so I stopped.",
             "no_progress": "I kept getting the same result, so I stopped rather than keep spending.",
             "budget": "This request was stopped by the spending cap.",
             "error": "The model call failed, so I stopped."}


def run_bounded(client, *, agent: str, session: str, variant: str, system: list[dict], tools: list[dict],
                handler: Callable[[str, dict], dict], task: str, effort: str, meter: Meter, budget: Budget,
                limits: Limits, max_tokens: int = 2000) -> Result:
    """A manual tool loop in which every call is budgeted, metered and counted."""
    messages = [{"role": "user", "content": task}]
    seen: Counter = Counter()
    calls, tool_log = 0, []

    def stop(status: str) -> Result:
        return Result(status, FALLBACKS[status], calls, tool_log)

    while True:
        if calls >= limits.max_calls:
            return stop("call_limit")
        chars = len(json.dumps([system, tools], default=str)) + len(json.dumps(messages, default=str))
        try:
            budget.check(chars, max_tokens)
        except BudgetExceeded:
            return stop("budget")
        try:
            msg = client.beta.messages.create(
                model=MODEL, max_tokens=max_tokens, system=system, tools=tools, messages=messages,
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", output_config={"effort": effort})
        except Exception:
            return stop("error")
        calls += 1
        meter.record(session, agent, variant, msg)
        text = " ".join(b.text for b in msg.content if b.type == "text")
        if msg.stop_reason == "refusal":
            return Result("refusal", text, calls, tool_log)
        if msg.stop_reason == "max_tokens":
            return Result("truncated", text, calls, tool_log)
        if msg.stop_reason != "tool_use":
            return Result("done", text, calls, tool_log)
        messages.append({"role": "assistant", "content": msg.content})
        results, stuck = [], False
        for block in (b for b in msg.content if b.type == "tool_use"):
            result = handler(block.name, block.input)
            tool_log.append({"tool": block.name, "args": block.input, "result": result})
            fingerprint = json.dumps([block.name, block.input, result], sort_keys=True, default=str)
            seen[fingerprint] += 1
            stuck = stuck or seen[fingerprint] >= limits.max_repeats
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result, default=str)})
        if stuck:
            return stop("no_progress")
        messages.append({"role": "user", "content": results})
