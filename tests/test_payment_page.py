from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


def run_browser(config: dict[str, str]) -> dict[str, dict[str, str | None]]:
    """Execute the page script against a minimal browser-like document."""
    app_path = ROOT / "site/app.js"
    if not app_path.is_file():
        raise AssertionError(f"missing client implementation: {app_path}")
    script = """
const fs = require('fs');
const config = JSON.parse(process.argv[1]);
const elements = Object.fromEntries(Object.keys(config).map((id) => [id, {
  href: 'unset', attributes: {}, title: '',
  removeAttribute(name) { if (name === 'href') this.href = null; else delete this.attributes[name]; },
  setAttribute(name, value) { this.attributes[name] = value; },
}]));
global.window = { PAYMENT_PAGE_CONFIG: config };
global.document = { getElementById: (id) => elements[id] || null };
eval(fs.readFileSync('site/app.js', 'utf8'));
console.log(JSON.stringify(elements));
"""
    result = subprocess.run(
        ["node", "-e", script, json.dumps(config)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def compose_config() -> dict[str, object]:
    compose_path = ROOT / "compose.yaml"
    if not compose_path.is_file():
        raise AssertionError(f"missing Compose configuration: {compose_path}")
    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


class PaymentPageTests(unittest.TestCase):
    def test_page_has_requested_offerings(self) -> None:
        page_path = ROOT / "site/index.html"
        self.assertTrue(page_path.is_file(), f"missing page: {page_path}")
        page = page_path.read_text(encoding="utf-8")
        for copy in (
            "TickerPulse",
            "$1.00/month",
            "Custom Service",
            "Tip",
            "Manage TickerPulse subscription",
        ):
            self.assertIn(copy, page)

    def test_valid_stripe_urls_are_enabled_as_same_tab_destinations(self) -> None:
        actions = run_browser(
            {
                "tickerPulsePaymentLinkUrl": "https://buy.stripe.com/test_123",
                "customServicePaymentLinkUrl": "https://buy.stripe.com/test_456",
                "tipPaymentLinkUrl": "https://buy.stripe.com/test_789",
                "customerPortalUrl": "https://billing.stripe.com/p/login/test_123",
            }
        )
        self.assertEqual(actions["tickerPulsePaymentLinkUrl"]["href"], "https://buy.stripe.com/test_123")
        self.assertEqual(actions["customerPortalUrl"]["href"], "https://billing.stripe.com/p/login/test_123")
        self.assertNotIn("aria-disabled", actions["tipPaymentLinkUrl"]["attributes"])

    def test_invalid_or_empty_url_is_disabled(self) -> None:
        actions = run_browser(
            {
                "tickerPulsePaymentLinkUrl": "",
                "customServicePaymentLinkUrl": "http://buy.stripe.com/test_456",
                "tipPaymentLinkUrl": "javascript:alert(1)",
                "customerPortalUrl": "https://example.test/portal",
            }
        )
        for action in actions.values():
            self.assertIsNone(action["href"])
            self.assertEqual(action["attributes"].get("aria-disabled"), "true")
            self.assertEqual(action["title"], "This Stripe test checkout has not been configured yet.")

    def test_amounts_are_collected_by_stripe(self) -> None:
        page_path = ROOT / "site/index.html"
        self.assertTrue(page_path.is_file(), f"missing page: {page_path}")
        page = page_path.read_text(encoding="utf-8")
        self.assertNotIn('type="number"', page)
        self.assertNotIn('name="amount"', page)

    def test_compose_keeps_payment_page_off_host_ports(self) -> None:
        config = compose_config()
        service = config["services"]["pay-page"]
        self.assertNotIn("ports", service)
        self.assertEqual(list(service["networks"]), ["traefik_public"])
        self.assertTrue(config["networks"]["traefik_public"]["external"])
        self.assertEqual(
            config["networks"]["traefik_public"]["name"],
            "vps-srv_traefik_public",
        )

    def test_compose_route_is_scoped_and_hardened(self) -> None:
        labels = compose_config()["services"]["pay-page"]["labels"]
        self.assertEqual(
            labels["traefik.http.routers.pay-page.rule"],
            "Host(`pay.ediacarian.dedyn.io`)",
        )
        self.assertEqual(
            labels["traefik.http.routers.pay-page.tls.certresolver"],
            "desecresolver",
        )
        self.assertEqual(
            labels["traefik.http.services.pay-page.loadbalancer.server.port"],
            "8080",
        )
        self.assertEqual(
            labels["traefik.http.routers.pay-page.middlewares"],
            "pay-page-security",
        )
        self.assertEqual(
            labels["traefik.http.middlewares.pay-page-security.headers.framedeny"],
            "true",
        )
