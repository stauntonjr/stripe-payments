from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import stripe

from payments_api.config import Settings
from payments_api.stripe_gateway import StripeGateway


class StripeGatewayTests(unittest.TestCase):
    def test_checkout_uses_blueprint_parameters_and_preview_version(self) -> None:
        create = Mock(
            return_value=SimpleNamespace(
                id="cs_test_123",
                url="https://checkout.stripe.com/c/pay/test",
            )
        )
        client = SimpleNamespace(
            v1=SimpleNamespace(
                checkout=SimpleNamespace(sessions=SimpleNamespace(create=create))
            )
        )
        settings = Settings.from_mapping(
            {
                "STRIPE_SECRET_KEY": "rk_test_example",
                "STRIPE_WEBHOOK_SECRET": "whsec_example",
                "STRIPE_TICKERPULSE_PRICE_ID": "price_1UIW1FJMVS0qQfgEkAA4kLPY",
                "STRIPE_INTEGRATION_IDENTIFIER": "tickerpulse_fastapi_qzrmhptk",
                "CHECKOUT_BASE_URL": "https://pay.ediacarian.dedyn.io",
                "SQLITE_PATH": ":memory:",
            }
        )

        with patch("payments_api.stripe_gateway.stripe.StripeClient", return_value=client):
            gateway = StripeGateway(settings)
            hosted = gateway.create_subscription_checkout("checkout-reference")

        self.assertEqual(hosted.session_id, "cs_test_123")
        params, = create.call_args.args
        self.assertEqual(params["mode"], "subscription")
        self.assertEqual(
            params["line_items"],
            [{"price": "price_1UIW1FJMVS0qQfgEkAA4kLPY", "quantity": 1}],
        )
        self.assertEqual(params["managed_payments"], {"enabled": True})
        self.assertEqual(params["client_reference_id"], "checkout-reference")
        self.assertEqual(
            params["integration_identifier"], "tickerpulse_fastapi_qzrmhptk"
        )
        self.assertEqual(
            create.call_args.kwargs,
            {"options": {"stripe_version": "2026-02-25.preview"}},
        )
        self.assertNotIn("payment_method_types", params)
        self.assertNotIn("automatic_tax", params)

    def test_verified_sdk_event_is_normalized_to_plain_mappings(self) -> None:
        sdk_event = stripe.Event.construct_from(
            {
                "id": "evt_test_123",
                "type": "checkout.session.completed",
                "data": {"object": {"id": "cs_test_123"}},
            },
            "rk_test_example",
        )
        with patch(
            "payments_api.stripe_gateway.stripe.Webhook.construct_event",
            return_value=sdk_event,
        ):
            gateway = StripeGateway(self._settings())

            event = gateway.construct_event(b"{}", "t=123,v1=signature")

        self.assertIsInstance(event, dict)
        self.assertEqual(event.get("type"), "checkout.session.completed")
        self.assertIsInstance(event.get("data"), dict)

    @staticmethod
    def _settings() -> Settings:
        return Settings.from_mapping(
            {
                "STRIPE_SECRET_KEY": "rk_test_example",
                "STRIPE_WEBHOOK_SECRET": "whsec_example",
                "STRIPE_TICKERPULSE_PRICE_ID": "price_1UIW1FJMVS0qQfgEkAA4kLPY",
                "STRIPE_INTEGRATION_IDENTIFIER": "tickerpulse_fastapi_qzrmhptk",
                "CHECKOUT_BASE_URL": "https://pay.ediacarian.dedyn.io",
                "SQLITE_PATH": ":memory:",
            }
        )


if __name__ == "__main__":
    unittest.main()
