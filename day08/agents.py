"""Two agents with the same tools. What they may actually do is decided by the gateway policy
and their identity, not by their prompts. The support agent's prompt is deliberately permissive."""
import sys
from pathlib import Path

from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "day05"))
import gateway  # noqa: E402
import iam_lib  # noqa: E402

MODEL = LiteLlm(model="anthropic/claude-opus-5-5")


def _tools(agent_token: str) -> list:
    def lookup_order(order_id: str) -> dict:
        """Checks an order's status and tracking."""
        return gateway.call(agent_token, "orders-mcp", "lookup_order", {"order_id": order_id})

    def issue_refund(order_id: str, amount: float) -> dict:
        """Refunds money on an order."""
        return gateway.call(agent_token, "orders-mcp", "issue_refund", {"order_id": order_id, "amount": amount})

    def delete_account(customer_id: str) -> dict:
        """Permanently deletes a customer account."""
        return gateway.call(agent_token, "orders-mcp", "delete_account", {"customer_id": customer_id})

    def send_to_url(url: str, data: str) -> dict:
        """Sends data to an external web address."""
        return gateway.call(agent_token, url, "http_post", {"data": data})

    return [lookup_order, issue_refund, delete_account, send_to_url]


def build(name: str, instruction: str) -> Agent:
    return Agent(model=MODEL, name=name, description=f"{name} (Day 8 demo)",
                 instruction=instruction, tools=_tools(iam_lib.mint(name)))


def support_agent() -> Agent:
    return build("support_agent",
                 "You are a customer support agent. Do what the customer asks using your tools. "
                 "If a tool is blocked, report the error exactly.")


def refunds_agent() -> Agent:
    return build("refunds_agent",
                 "You process approved refunds. Use your tools as instructed. If a tool is blocked, report the error exactly.")
