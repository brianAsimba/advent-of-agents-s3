"""A SQL analyst over a fake coffee chain, with a long semantic layer, for changing one cost variable at a time.

Variants (same questions, same deterministic judge):
  baseline     timestamp in front of the semantic layer, high effort
  low_effort   baseline at low effort
  static_first the timestamp moves into the user message, so the layer can be cached; high effort
  best         static_first at low effort
  no_glossary  best, minus the business definitions
"""
import datetime as dt
import random
import re
import secrets
import sqlite3
from dataclasses import dataclass

from token_meter import Budget, Limits, Meter, Result, run_bounded

AGENT = "sql_analyst"
ROW_CAP = 30  # tool output is billed too, on every later call in the loop
STORES = ["Harbor", "Mill Street", "Union Square", "Riverside", "Old Town", "Airport", "Campus", "Lakeshore", "Depot",
          "Northgate", "Pier 9", "Market Hall"]
PRODUCTS = [("Drip Coffee", "beverage", 3.5), ("Latte", "beverage", 5.0), ("Cappuccino", "beverage", 4.75),
            ("Cold Brew", "beverage", 5.25), ("Espresso", "beverage", 3.0), ("Matcha", "beverage", 5.5),
            ("Blueberry Muffin", "food", 3.75), ("Croissant", "food", 3.5), ("Breakfast Burrito", "food", 8.5),
            ("Avocado Toast", "food", 9.0), ("House Beans 12oz", "retail", 16.0), ("Single Origin 12oz", "retail", 21.0),
            ("Ceramic Mug", "retail", 14.0), ("Pour-Over Kit", "retail", 32.0)]

SCHEMA_DOC = """# Lantern Coffee analytics: semantic layer

Lantern Coffee is a fictional coffee chain. All data is synthetic. You answer business questions by writing SQLite SELECT
queries with the run_sql tool. Results are capped at {row_cap} rows, so aggregate in SQL instead of reading raw rows.

## Tables

### stores: one row per store
- store_id INTEGER primary key. Stable; never reused after a store closes.
- name TEXT. The store's short display name. Unique.
- region TEXT. One of: north, south, east, west. Assigned by the operations team and used in regional reports.
- opened_on TEXT. ISO date on which the store first traded. Compare it as text; the ISO format sorts correctly.
- closed_on TEXT. ISO date on which the store stopped trading. NULL if it has not closed.
- is_pilot INTEGER. 1 if the store is a pilot concept, otherwise 0. Pilots report in the same tables as other stores.

### products: one row per product
- product_id INTEGER primary key.
- name TEXT. The product's display name.
- category TEXT. One of: beverage, food, retail. Retail means packaged goods and equipment taken home by the customer.
- list_price REAL. The current price in US dollars. Do not use it for revenue, because prices changed over time; use
  orders.unit_price, which records what was actually charged.

### orders: one row per order, and each order holds one product line
- order_id INTEGER primary key.
- store_id INTEGER, references stores.store_id.
- product_id INTEGER, references products.product_id.
- order_date TEXT. ISO date. The data runs from 2024-01-01 through 2026-09-30. Use substr(order_date, 1, 4) for a
  calendar year and substr(order_date, 1, 7) for a calendar month.
- channel TEXT. One of: store (at the counter), mobile (the app), wholesale (bulk accounts billed separately).
- status TEXT. One of: completed, refunded, cancelled.
- qty INTEGER. Units on the order line. Always at least 1.
- unit_price REAL. US dollars actually charged per unit on this order line.

## Query conventions
- Write one statement, starting with SELECT or WITH. The connection is read-only and refuses anything else.
- Prefer one query that answers the question over several exploratory queries. Every extra query costs money.
- Round money to two decimals only in your final answer, not inside intermediate calculations.
- Dates are text, so use string comparison with ISO dates, for example order_date >= '2026-02-01'.
- Join orders to stores on store_id and to products on product_id. Both joins are always complete.
- Do not filter on list_price. Do not infer a currency conversion; everything is in US dollars.

## Example query shapes
- Units by category: SELECT p.category, SUM(o.qty) FROM orders o JOIN products p USING (product_id) GROUP BY 1;
- Orders by region: SELECT s.region, COUNT(*) FROM orders o JOIN stores s USING (store_id) GROUP BY 1;
- Monthly order counts: SELECT substr(order_date, 1, 7), COUNT(*) FROM orders GROUP BY 1 ORDER BY 1;
- Store openings by year: SELECT substr(opened_on, 1, 4), COUNT(*) FROM stores GROUP BY 1;

## Reference: stores in this data set
{store_list}

## Reference: products in this data set
{product_list}

## Answer format
Answer with a short explanation, then finish with a final line exactly in this form, using digits only, with no currency
symbol and no thousands separators:
ANSWER: <number>
"""
GLOSSARY = """
## Business glossary: these definitions override the plain meaning of the words
- **Net revenue** is qty * unit_price, on orders with status = 'completed', excluding channel = 'wholesale'. Wholesale is
  billed separately and is never included in net revenue. Refunded and cancelled orders are never revenue.
- **Average order value (AOV)** is net revenue divided by the count of distinct orders included in that net revenue.
- **Active store** means a store that opened on or before 2026-01-01, has not closed (closed_on IS NULL), and is not a
  pilot (is_pilot = 0). Closed stores and pilots are never counted as active, even if they traded during the period.
- **Fiscal year** N starts on February 1 of year N and ends on January 31 of year N + 1. **Fiscal Q1 2026** is therefore
  2026-02-01 through 2026-04-30. **Fiscal Q2 2026** is 2026-05-01 through 2026-07-31.
- **Top store** for a period means the store with the highest net revenue in that period.
- **Attach rate** is the share of completed non-wholesale orders that are food or retail.
"""
QUESTIONS = [
    ("What was our total net revenue in calendar 2025?", """
        SELECT SUM(qty * unit_price) FROM orders WHERE substr(order_date, 1, 4) = '2025'
        AND status = 'completed' AND channel != 'wholesale'"""),
    ("How many active stores do we have?", """
        SELECT COUNT(*) FROM stores WHERE opened_on <= '2026-01-01' AND closed_on IS NULL AND is_pilot = 0"""),
    ("What was the top store's net revenue in fiscal Q1 2026? Give the revenue figure.", """
        SELECT MAX(r) FROM (SELECT SUM(qty * unit_price) AS r FROM orders WHERE order_date BETWEEN '2026-02-01' AND '2026-04-30'
        AND status = 'completed' AND channel != 'wholesale' GROUP BY store_id)"""),
    ("What was the average order value on the mobile channel in calendar 2025?", """
        SELECT SUM(qty * unit_price) / COUNT(DISTINCT order_id) FROM orders WHERE substr(order_date, 1, 4) = '2025'
        AND status = 'completed' AND channel = 'mobile'"""),
]
RUN_SQL = {"name": "run_sql", "description": f"Run one read-only SQLite SELECT query. Returns up to {ROW_CAP} rows.",
           "input_schema": {"type": "object", "additionalProperties": False, "required": ["query"],
                            "properties": {"query": {"type": "string", "description": "A single SELECT or WITH statement"}}}}


@dataclass(frozen=True)
class Variant:
    name: str
    effort: str
    static_first: bool
    glossary: bool = True


VARIANTS = {v.name: v for v in (Variant("baseline", "high", False), Variant("low_effort", "low", False),
                                Variant("static_first", "high", True), Variant("best", "low", True),
                                Variant("no_glossary", "low", True, glossary=False))}


def build_db(seed: int = 28, orders: int = 4000) -> sqlite3.Connection:
    rnd = random.Random(seed)
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE stores (store_id INTEGER PRIMARY KEY, name TEXT, region TEXT, opened_on TEXT, closed_on TEXT, is_pilot INTEGER);
        CREATE TABLE products (product_id INTEGER PRIMARY KEY, name TEXT, category TEXT, list_price REAL);
        CREATE TABLE orders (order_id INTEGER PRIMARY KEY, store_id INTEGER, product_id INTEGER, order_date TEXT, channel TEXT,
            status TEXT, qty INTEGER, unit_price REAL);
    """)
    for i, name in enumerate(STORES, 1):
        opened = dt.date(2019 + i % 6, 1 + i % 12, 10).isoformat()
        closed = "2025-06-30" if name == "Depot" else None
        conn.execute("INSERT INTO stores VALUES (?,?,?,?,?,?)", (i, name, ["north", "south", "east", "west"][i % 4], opened, closed,
                                                                 int(name in ("Pier 9", "Market Hall"))))
    conn.execute("UPDATE stores SET opened_on = '2026-03-15' WHERE name = 'Northgate'")
    for i, (name, category, price) in enumerate(PRODUCTS, 1):
        conn.execute("INSERT INTO products VALUES (?,?,?,?)", (i, name, category, price))
    days = (dt.date(2026, 9, 30) - dt.date(2024, 1, 1)).days
    for i in range(1, orders + 1):
        product = rnd.randint(1, len(PRODUCTS))
        date = (dt.date(2024, 1, 1) + dt.timedelta(days=rnd.randint(0, days))).isoformat()
        channel = rnd.choices(["store", "mobile", "wholesale"], [6, 3, 1])[0]
        status = rnd.choices(["completed", "refunded", "cancelled"], [90, 6, 4])[0]
        qty = rnd.randint(20, 60) if channel == "wholesale" else rnd.randint(1, 3)
        price = round(PRODUCTS[product - 1][2] * rnd.choice([0.9, 1.0, 1.0, 1.1]), 2)
        conn.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?)", (i, rnd.randint(1, len(STORES)), product, date, channel, status, qty, price))
    conn.commit()
    conn.execute("PRAGMA query_only = ON")
    return conn


def semantic_layer(conn: sqlite3.Connection, glossary: bool = True) -> str:
    stores = "\n".join(f"- {r[0]} ({r[1]} region), opened {r[2]}" for r in conn.execute("SELECT name, region, opened_on FROM stores"))
    products = "\n".join(f"- {r[0]} ({r[1]}), list price ${r[2]:.2f}" for r in conn.execute("SELECT name, category, list_price FROM products"))
    return SCHEMA_DOC.format(row_cap=ROW_CAP, store_list=stores, product_list=products) + (GLOSSARY if glossary else "")


def expected_answers(conn: sqlite3.Connection) -> list[float]:
    return [conn.execute(sql).fetchone()[0] for _, sql in QUESTIONS]


def run_sql(conn: sqlite3.Connection, query: str) -> dict:
    """Read-only by connection and by shape. Errors come back as data, so the model can correct its query."""
    if not re.match(r"\s*(select|with)\b", query, re.I):
        return {"error": "only SELECT or WITH statements are allowed"}
    steps = {"n": 0}

    def guard():
        steps["n"] += 1
        return 1 if steps["n"] > 2000 else 0  # stops a runaway query

    conn.set_progress_handler(guard, 1000)
    try:
        cur = conn.execute(query)
        rows = cur.fetchmany(ROW_CAP + 1)
        return {"columns": [c[0] for c in cur.description or []], "rows": rows[:ROW_CAP], "truncated": len(rows) > ROW_CAP}
    except sqlite3.Error as e:
        return {"error": str(e)}
    finally:
        conn.set_progress_handler(None, 0)


def judge(text: str, expected: float, tolerance: float = 0.005) -> bool:
    """Deterministic: the final ANSWER line must be within 0.5% of the number from ground-truth SQL."""
    found = re.findall(r"^\s*\**ANSWER:\**\s*\$?(-?[\d,]*\.?\d+)\**\s*$", text or "", re.M | re.I)
    if not found:
        return False
    return abs(float(found[-1].replace(",", "")) - expected) <= abs(expected) * tolerance


def build_system(layer: str, variant: Variant, stamp: str, nonce: str) -> list[dict]:
    """The nonce keeps each variant's cache cold at the start of a run, so runs are comparable and don't reuse earlier ones.

    The baseline carries a cache marker on purpose. It's the common mistake: a marker on a prefix that changes every task
    pays the write premium at the start of each one, and reads only within that task. A per-call timestamp never reads.
    """
    body = f"Layer revision {nonce}.\n{layer}"
    if not variant.static_first:
        body = f"Current time: {stamp}\n{body}"
    return [{"type": "text", "text": body, "cache_control": {"type": "ephemeral"}}]


def run_question(client, conn: sqlite3.Connection, layer: str, variant: Variant, question: str, expected: float, session: str,
                 nonce: str, meter: Meter, budget: Budget, limits: Limits, stamp: str | None = None) -> Result:
    stamp = stamp or dt.datetime.now().isoformat()  # a fresh timestamp per task, as a real app's header would have
    task = question if not variant.static_first else f"(Current time: {stamp})\n{question}"
    result = run_bounded(client, agent=AGENT, session=session, variant=variant.name,
                         system=build_system(layer, variant, stamp, nonce), tools=[RUN_SQL],
                         handler=lambda _name, args: run_sql(conn, args.get("query", "")),
                         task=task, effort=variant.effort, meter=meter, budget=budget, limits=limits)
    meter.finish_task(session, AGENT, variant.name, result.status == "done" and judge(result.text, expected), result.status)
    return result


def run_variant(client, conn: sqlite3.Connection, variant: Variant, meter: Meter, budget: Budget, limits: Limits) -> dict:
    """Same questions, same judge, one variable changed. A fresh prefix per variant, so each pays its own cold start."""
    layer = semantic_layer(conn, variant.glossary)
    nonce = secrets.token_hex(4)
    answers = expected_answers(conn)
    statuses = []
    for i, (question, _) in enumerate(QUESTIONS):
        session = f"{variant.name}-q{i + 1}"
        statuses.append(run_question(client, conn, layer, variant, question, answers[i], session, nonce, meter, budget, limits).status)
    return {**meter.cost_per_success(variant.name), "statuses": statuses}
