"""Deterministic platform code: the only place payment authority lives. The model never sees this key.

sign_mandates() mirrors the course's trusted_platform.py:
  1. verify the merchant's ap2.merchant_authorization against the merchant's published UCP profile
  2. confirm the amount the human approved equals the merchant-signed total
  3. sign two single-use, short-lived mandates bound to the cart hash and amount
"""
import time
import uuid

import ucp
from merchant import PLATFORM_PROFILE

MANDATE_TTL = 300  # seconds
_KEY = ucp.new_key()  # in the course: Secret Manager. Here: process memory, never returned by a tool.
ucp.publish(PLATFORM_PROFILE, "Brian's agent platform", _KEY)


class MandateRefused(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code


def _mint(checkout: dict, amount_cents: int, ttl: int = MANDATE_TTL) -> tuple[str, str]:
    base = {"iss": PLATFORM_PROFILE, "checkout_id": checkout["id"], "cart_hash": ucp.cart_hash(checkout),
            "amount_cents": amount_cents, "exp": int(time.time() + ttl)}
    return (ucp.sign(_KEY, {**base, "typ": "checkout_mandate", "jti": uuid.uuid4().hex}),
            ucp.sign(_KEY, {**base, "typ": "payment_mandate", "jti": uuid.uuid4().hex}))


def sign_mandates(checkout: dict, merchant_profile_url: str, approved_cents: int) -> tuple[str, str]:
    profile = ucp.PROFILES.get(merchant_profile_url)
    if profile is None:
        raise MandateRefused("merchant_unknown", "merchant has no published UCP profile")
    try:
        auth = ucp.verify(profile["public_key"], checkout.get("merchant_authorization", ""))
    except ucp.BadSignature:
        raise MandateRefused("merchant_signature_invalid", "merchant signature on the cart does not verify")
    if auth["cart_hash"] != ucp.cart_hash(checkout) or auth["total_cents"] != checkout["total_cents"]:
        raise MandateRefused("cart_tampered", "cart was changed after the merchant signed it")
    if approved_cents != auth["total_cents"]:
        raise MandateRefused("amount_mismatch", f"approved amount {approved_cents} differs from the signed total {auth['total_cents']}")
    return _mint(checkout, approved_cents)
