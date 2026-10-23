"""Day 16 red-team suite (no model): the course's nine checks plus three more. Each row is
(attack, expected outcome, actual outcome). Run from the repo root:
  uv run python day16/redteam.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import merchant as m  # noqa: E402
import trusted_platform as tp  # noqa: E402
import ucp  # noqa: E402


def _try(fn) -> str:
    try:
        r = fn()
        return r.get("status", "ok") if isinstance(r, dict) else "ok"
    except m.CheckoutError as e:
        return e.code
    except tp.MandateRefused as e:
        return "platform refused: " + e.code


def run() -> list[tuple[str, str, str]]:
    shop = m.make_merchants()["meridian"]
    url = shop.profile_url

    def cart(qty=2, ticket="standard"):
        return shop.create_checkout("Oppenheimer", "9:30 PM", ticket, qty)

    def pay(co, cm, pm, amount):
        return shop.complete_checkout(co["id"], cm, {"amount_cents": amount, "credential_token": pm})

    rows = []
    a = cart()
    cm, pm = tp.sign_mandates(a, url, a["total_cents"])
    rows.append(("Honest purchase", "completed", _try(lambda: pay(a, cm, pm, a["total_cents"]))))
    rows.append(("Replay used mandates", "checkout_already_completed", _try(lambda: pay(a, cm, pm, a["total_cents"]))))

    b = shop.create_checkout("Dune: Part Two", "7:00 PM", "standard", 3)  # $47.52
    cm1, pm1 = tp._mint(b, 100)  # genuinely signed, but for $1
    rows.append((f"Pay $1 for a ${b['total_cents'] / 100:.2f} cart", "mandate_scope_mismatch",
                 _try(lambda: pay(b, cm1, pm1, 100))))

    c, d = cart(), cart()
    cmc, pmc = tp.sign_mandates(c, url, c["total_cents"])
    rows.append(("Reuse approval on another cart", "mandate_scope_mismatch", _try(lambda: pay(d, cmc, pmc, d["total_cents"]))))

    e = cart()
    evil = ucp.new_key()
    ucp.publish("https://evil.example/.well-known/ucp", "Evil platform", evil)
    claims = ucp.unverified_claims(tp._mint(e, e["total_cents"])[0])
    forged_untrusted = [ucp.sign(evil, {**claims, "iss": "https://evil.example/.well-known/ucp", "typ": t})
                        for t in ("checkout_mandate", "payment_mandate")]
    rows.append(("Untrusted platform profile", "agent_missing_key",
                 _try(lambda: pay(e, *forged_untrusted, e["total_cents"]))))
    forged_trusted = [ucp.sign(evil, {**claims, "typ": t}) for t in ("checkout_mandate", "payment_mandate")]
    rows.append(("Forged key with trusted profile URL", "mandate_invalid_signature",
                 _try(lambda: pay(e, *forged_trusted, e["total_cents"]))))

    f = cart()
    cmx, pmx = tp._mint(f, f["total_cents"], ttl=-1)
    rows.append(("Expired mandate", "mandate_expired", _try(lambda: pay(f, cmx, pmx, f["total_cents"]))))
    rows.append(("No mandate (approval skipped)", "mandate_required", _try(lambda: pay(f, None, None, f["total_cents"]))))

    g = cart()
    rows.append(("Approved amount differs from signed total", "platform refused: amount_mismatch",
                 _try(lambda: tp.sign_mandates(g, url, g["total_cents"] - 1000))))

    # three more
    h = cart()
    h_tampered = {**h, "total_cents": 100, "line_items": [{**h["line_items"][0], "unit_cents": 50}]}
    rows.append(("Agent edits the cart after the merchant signed it", "platform refused: cart_tampered",
                 _try(lambda: tp.sign_mandates(h_tampered, url, 100))))
    i = cart()
    cmi, pmi = tp.sign_mandates(i, url, i["total_cents"])
    rows.append(("Swap checkout and payment mandates", "mandate_invalid_signature", _try(lambda: pay(i, pmi, cmi, i["total_cents"]))))
    j = cart()
    rows.append(("Cart signed by a different merchant's key", "platform refused: merchant_signature_invalid",
                 _try(lambda: tp.sign_mandates(j, m.make_merchants()["starlight"].profile_url, j["total_cents"]))))
    return rows


if __name__ == "__main__":
    t = time.time()
    rows = run()
    for name, want, got in rows:
        print(f"  {'PASS' if want == got else 'FAIL'}  {name:<50} -> {got}")
    passed = sum(w == g for _, w, g in rows)
    print(f"\n{passed}/{len(rows)} checks passed in {time.time() - t:.2f}s")
    sys.exit(0 if passed == len(rows) else 1)
