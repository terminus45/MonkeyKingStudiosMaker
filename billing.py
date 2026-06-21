"""billing.py — Stripe integration for Phase 1.

Lazily imports `stripe` at call time so the app boots without it when BILLING_ENABLED=false.
All pricing is server-authoritative: the client sends only package_id; coins and price
are always read from PACKAGES on the server. The webhook re-derives coins from metadata
using the same table — it never trusts a client-supplied coin count.

Stripe setup (local dev):
  1. Install: pip install stripe
  2. Set env: STRIPE_SECRET_KEY=sk_test_...
              STRIPE_WEBHOOK_SECRET=whsec_...  (from `stripe listen` output)
              STRIPE_SUCCESS_URL=http://localhost:8000/account.html?return=success
              STRIPE_CANCEL_URL=http://localhost:8000/account.html?return=cancel
  3. Forward webhooks: stripe listen --forward-to localhost:8000/stripe/webhook
  4. Test: stripe trigger checkout.session.completed
"""

from typing import Optional

from config import (
    STRIPE_CANCEL_URL,
    STRIPE_SECRET_KEY,
    STRIPE_SUCCESS_URL,
    STRIPE_WEBHOOK_SECRET,
)
import billing_db

# ── Package catalog (server-authoritative) ────────────────────────────────────
# Format: package_id -> (coins, price_cents)
# 100 coins = $1 → coins == price_cents numerically (1 coin per cent).
# Promo packs (different ratio) are allowed here in Phase 2 by changing coins alone.

PACKAGES: dict[str, tuple[int, int]] = {
    "p5":  (500,  500),   # $5 → 500 coins
    "p10": (1000, 1000),  # $10 → 1,000 coins
    "p20": (2000, 2000),  # $20 → 2,000 coins
}

_PACKAGE_META = {
    "p5":  {"display_name": "$5 — 500 coins",   "tag": "Starter pack"},
    "p10": {"display_name": "$10 — 1,000 coins", "tag": "Most popular"},
    "p20": {"display_name": "$20 — 2,000 coins", "tag": "Best value"},
}


def package_catalog() -> list[dict]:
    """Return the public package list for GET /billing/packages."""
    result = []
    for pkg_id, (coins, price_cents) in PACKAGES.items():
        meta = _PACKAGE_META.get(pkg_id, {})
        result.append({
            "id": pkg_id,
            "display_name": meta.get("display_name", pkg_id),
            "tag": meta.get("tag", ""),
            "coins": coins,
            "price_cents": price_cents,
        })
    return result


# ── Stripe checkout session creation ─────────────────────────────────────────

def create_checkout_session(profile_id: str, package_id: str) -> str:
    """Create a Stripe Checkout session for the given package and return the URL.

    Raises:
        ValueError: if package_id is not in PACKAGES.
        RuntimeError: if STRIPE_SECRET_KEY is not configured (caller should 503).
    """
    if not STRIPE_SECRET_KEY:
        raise RuntimeError(
            "STRIPE_SECRET_KEY is not configured. "
            "Set it in your .env file or environment."
        )

    if package_id not in PACKAGES:
        raise ValueError(f"Unknown package_id: {package_id!r}")

    coins, price_cents = PACKAGES[package_id]

    # Lazy import — only reached when billing is enabled and key is set.
    import stripe  # noqa: PLC0415
    stripe.api_key = STRIPE_SECRET_KEY

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "unit_amount": price_cents,
                    "product_data": {
                        "name": f"{coins:,} MonkeyKing Coins",
                        "description": f"100 coins = $1 · Coins never expire",
                    },
                },
                "quantity": 1,
            }
        ],
        success_url=STRIPE_SUCCESS_URL,
        cancel_url=STRIPE_CANCEL_URL,
        # profile_id + package_id echoed back in webhook so we can credit server-side.
        client_reference_id=profile_id,
        metadata={
            "profile_id": profile_id,
            "package_id": package_id,
            # Informational only — webhook re-derives coins from PACKAGES[package_id].
            "coins_hint": str(coins),
        },
    )

    return session.url


# ── Stripe webhook handler ────────────────────────────────────────────────────

def handle_webhook(payload_bytes: bytes, sig_header: Optional[str]) -> None:
    """Verify a Stripe webhook and process checkout.session.completed events.

    Must receive the RAW request body (not parsed JSON) — Stripe computes the HMAC
    over the raw bytes, and parsing before verification breaks the signature.

    Raises:
        ValueError: on signature verification failure (caller should return 400).
        RuntimeError: if STRIPE_WEBHOOK_SECRET is not configured.
    """
    if not STRIPE_WEBHOOK_SECRET:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET is not configured.")

    import stripe  # noqa: PLC0415
    stripe.api_key = STRIPE_SECRET_KEY

    try:
        event = stripe.Webhook.construct_event(
            payload_bytes, sig_header or "", STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError as exc:
        raise ValueError(f"Stripe signature verification failed: {exc}") from exc

    # Only process checkout.session.completed
    if event["type"] != "checkout.session.completed":
        # Other event types acknowledged but not acted on.
        return

    session = event["data"]["object"]

    # Guard: only credit when payment is actually paid (not just open/expired).
    if session.get("payment_status") != "paid":
        return

    # Resolve profile_id and package from server-side metadata.
    # IMPORTANT: we re-derive coins from PACKAGES — never trust the client or metadata.
    meta = session.get("metadata") or {}
    profile_id = meta.get("profile_id") or session.get("client_reference_id")
    package_id = meta.get("package_id")

    if not profile_id or not package_id:
        raise ValueError(
            f"Webhook missing profile_id or package_id in metadata: {meta!r}"
        )
    if package_id not in PACKAGES:
        raise ValueError(f"Webhook has unknown package_id: {package_id!r}")

    coins, _ = PACKAGES[package_id]  # authoritative coin count from server

    # `credit_coins` is the single source of idempotency: keyed on the Stripe
    # event id, a retry (or a crash-and-redeliver) credits EXACTLY once. We do
    # NOT short-circuit on the stripe_events table — doing so before the credit
    # commits could mark an event "seen" yet never credit it (money lost to the
    # customer on a crash between the two writes). The stripe_events row is
    # best-effort observability only, written AFTER the credit commits.
    billing_db.credit_coins(
        profile_id=profile_id,
        amount=coins,
        reason="stripe_purchase",
        stripe_event_id=event["id"],
        idempotency_key=f"stripe:{event['id']}",
    )

    try:
        billing_db.record_stripe_event(event["id"])      # insert if new (idempotent)
        billing_db.update_stripe_event_status(event["id"], "applied")
    except Exception:
        pass  # observability only — must never fail or undo a committed credit
