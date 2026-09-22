from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from payments_api.store import (
    CheckoutCompletion,
    CheckoutStore,
    UnknownCheckoutReference,
)


class CheckoutStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.database = Path(self.tempdir.name) / "payments.sqlite3"
        self.store = CheckoutStore(str(self.database))
        self.store.initialize()

    def test_checkout_moves_from_creating_to_pending_when_session_attaches(self) -> None:
        self.store.create_checkout("checkout-ref")

        self.store.attach_session("checkout-ref", "cs_test_123")

        record = self.store.get_checkout("checkout-ref")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.state, "pending")
        self.assertEqual(record.session_id, "cs_test_123")
        self.assertIsNone(record.customer_id)
        self.assertIsNone(record.subscription_id)

    def test_failed_session_creation_is_visible(self) -> None:
        self.store.create_checkout("checkout-ref")

        self.store.mark_creation_failed("checkout-ref")

        record = self.store.get_checkout("checkout-ref")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.state, "creation_failed")

    def test_completion_persists_stripe_resource_identifiers(self) -> None:
        self.store.create_checkout("checkout-ref")
        self.store.attach_session("checkout-ref", "cs_test_123")

        processed = self.store.complete_checkout(self._completion())

        self.assertTrue(processed)
        record = self.store.get_checkout("checkout-ref")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.state, "completed")
        self.assertEqual(record.customer_id, "cus_test_123")
        self.assertEqual(record.subscription_id, "sub_test_123")

    def test_duplicate_event_is_idempotent(self) -> None:
        self.store.create_checkout("checkout-ref")
        self.store.attach_session("checkout-ref", "cs_test_123")

        self.assertTrue(self.store.complete_checkout(self._completion()))
        self.assertFalse(self.store.complete_checkout(self._completion()))

        record = self.store.get_checkout("checkout-ref")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.customer_id, "cus_test_123")
        self.assertEqual(record.subscription_id, "sub_test_123")

    def test_unknown_reference_rolls_back_event_claim_for_retry(self) -> None:
        with self.assertRaises(UnknownCheckoutReference):
            self.store.complete_checkout(self._completion())

        self.store.create_checkout("checkout-ref")
        self.store.attach_session("checkout-ref", "cs_test_123")
        self.assertTrue(self.store.complete_checkout(self._completion()))

    def test_initialize_rejects_missing_database_parent(self) -> None:
        store = CheckoutStore(str(Path(self.tempdir.name) / "missing" / "payments.sqlite3"))

        with self.assertRaises(OSError):
            store.initialize()

    @staticmethod
    def _completion() -> CheckoutCompletion:
        return CheckoutCompletion(
            event_id="evt_test_123",
            event_type="checkout.session.completed",
            checkout_reference="checkout-ref",
            session_id="cs_test_123",
            customer_id="cus_test_123",
            subscription_id="sub_test_123",
        )


if __name__ == "__main__":
    unittest.main()
