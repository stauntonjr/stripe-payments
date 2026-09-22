from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Protocol
from urllib.parse import urlsplit
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from payments_api.config import Settings
from payments_api.store import CheckoutCompletion, CheckoutStore
from payments_api.stripe_gateway import HostedCheckout


logger = logging.getLogger(__name__)


class CheckoutGateway(Protocol):
    def create_subscription_checkout(self, checkout_reference: str) -> HostedCheckout:
        """Create one hosted subscription Checkout Session."""

    def construct_event(
        self,
        payload: bytes,
        signature: str,
    ) -> Mapping[str, object]:
        """Verify and parse a Stripe webhook event."""


def create_app(
    settings: Settings,
    gateway: CheckoutGateway,
    store: CheckoutStore,
) -> FastAPI:
    app = FastAPI(title="TickerPulse payments", docs_url=None, redoc_url=None)

    @app.post("/api/checkout-sessions")
    def create_checkout_session() -> JSONResponse:
        reference = uuid.uuid4().hex
        created = False
        try:
            store.create_checkout(reference)
            created = True
            hosted = gateway.create_subscription_checkout(reference)
            if not _is_allowed_checkout_url(hosted.url):
                raise ValueError("unsafe Checkout destination")
            store.attach_session(reference, hosted.session_id)
        except Exception as error:
            if created:
                try:
                    store.mark_creation_failed(reference)
                except Exception:
                    pass
            logger.error(
                "checkout_creation_failed reference=%s error_type=%s",
                reference,
                type(error).__name__,
            )
            return JSONResponse(
                status_code=502,
                content={"detail": "Checkout is temporarily unavailable."},
            )
        return JSONResponse(status_code=201, content={"checkout_url": hosted.url})

    @app.post("/api/stripe/webhook")
    async def receive_stripe_webhook(request: Request) -> JSONResponse:
        signature = request.headers.get("Stripe-Signature")
        if not signature:
            return JSONResponse(status_code=400, content={"detail": "Invalid webhook."})
        payload = await request.body()
        try:
            event = gateway.construct_event(payload, signature)
        except Exception:
            return JSONResponse(status_code=400, content={"detail": "Invalid webhook."})

        event_type = event.get("type")
        if event_type != "checkout.session.completed":
            return JSONResponse(
                status_code=200,
                content={"received": True, "duplicate": False},
            )

        event_id = event.get("id")
        try:
            data = _required_mapping(event.get("data"))
            checkout = _required_mapping(data.get("object"))
            completion = CheckoutCompletion(
                event_id=_required_string(event_id),
                event_type="checkout.session.completed",
                checkout_reference=_required_string(checkout.get("client_reference_id")),
                session_id=_required_string(checkout.get("id")),
                customer_id=_resource_id(checkout.get("customer")),
                subscription_id=_resource_id(checkout.get("subscription")),
            )
            processed = store.complete_checkout(completion)
        except Exception as error:
            logger.error(
                "webhook_processing_failed event_id=%s error_type=%s",
                event_id if isinstance(event_id, str) else "unknown",
                type(error).__name__,
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Webhook processing failed."},
            )
        return JSONResponse(
            status_code=200,
            content={"received": True, "duplicate": not processed},
        )

    return app


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


def _required_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("expected mapping")
    return value


def _required_string(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("expected non-empty string")
    return value


def _resource_id(value: object) -> str:
    if isinstance(value, str):
        return _required_string(value)
    if isinstance(value, Mapping):
        return _required_string(value.get("id"))
    raise ValueError("expected Stripe resource ID")
