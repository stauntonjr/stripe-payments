from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from payments_api.config import Settings
from payments_api.main import create_app
from payments_api.store import CheckoutStore
from payments_api.stripe_gateway import HostedCheckout


class FakeStripeGateway:
    def __init__(
        self,
        hosted: HostedCheckout | None = None,
        error: Exception | None = None,
    ) -> None:
        self.hosted = hosted or HostedCheckout(
            session_id="cs_test_123",
            url="https://checkout.stripe.com/c/pay/test",
        )
        self.error = error
        self.references: list[str] = []

    def create_subscription_checkout(self, checkout_reference: str) -> HostedCheckout:
        self.references.append(checkout_reference)
        if self.error is not None:
            raise self.error
        return self.hosted


class CheckoutApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.store = CheckoutStore(str(Path(self.tempdir.name) / "payments.sqlite3"))
        self.store.initialize()

    def test_checkout_creation_returns_only_hosted_url_and_persists_session(self) -> None:
        gateway = FakeStripeGateway()
        client = self._client(gateway)

        response = client.post("/api/checkout-sessions")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json(),
            {"checkout_url": "https://checkout.stripe.com/c/pay/test"},
        )
        self.assertEqual(len(gateway.references), 1)
        record = self.store.get_checkout(gateway.references[0])
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.state, "pending")
        self.assertEqual(record.session_id, "cs_test_123")

    def test_each_checkout_request_gets_a_distinct_reference(self) -> None:
        gateway = FakeStripeGateway()
        client = self._client(gateway)

        self.assertEqual(client.post("/api/checkout-sessions").status_code, 201)
        gateway.hosted = HostedCheckout(
            session_id="cs_test_456",
            url="https://checkout.stripe.com/c/pay/second",
        )
        self.assertEqual(client.post("/api/checkout-sessions").status_code, 201)

        self.assertEqual(len(set(gateway.references)), 2)

    def test_gateway_failure_is_generic_and_marks_checkout_failed(self) -> None:
        gateway = FakeStripeGateway(error=RuntimeError("secret diagnostic detail"))
        client = self._client(gateway)

        response = client.post("/api/checkout-sessions")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"detail": "Checkout is temporarily unavailable."})
        self.assertNotIn("secret diagnostic detail", response.text)
        record = self.store.get_checkout(gateway.references[0])
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.state, "creation_failed")

    def test_non_stripe_checkout_url_is_rejected_and_marked_failed(self) -> None:
        gateway = FakeStripeGateway(
            hosted=HostedCheckout(
                session_id="cs_test_123",
                url="https://attacker.example/checkout",
            )
        )
        client = self._client(gateway)

        response = client.post("/api/checkout-sessions")

        self.assertEqual(response.status_code, 502)
        record = self.store.get_checkout(gateway.references[0])
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.state, "creation_failed")

    def test_health_check_confirms_database_readiness(self) -> None:
        client = self._client(FakeStripeGateway())

        response = client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def _client(self, gateway: FakeStripeGateway) -> TestClient:
        settings = Settings.from_mapping(
            {
                "STRIPE_SECRET_KEY": "rk_test_example",
                "STRIPE_WEBHOOK_SECRET": "whsec_example",
                "STRIPE_TICKERPULSE_PRICE_ID": "price_1UIW1FJMVS0qQfgEkAA4kLPY",
                "STRIPE_INTEGRATION_IDENTIFIER": "tickerpulse_fastapi_qzrmhptk",
                "CHECKOUT_BASE_URL": "https://pay.ediacarian.dedyn.io",
                "SQLITE_PATH": str(Path(self.tempdir.name) / "payments.sqlite3"),
            }
        )
        return TestClient(create_app(settings, gateway, self.store))


if __name__ == "__main__":
    unittest.main()
