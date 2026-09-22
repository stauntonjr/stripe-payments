from __future__ import annotations

import unittest

from payments_api.config import Settings


VALID = {
    "STRIPE_SECRET_KEY": "rk_test_example",
    "STRIPE_WEBHOOK_SECRET": "whsec_example",
    "STRIPE_TICKERPULSE_PRICE_ID": "price_1UIW1FJMVS0qQfgEkAA4kLPY",
    "STRIPE_INTEGRATION_IDENTIFIER": "tickerpulse_fastapi_qzrmhptk",
    "CHECKOUT_BASE_URL": "https://pay.ediacarian.dedyn.io",
    "SQLITE_PATH": ":memory:",
}


class SettingsTests(unittest.TestCase):
    def test_valid_settings_are_immutable_and_normalize_origin(self) -> None:
        values = {**VALID, "CHECKOUT_BASE_URL": "https://pay.ediacarian.dedyn.io/"}

        settings = Settings.from_mapping(values)

        self.assertEqual(settings.checkout_base_url, "https://pay.ediacarian.dedyn.io")
        with self.assertRaises((AttributeError, TypeError)):
            settings.price_id = "price_changed"  # type: ignore[misc]

    def test_every_setting_is_required(self) -> None:
        for missing in VALID:
            with self.subTest(missing=missing):
                values = dict(VALID)
                del values[missing]
                with self.assertRaisesRegex(ValueError, missing):
                    Settings.from_mapping(values)

    def test_checkout_base_url_must_be_a_clean_https_origin(self) -> None:
        invalid_urls = (
            "http://pay.ediacarian.dedyn.io",
            "https://user:password@pay.ediacarian.dedyn.io",
            "https://pay.ediacarian.dedyn.io/path",
            "https://pay.ediacarian.dedyn.io?debug=1",
            "https://pay.ediacarian.dedyn.io#fragment",
            "https://",
        )
        for value in invalid_urls:
            with self.subTest(value=value), self.assertRaises(ValueError):
                Settings.from_mapping({**VALID, "CHECKOUT_BASE_URL": value})

    def test_price_id_must_be_a_stripe_price_identifier(self) -> None:
        for value in ("prod_123", "price_", " price_123", "price_123/456"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Settings.from_mapping({**VALID, "STRIPE_TICKERPULSE_PRICE_ID": value})

    def test_integration_identifier_requires_eight_lowercase_suffix_letters(self) -> None:
        invalid_values = (
            "tickerpulse_fastapi_short",
            "tickerpulse_fastapi_abcdefghi",
            "tickerpulse_fastapi_ABCDefgh",
            "tickerpulse_fastapi_abcd1234",
            "abcdefgh",
        )
        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                Settings.from_mapping({**VALID, "STRIPE_INTEGRATION_IDENTIFIER": value})

    def test_sqlite_path_cannot_be_empty(self) -> None:
        for value in ("", "   "):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Settings.from_mapping({**VALID, "SQLITE_PATH": value})


if __name__ == "__main__":
    unittest.main()
