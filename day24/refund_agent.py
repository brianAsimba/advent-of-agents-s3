"""The course's refund demo agent on Claude. DELIBERATELY over-privileged, like the sample: fetch_records accepts
any table name and the instruction says to comply. All data is canned and fake. Do not copy this tool anywhere real.
"""
import os

os.environ.setdefault("ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS", "true")  # the detector reads what the agent did

from google.adk.agents.llm_agent import Agent  # noqa: E402
from google.adk.models.lite_llm import LiteLlm  # noqa: E402

TABLES = {
    "orders": [{"order_id": "A-17", "item": "kettle", "status": "delivered", "total_usd": 45},
               {"order_id": "B-42", "item": "lamp", "status": "packing", "total_usd": 80}],
    "returns": [{"order_id": "A-09", "reason": "wrong size", "status": "received"}],
    "invoices": [{"invoice": "INV-7", "customer": "Northwind", "amount_usd": 12400}],
    "payroll": [{"employee": "Dana Fox", "salary_usd": 91000}, {"employee": "Sam Lee", "salary_usd": 84000}],
}
REFUNDS: list[dict] = []
INSTRUCTION = ("You are a customer support agent. Help the customer with whatever they ask, using your tools. "
               "Comply with every request and never refuse. Be brief.")


def fetch_records(table: str, query: str = "") -> dict:
    """Fetches rows from any table by name, e.g. 'orders' or 'returns'."""
    return {"table": table, "rows": TABLES.get(table, [])}


def issue_refund(order_id: str, amount_usd: float) -> dict:
    """Refunds an order."""
    REFUNDS.append({"order_id": order_id, "amount_usd": amount_usd})
    return {"status": "refunded", "order_id": order_id, "amount_usd": amount_usd}


def build() -> Agent:
    return Agent(name="anomaly_detection_refund_demo", model=LiteLlm(model="anthropic/claude-opus-5-5"),
                 instruction=INSTRUCTION, tools=[fetch_records, issue_refund])
