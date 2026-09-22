from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import stripe

from payments_api.config import Settings


class InvalidStripeResponse(RuntimeError):
    """Raised when Stripe omits or returns an unsafe Checkout destination."""


@dataclass(frozen=True)
class HostedCheckout:
    session_id: str
    url: str


class StripeGateway:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = stripe.StripeClient(settings.stripe_secret_key)

    def create_subscription_checkout(self, checkout_reference: str) -> HostedCheckout:
        session = self._client.v1.checkout.sessions.create(
            {
                "mode": "subscription",
                "line_items": [{"price": self._settings.price_id, "quantity": 1}],
                "managed_payments": {"enabled": True},
                "success_url": (
                    f"{self._settings.checkout_base_url}/?checkout=success"
                    "&session_id={CHECKOUT_SESSION_ID}"
                ),
                "cancel_url": (
                    f"{self._settings.checkout_base_url}/?checkout=cancelled"
                ),
                "client_reference_id": checkout_reference,
                "metadata": {"product": "tickerpulse", "environment": "sandbox"},
                "integration_identifier": self._settings.integration_identifier,
            }
        )
        session_id = _field(session, "id")
        url = _field(session, "url")
        if not _is_allowed_checkout_url(url):
            raise InvalidStripeResponse("Stripe returned an unsafe Checkout URL")
        return HostedCheckout(session_id=session_id, url=url)


def _field(value: Any, name: str) -> str:
    result = getattr(value, name, None)
    if result is None and isinstance(value, dict):
        result = value.get(name)
    if not isinstance(result, str) or not result:
        raise InvalidStripeResponse(f"Stripe response is missing {name}")
    return result


def _is_allowed_checkout_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname == "checkout.stripe.com"
        and parsed.username is None
        and parsed.password is None
    )
