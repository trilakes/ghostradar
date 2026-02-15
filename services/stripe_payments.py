import os
import stripe

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

APP_URL = os.environ.get("APP_URL", "http://localhost:5000")
PRICE_MONTHLY = os.environ.get("STRIPE_PRICE_MONTHLY")
PRICE_LIFETIME = os.environ.get("STRIPE_PRICE_LIFETIME")


def create_checkout_session(user_id: str, plan: str) -> str:
    """Create a Stripe Checkout session and return the URL."""
    price_id = PRICE_MONTHLY if plan == "monthly" else PRICE_LIFETIME
    mode = "subscription" if plan == "monthly" else "payment"

    session = stripe.checkout.Session.create(
        mode=mode,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{APP_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{APP_URL}/cancel",
        metadata={"user_id": str(user_id), "plan": plan},
    )
    return session.url, session.id


def verify_session(session_id: str) -> dict | None:
    """Retrieve a Stripe Checkout session to verify payment."""
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == "paid":
            return {
                "user_id": session.metadata.get("user_id"),
                "plan": session.metadata.get("plan"),
            }
    except Exception:
        pass
    return None


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    """Construct and verify a Stripe webhook event."""
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
