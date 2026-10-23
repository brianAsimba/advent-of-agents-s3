"""Day 16 shared pieces: Ed25519-signed tokens, cart hashing, and the published UCP profiles.

What Google Cloud / the protocols do                 What this file does (teaching model, not the full specs)
---------------------------------------------------  ------------------------------------------------------------
Merchant publishes /.well-known/ucp with public key  PROFILES: profile URL -> {name, public_key}, like hosted JSON
ap2.merchant_authorization JWT over the cart          sign(merchant_key, {cart_hash, total_cents, ...})
Single-use SD-JWT Checkout + Payment Mandates          sign(platform_key, {typ, cart_hash, amount_cents, exp, jti})
SHA-256 of the signed checkout                          cart_hash(): SHA-256 of the canonical cart JSON
"""
import base64
import hashlib
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

PROFILES: dict[str, dict] = {}  # profile URL -> published profile (what an HTTPS GET of /.well-known/ucp returns)


class BadSignature(Exception):
    pass


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def new_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def public_hex(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


def publish(url: str, name: str, key: Ed25519PrivateKey) -> None:
    PROFILES[url] = {"name": name, "public_key": public_hex(key)}


def sign(key: Ed25519PrivateKey, claims: dict) -> str:
    body = _b64(canonical(claims))
    return f"{body}.{_b64(key.sign(body.encode()))}"


def unverified_claims(token: str) -> dict:
    """Reads claims WITHOUT checking the signature (only to find out who claims to have signed it)."""
    return json.loads(_unb64(token.split(".")[0]))


def verify(public_key_hex: str, token: str) -> dict:
    try:
        body, sig = token.split(".")
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex)).verify(_unb64(sig), body.encode())
    except (ValueError, InvalidSignature) as e:
        raise BadSignature("signature does not verify") from e
    return json.loads(_unb64(body))


def cart_hash(checkout: dict) -> str:
    """Hash of what the merchant locked: id, merchant, line items, total. Not the signature itself."""
    locked = {k: checkout[k] for k in ("id", "merchant", "line_items", "total_cents")}
    return hashlib.sha256(canonical(locked)).hexdigest()
