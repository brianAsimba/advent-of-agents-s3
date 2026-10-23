# Day 16 on Claude: agent payments (the model shops, only signed human approval pays)

Shopping and paying are separate. The model may browse and build a cart; paying needs **cryptographic proof that a human approved this exact cart**. "Always ask before paying" in a prompt can be talked around, so the model never holds payment authority. **Test money only:** both merchants are local fakes.

| Course (Google Cloud, UCP + AP2) | Here |
|---|---|
| Merchant publishes `/.well-known/ucp` with its public key | `ucp.PROFILES` (profile URL → name + Ed25519 public key) |
| Merchant signs the cart (`ap2.merchant_authorization`) | `Merchant.create_checkout` signs the cart hash + total |
| Egress Agent Gateway, deny by default | `cineagent.gateway()`: only `meridian` is allowlisted; StarLight → `403 Forbidden` |
| Semantic governance spend cap (> $100 denied before the card) | `spend_cap` `before_tool_callback`, deterministic, runs before the approval card |
| `FunctionTool(complete_purchase, require_confirmation=True)` | Same; ADK pauses with an `adk_request_confirmation` call |
| `trusted_platform.py` signs single-use Checkout + Payment Mandates (key in Secret Manager) | `trusted_platform.sign_mandates`: key in process memory, never in a tool result |
| Merchant checks mandates: single use, key from allowlisted profile, unexpired, bound to cart hash and amount | `Merchant.complete_checkout` |
| Signed AP2 receipt | Merchant-signed receipt |

Simplification: mandates are compact Ed25519-signed JSON, not full SD-JWTs.

## Run (repo root)
```bash
uv run pytest day16 -q
```
```bash
uv run python day16/redteam.py
```
```bash
uv run python day16/demo.py
```
Add `--interactive` to answer the approval cards yourself. The amount charged is read from the merchants' records, not from the model's reply.

## What my run showed (2026-10-22)
- **Red team: 12/12 passed.** The course's nine checks: honest purchase, replay, $1 for a $47.52 cart, approval reused on another cart, untrusted platform profile, forged key with the trusted profile URL, expired mandate, missing mandate, and approved amount ≠ signed total. Plus three more: the agent edits the cart after signing, the checkout and payment mandates are swapped, and the cart is checked against another merchant's key.
- **Demo:** $32.40 approved → paid, 2 tickets. The same order declined → $0. 4 IMAX ($118.80) → blocked by the spend cap, **no approval card shown**. StarLight → `403`, nothing booked.
- Claude asked "Should I pay $32.40?" in chat before calling the payment tool. Polite, but **a "yes" typed in chat isn't the approval**: the card still appeared and decided, and declining it charged $0.
