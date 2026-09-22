from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

from payments_api.config import Settings
from payments_api.main import create_app
from payments_api.store import CheckoutStore


COMPLETED_EVENT = {
    "id": "evt_test_123",
    "type": "checkout.session.completed",
    "data": {
        "object": {
            "id": "cs_test_123",
            "client_reference_id": "checkout-ref",
            "customer": "cus_test_123",
            "subscription": "sub_test_123",
        }
    },
}


class FakeWebhookGateway:
    def __init__(self, event: dict[str, object], error: Exception | None = None) -> None:
        self.event = event
        self.error = error

    def construct_event(self, payload: bytes, signature: str) -> dict[str, object]:
        if self.error is not None:
            raise self.error
        return deepcopy(self.event)


class WebhookApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.database = Path(self.tempdir.name) / "payments.sqlite3"
        self.store = CheckoutStore(str(self.database))
        self.store.initialize()

    def test_completed_checkout_persists_all_stripe_identifiers(self) -> None:
        self._seed_checkout()
        client = self._client(FakeWebhookGateway(COMPLETED_EVENT))

        response = self._post(client)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"received": True, "duplicate": False})
        record = self.store.get_checkout("checkout-ref")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.state, "completed")
        self.assertEqual(record.session_id, "cs_test_123")
        self.assertEqual(record.customer_id, "cus_test_123")
        self.assertEqual(record.subscription_id, "sub_test_123")

    def test_duplicate_event_returns_success_without_a_second_event_row(self) -> None:
        self._seed_checkout()
        client = self._client(FakeWebhookGateway(COMPLETED_EVENT))

        first = self._post(client)
        duplicate = self._post(client)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.json(), {"received": True, "duplicate": True})
        self.assertEqual(self._event_count(), 1)

    def test_missing_signature_is_rejected_without_state_change(self) -> None:
        self._seed_checkout()
        client = self._client(FakeWebhookGateway(COMPLETED_EVENT))

        response = client.post("/api/stripe/webhook", content=b"{}")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._event_count(), 0)
        self.assertEqual(self.store.get_checkout("checkout-ref").state, "pending")  # type: ignore[union-attr]

    def test_verifier_rejection_is_http_400_without_state_change(self) -> None:
        self._seed_checkout()
        client = self._client(
            FakeWebhookGateway(COMPLETED_EVENT, error=ValueError("invalid signature"))
        )

        response = self._post(client)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._event_count(), 0)
        self.assertEqual(self.store.get_checkout("checkout-ref").state, "pending")  # type: ignore[union-attr]

    def test_unknown_reference_rolls_back_event_for_retry(self) -> None:
        client = self._client(FakeWebhookGateway(COMPLETED_EVENT))

        failed = self._post(client)
        self._seed_checkout()
        retried = self._post(client)

        self.assertEqual(failed.status_code, 500)
        self.assertEqual(retried.status_code, 200)
        self.assertEqual(retried.json(), {"received": True, "duplicate": False})
        self.assertEqual(self._event_count(), 1)

    def test_missing_required_completion_identifiers_are_retryable(self) -> None:
        for missing in (
            "id",
            "client_reference_id",
            "customer",
            "subscription",
        ):
            with self.subTest(missing=missing):
                event = deepcopy(COMPLETED_EVENT)
                checkout = event["data"]["object"]  # type: ignore[index]
                checkout[missing] = None  # type: ignore[index]
                client = self._client(FakeWebhookGateway(event))
                response = self._post(client)
                self.assertEqual(response.status_code, 500)
                self.assertEqual(self._event_count(), 0)

    def test_expanded_customer_and_subscription_objects_are_normalized(self) -> None:
        self._seed_checkout()
        event = deepcopy(COMPLETED_EVENT)
        checkout = event["data"]["object"]  # type: ignore[index]
        checkout["customer"] = {"id": "cus_expanded"}  # type: ignore[index]
        checkout["subscription"] = {"id": "sub_expanded"}  # type: ignore[index]
        client = self._client(FakeWebhookGateway(event))

        response = self._post(client)

        self.assertEqual(response.status_code, 200)
        record = self.store.get_checkout("checkout-ref")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.customer_id, "cus_expanded")
        self.assertEqual(record.subscription_id, "sub_expanded")

    def test_unrelated_valid_event_is_acknowledged_without_persistence(self) -> None:
        event = {"id": "evt_other", "type": "customer.created", "data": {"object": {}}}
        client = self._client(FakeWebhookGateway(event))

        response = self._post(client)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"received": True, "duplicate": False})
        self.assertEqual(self._event_count(), 0)

    def test_one_time_payment_link_completion_is_acknowledged_without_subscription_persistence(self) -> None:
        event = {
            "id": "evt_tip",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_tip",
                    "client_reference_id": None,
                    "customer": None,
                    "subscription": None,
                    "payment_link": "plink_test_tip",
                    "payment_status": "paid",
                }
            },
        }
        client = self._client(FakeWebhookGateway(event))

        response = self._post(client)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"received": True, "duplicate": False, "ignored": True},
        )
        self.assertEqual(self._event_count(), 0)

    def _seed_checkout(self) -> None:
        self.store.create_checkout("checkout-ref")
        self.store.attach_session("checkout-ref", "cs_test_123")

    def _post(self, client: TestClient):
        return client.post(
            "/api/stripe/webhook",
            content=b'{"raw":"payload"}',
            headers={"Stripe-Signature": "t=123,v1=signature"},
        )

    def _event_count(self) -> int:
        with sqlite3.connect(self.database) as connection:
            return connection.execute("SELECT COUNT(*) FROM stripe_events").fetchone()[0]

    def _client(self, gateway: FakeWebhookGateway) -> TestClient:
        settings = Settings.from_mapping(
            {
                "STRIPE_SECRET_KEY": "rk_test_example",
                "STRIPE_WEBHOOK_SECRET": "whsec_example",
                "STRIPE_TICKERPULSE_PRICE_ID": "price_1UIW1FJMVS0qQfgEkAA4kLPY",
                "STRIPE_INTEGRATION_IDENTIFIER": "tickerpulse_fastapi_qzrmhptk",
                "CHECKOUT_BASE_URL": "https://pay.ediacarian.dedyn.io",
                "SQLITE_PATH": str(self.database),
            }
        )
        return TestClient(create_app(settings, gateway, self.store))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
