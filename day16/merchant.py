"""Two UCP cinema merchants (fake, test money only). Each signs its carts and verifies mandates itself.

complete_checkout() mirrors the course's merchant/main.py:
  - rejects completed sessions, so mandates are single use
  - requires both mandates
  - loads the platform's public key from an ALLOWLISTED profile URL, never from the request
  - checks both mandates are unexpired and bound to this cart's hash and amount
"""
import time
import uuid

import ucp

PLATFORM_PROFILE = "https://platform.brian.local/.well-known/ucp"


class CheckoutError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class Merchant:
    def __init__(self, name: str, slug: str, showtimes: list[dict], trusted_platforms=(PLATFORM_PROFILE,)):
        self.name, self.slug = name, slug
        self.profile_url = f"https://{slug}.example/.well-known/ucp"
        self._key = ucp.new_key()
        ucp.publish(self.profile_url, name, self._key)
        self.showtimes = showtimes
        self.trusted_platforms = set(trusted_platforms)
        self.sessions: dict[str, dict] = {}
        self.completed: set[str] = set()

    # ----- catalog -----
    def list_showtimes(self, movie: str = "") -> list[dict]:
        return [s for s in self.showtimes if movie.lower() in s["movie"].lower()]

    # ----- checkout -----
    def create_checkout(self, movie: str, time_: str, ticket_type: str, quantity: int) -> dict:
        show = next((s for s in self.showtimes if s["movie"].lower() == movie.lower()
                     and s["time"] == time_ and s["ticket_type"] == ticket_type), None)
        if show is None or not 1 <= quantity <= 10:
            raise CheckoutError("not_available")
        checkout = {"id": f"co_{uuid.uuid4().hex[:10]}", "merchant": self.name,
                    "line_items": [{"movie": show["movie"], "time": show["time"], "ticket_type": ticket_type,
                                    "quantity": quantity, "unit_cents": show["price_cents"]}],
                    "total_cents": show["price_cents"] * quantity}
        checkout["merchant_authorization"] = ucp.sign(self._key, {"cart_hash": ucp.cart_hash(checkout),
                                                                  "total_cents": checkout["total_cents"]})
        self.sessions[checkout["id"]] = checkout
        return dict(checkout)

    def get_checkout(self, checkout_id: str) -> dict:
        if checkout_id not in self.sessions:
            raise CheckoutError("unknown_checkout")
        return dict(self.sessions[checkout_id])

    def _check_mandate(self, token: str | None, typ: str, checkout: dict, amount_cents: int) -> None:
        if not token:
            raise CheckoutError("mandate_required")
        issuer = ucp.unverified_claims(token).get("iss")
        if issuer not in self.trusted_platforms or issuer not in ucp.PROFILES:
            raise CheckoutError("agent_missing_key")  # no trusted key to check it with
        try:
            claims = ucp.verify(ucp.PROFILES[issuer]["public_key"], token)
        except ucp.BadSignature:
            raise CheckoutError("mandate_invalid_signature")
        if claims.get("typ") != typ:
            raise CheckoutError("mandate_invalid_signature")
        if claims["exp"] < time.time():
            raise CheckoutError("mandate_expired")
        if claims["cart_hash"] != ucp.cart_hash(checkout) or claims["amount_cents"] != amount_cents \
                or amount_cents != checkout["total_cents"]:
            raise CheckoutError("mandate_scope_mismatch")

    def complete_checkout(self, checkout_id: str, checkout_mandate: str | None, payment: dict) -> dict:
        checkout = self.get_checkout(checkout_id)
        if checkout_id in self.completed:
            raise CheckoutError("checkout_already_completed")
        amount = payment.get("amount_cents")
        self._check_mandate(checkout_mandate, "checkout_mandate", checkout, amount)
        self._check_mandate(payment.get("credential_token"), "payment_mandate", checkout, amount)
        self.completed.add(checkout_id)
        tickets = [f"{self.slug.upper()}-{checkout_id[-4:]}-{i + 1}"
                   for i in range(checkout["line_items"][0]["quantity"])]
        receipt = {"checkout_id": checkout_id, "status": "completed", "amount_cents": amount, "tickets": tickets}
        return {**receipt, "receipt": ucp.sign(self._key, receipt)}


SHOWTIMES = [
    {"movie": "Oppenheimer", "time": "9:30 PM", "ticket_type": "standard", "price_cents": 1620},
    {"movie": "Oppenheimer", "time": "9:30 PM", "ticket_type": "imax", "price_cents": 2970},
    {"movie": "Dune: Part Two", "time": "7:00 PM", "ticket_type": "standard", "price_cents": 1584},
]


def make_merchants() -> dict[str, Merchant]:
    return {"meridian": Merchant("Meridian Cinemas", "meridian", SHOWTIMES),
            "starlight": Merchant("StarLight Theaters", "starlight", SHOWTIMES)}
