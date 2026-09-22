from __future__ import annotations

import logging
from typing import Protocol
from urllib.parse import urlsplit
import uuid

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from payments_api.config import Settings
from payments_api.store import CheckoutStore
from payments_api.stripe_gateway import HostedCheckout


logger = logging.getLogger(__name__)


class CheckoutGateway(Protocol):
    def create_subscription_checkout(self, checkout_reference: str) -> HostedCheckout:
        """Create one hosted subscription Checkout Session."""


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
