# Day 16 — Agent Payments: Secure Shopping
[Page](https://adventofagents.com/2026/10/16) · [Video: Sita Lakshmi Sangameswaran (9 min)](https://www.youtube.com/watch?v=3Q1L4z5-6ug) · [Demo repo](https://github.com/Sita04/secure-agent-commerce-gemini-enterprise) · [AP2 spec](https://g.dev/cloud/adventofagents-season3-docs-ap2-specification) · [UCP AP2 mandates](https://g.dev/cloud/adventofagents-season3-docs-ucp-ap2-mandates) · [ADK tool confirmation](https://g.dev/cloud/adventofagents-season3-docs-adk-tool-confirmation)

## Core idea
**Shopping ≠ paying.** The model may browse catalogs and build a cart. Paying requires cryptographic proof that a human approved **this exact cart**, produced by deterministic code holding a key the model never sees. A prompt rule ("always ask before paying") can be bypassed; a signature check can't.

## The flow (CineAgent)
1. **Egress gateway, deny by default:** only approved merchants are reachable (StarLight → `403`).
2. **Merchant-signed cart (UCP):** the merchant locks the line items and total and signs them (`ap2.merchant_authorization`). Its public key is in its `/.well-known/ucp` profile.
3. **Spend cap before the card:** the governance policy denies `complete_purchase` over $100 *before* the human ever sees a card, so nobody is asked to approve something policy forbids.
4. **Human approval:** ADK pauses (`require_confirmation=True`) and shows an Approve/Decline card, outside the model.
5. **Deterministic mandates (AP2):** on Approve, platform code verifies the merchant's signature, checks the approved amount equals the signed total, and signs two **single-use, short-lived** mandates (Checkout + Payment) bound to the cart hash.
6. **Merchant verifies:** it loads the platform key from its **allowlisted** profile (never from the request), then checks expiry, single use, cart hash and amount, and returns a signed receipt.

## What my run showed (2026-10-22, on Claude)
- Red team 12/12: the course's nine attacks (replay, $1 for $47.52, approval reused on another cart, untrusted profile, forged key, expired, missing mandate, amount ≠ total) plus cart edited after signing, mandates swapped, and the wrong merchant's key.
- $32.40 approved → paid; declined → $0; $118.80 → spend cap, **no card shown**; StarLight → `403`.
- Claude asked "Should I pay?" in chat first. That's fine, but a chat "yes" is just text; the card is what authorizes payment.

## Why each check exists
| Attack | Stopped by |
|---|---|
| Agent edits the price | Merchant's signature on the cart |
| Pay less than the cart total | Mandate bound to amount + cart hash |
| Reuse one approval for a second cart | Mandate bound to the cart hash |
| Replay a used mandate | Merchant marks the checkout completed (single use) |
| Attacker signs their own mandate | Key loaded from the allowlisted profile, not the payload |
| Old approval used later | Short expiry |

## Connections
- **Barber pilot (Camp III):** deposits or no-show fees: the agent proposes, the customer approves in a non-agentic UI (a Stripe Checkout link), and a server webhook, not the model, confirms payment. Same split: the model never holds payment authority.
- **Trading desk (Camp VI):** the same pattern as an order mandate. The risk manager or a human signs the exact order (ticker, qty, limit), and the executor checks the signature, amount and single use before sending it to the paper broker. Max order size stays a deterministic cap before approval.
- **SMB clients:** any invoice/refund automation should use approve-then-sign with amount binding, never "the model said yes".

## Check yourself
- Why can't a prompt rule be the payment safeguard?
- What does the merchant's cart signature protect against?
- Why does the spend cap run before the approval card?
- Why does the merchant take the platform's key from its allowlist and not from the request?
- Which two values bind a mandate to one cart?
