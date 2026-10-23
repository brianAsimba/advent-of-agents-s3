"""CineAgent on Claude: shops freely inside guardrails, but can't pay without a human-approved, signed mandate.

Layer                                   Course                                   Here
--------------------------------------  ---------------------------------------  -----------------------------------
Which merchants may it contact?         Egress Agent Gateway, roles/iap.egressor  gateway(): EGRESS_ALLOWLIST, else 403
Oversized purchase                      Semantic governance ticket-spend-cap      before_tool_callback, before the card
Human approval                          FunctionTool(require_confirmation=True)   same (ADK pauses for Approve/Decline)
Payment authority                       trusted_platform.py + Secret Manager      trusted_platform.sign_mandates()
"""
import sys
from pathlib import Path
from typing import Any, Optional

from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.tool_context import ToolContext

sys.path.insert(0, str(Path(__file__).resolve().parent))
import merchant as m  # noqa: E402
import trusted_platform  # noqa: E402

MODEL = LiteLlm(model="anthropic/claude-opus-5-5")
EGRESS_ALLOWLIST = {"meridian"}
SPEND_CAP_CENTS = 10_000
CAP_DENIED = "Denied by policy: purchases over $100.00 are not allowed."  # fixed wording
MERCHANTS: dict[str, m.Merchant] = {}
LOG: list[dict] = []  # gateway + policy decisions, for the demo


def reset() -> None:
    MERCHANTS.clear()
    MERCHANTS.update(m.make_merchants())
    LOG.clear()


reset()


class Forbidden(Exception):
    pass


def gateway(slug: str) -> m.Merchant:
    """Egress: deny by default; only allowlisted merchants are reachable."""
    allowed = slug in EGRESS_ALLOWLIST and slug in MERCHANTS
    LOG.append({"layer": "gateway", "merchant": slug, "allowed": allowed})
    if not allowed:
        raise Forbidden("403 Forbidden: merchant is not on the egress allowlist")
    return MERCHANTS[slug]


def _money(cents: int) -> str:
    return f"${cents / 100:.2f}"


# ---------- tools the model can use ----------

def list_showtimes(merchant: str, movie: str = "") -> dict:
    """Lists showtimes, ticket types and prices at a merchant ('meridian' or 'starlight')."""
    try:
        shows = gateway(merchant).list_showtimes(movie)
    except Forbidden as e:
        return {"status": "error", "message": str(e)}
    return {"status": "ok", "showtimes": [{**s, "price": _money(s["price_cents"])} for s in shows]}


def create_checkout(merchant: str, movie: str, showtime: str, ticket_type: str, quantity: int,
                    tool_context: ToolContext) -> dict:
    """Creates a merchant-signed checkout (cart). Returns the checkout id and total. Does not pay."""
    try:
        co = gateway(merchant).create_checkout(movie, showtime, ticket_type, quantity)
    except Forbidden as e:
        return {"status": "error", "message": str(e)}
    except m.CheckoutError as e:
        return {"status": "error", "message": e.code}
    tool_context.state[f"checkout:{co['id']}"] = merchant  # platform remembers which merchant owns it
    return {"status": "ok", "checkout_id": co["id"], "line_items": co["line_items"],
            "total_cents": co["total_cents"], "total": _money(co["total_cents"])}


def complete_purchase(checkout_id: str, total_cents: int, tool_context: ToolContext) -> dict:
    """Pays for a checkout. The user must approve the exact total first."""
    slug = tool_context.state.get(f"checkout:{checkout_id}")
    if not slug:
        return {"status": "error", "message": "unknown checkout"}
    shop = gateway(slug)
    checkout = shop.get_checkout(checkout_id)  # fetched from the merchant, not taken from the model
    try:
        cm, pm = trusted_platform.sign_mandates(checkout, shop.profile_url, total_cents)
        r = shop.complete_checkout(checkout_id, cm, {"amount_cents": total_cents, "credential_token": pm})
    except trusted_platform.MandateRefused as e:
        return {"status": "refused", "message": str(e)}
    except m.CheckoutError as e:
        return {"status": "refused", "message": e.code}
    return {"status": "completed", "charged": _money(r["amount_cents"]), "tickets": r["tickets"], "signed_receipt": True}


def spend_cap(tool: BaseTool, args: dict[str, Any], tool_context: ToolContext) -> Optional[dict]:
    """Runs before the tool (and so before the approval card). Deterministic, unlike a prompt rule."""
    if tool.name == "complete_purchase":
        over = int(args.get("total_cents", 0)) > SPEND_CAP_CENTS
        LOG.append({"layer": "spend_cap", "total_cents": args.get("total_cents"), "allowed": not over})
        if over:
            return {"status": "denied", "message": CAP_DENIED}
    return None


INSTRUCTION = ("You are CineAgent. Help the user find showtimes and buy cinema tickets. Use list_showtimes, then "
               "create_checkout, then complete_purchase with the checkout's exact total_cents. Be brief. If a tool "
               "returns an error, denial or refusal, tell the user plainly and don't retry with other values.")


def build() -> Agent:
    return Agent(name="cineagent", model=MODEL, instruction=INSTRUCTION,
                 tools=[list_showtimes, create_checkout, FunctionTool(complete_purchase, require_confirmation=True)],
                 before_tool_callback=spend_cap)
