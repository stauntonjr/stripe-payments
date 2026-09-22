from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
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


def run_checkout(scenario: dict[str, object]) -> dict[str, object]:
    script = """
const fs = require('fs');
const scenario = JSON.parse(process.argv[1]);
let clickHandler;
let resolveFetch;
const requests = [];
const assigned = [];
const button = {
  disabled: false, attributes: {},
  addEventListener(name, handler) { if (name === 'click') clickHandler = handler; },
  setAttribute(name, value) { this.attributes[name] = value; },
  removeAttribute(name) { delete this.attributes[name]; },
};
const error = { hidden: true, textContent: '' };
const elements = {
  tickerPulseCheckoutButton: button,
  tickerPulseCheckoutError: error,
};
global.window = {
  PAYMENT_PAGE_CONFIG: {},
  location: { assign(value) { assigned.push(value); } },
};
global.document = { getElementById: (id) => elements[id] || null };
global.fetch = (url, options) => {
  requests.push({ url, method: options.method, body: options.body ?? null });
  return new Promise((resolve, reject) => {
    resolveFetch = () => {
      if (scenario.fetchError) return reject(new Error('network failure'));
      resolve({
        ok: scenario.ok !== false,
        status: scenario.status || 201,
        json: async () => {
          if (scenario.jsonError) throw new Error('invalid json');
          return scenario.json;
        },
      });
    };
  });
};
eval(fs.readFileSync('site/app.js', 'utf8'));
(async () => {
  const pending = clickHandler({ preventDefault() {} });
  const busy = { disabled: button.disabled, ariaBusy: button.attributes['aria-busy'] || null };
  resolveFetch();
  await pending;
  console.log(JSON.stringify({
    requests, assigned, busy,
    final: {
      disabled: button.disabled,
      ariaBusy: button.attributes['aria-busy'] || null,
      errorHidden: error.hidden,
      errorText: error.textContent,
    },
  }));
})().catch((error) => { console.error(error); process.exit(1); });
"""
    result = subprocess.run(
        ["node", "-e", script, json.dumps(scenario)],
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
                "customServicePaymentLinkUrl": "https://buy.stripe.com/test_456",
                "tipPaymentLinkUrl": "https://buy.stripe.com/test_789",
                "customerPortalUrl": "https://billing.stripe.com/p/login/test_123",
            }
        )
        self.assertEqual(actions["customerPortalUrl"]["href"], "https://billing.stripe.com/p/login/test_123")
        self.assertNotIn("aria-disabled", actions["tipPaymentLinkUrl"]["attributes"])

    def test_invalid_or_empty_url_is_disabled(self) -> None:
        actions = run_browser(
            {
                "customServicePaymentLinkUrl": "http://buy.stripe.com/test_456",
                "tipPaymentLinkUrl": "javascript:alert(1)",
                "customerPortalUrl": "https://example.test/portal",
            }
        )
        for action in actions.values():
            self.assertIsNone(action["href"])
            self.assertEqual(action["attributes"].get("aria-disabled"), "true")
            self.assertEqual(action["title"], "This Stripe test checkout has not been configured yet.")

    def test_tickerpulse_checkout_posts_once_and_redirects_to_stripe(self) -> None:
        result = run_checkout(
            {"json": {"checkout_url": "https://checkout.stripe.com/c/pay/test_123"}}
        )

        self.assertEqual(
            result["requests"],
            [{"url": "/api/checkout-sessions", "method": "POST", "body": None}],
        )
        self.assertEqual(result["busy"], {"disabled": True, "ariaBusy": "true"})
        self.assertEqual(
            result["assigned"], ["https://checkout.stripe.com/c/pay/test_123"]
        )

    def test_tickerpulse_checkout_restores_button_after_request_failures(self) -> None:
        scenarios = (
            {"fetchError": True},
            {"ok": False, "status": 503, "json": {}},
            {"jsonError": True},
        )
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                result = run_checkout(scenario)
                self.assertEqual(result["assigned"], [])
                self.assertEqual(
                    result["final"],
                    {
                        "disabled": False,
                        "ariaBusy": None,
                        "errorHidden": False,
                        "errorText": "Checkout is temporarily unavailable. Please try again.",
                    },
                )

    def test_tickerpulse_checkout_refuses_unsafe_redirect_destinations(self) -> None:
        unsafe = (
            "http://checkout.stripe.com/c/pay/test",
            "https://user:pass@checkout.stripe.com/c/pay/test",
            "https://checkout.stripe.com.evil.example/c/pay/test",
            "https://example.test/checkout",
        )
        for checkout_url in unsafe:
            with self.subTest(checkout_url=checkout_url):
                result = run_checkout({"json": {"checkout_url": checkout_url}})
                self.assertEqual(result["assigned"], [])
                self.assertFalse(result["final"]["disabled"])
                self.assertFalse(result["final"]["errorHidden"])

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

    def test_compose_adds_isolated_persistent_fastapi_service(self) -> None:
        config = compose_config()
        service = config["services"]["payments-api"]
        self.assertEqual(service["build"]["dockerfile"], "Dockerfile.api")
        self.assertNotIn("ports", service)
        self.assertEqual(list(service["networks"]), ["traefik_public"])
        self.assertTrue(service["read_only"])
        self.assertIn("healthcheck", service)
        self.assertEqual(
            service["environment"]["SQLITE_PATH"],
            "/data/stripe-payments.sqlite3",
        )
        self.assertTrue(
            any(
                volume["source"] == "payments_data"
                and volume["target"] == "/data"
                for volume in service["volumes"]
            )
        )
        self.assertIn("payments_data", config["volumes"])
        compose_source = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn("env_file:\n      - path: .env\n        required: false", compose_source)

    def test_fastapi_route_precedes_static_route_and_reuses_security_headers(self) -> None:
        services = compose_config()["services"]
        labels = services["payments-api"]["labels"]
        static_labels = services["pay-page"]["labels"]
        self.assertEqual(
            labels["traefik.http.routers.payments-api.rule"],
            "Host(`pay.ediacarian.dedyn.io`) && PathPrefix(`/api`)",
        )
        self.assertGreater(
            int(labels["traefik.http.routers.payments-api.priority"]),
            int(static_labels.get("traefik.http.routers.pay-page.priority", "0")),
        )
        self.assertEqual(
            labels["traefik.http.services.payments-api.loadbalancer.server.port"],
            "8000",
        )
        self.assertEqual(
            labels["traefik.http.routers.payments-api.middlewares"],
            "pay-page-security",
        )

    def test_docker_build_context_excludes_credentials_and_local_state(self) -> None:
        ignored = {
            line.strip()
            for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }
        for pattern in (
            ".env",
            "secrets/",
            ".git/",
            "*.sqlite3",
            "__pycache__/",
            ".specstory/",
        ):
            self.assertIn(pattern, ignored)

    def test_environment_example_contains_only_non_secret_defaults(self) -> None:
        example = (ROOT / ".env.example").read_text(encoding="utf-8")
        for line in (
            "STRIPE_SECRET_KEY=",
            "STRIPE_WEBHOOK_SECRET=",
            "STRIPE_TICKERPULSE_PRICE_ID=price_1UIW1FJMVS0qQfgEkAA4kLPY",
            "STRIPE_INTEGRATION_IDENTIFIER=tickerpulse_fastapi_qzrmhptk",
            "CHECKOUT_BASE_URL=https://pay.ediacarian.dedyn.io",
            "SQLITE_PATH=/data/stripe-payments.sqlite3",
        ):
            self.assertIn(line, example)
        for secret_prefix in ("sk_test_", "rk_test_", "whsec_"):
            self.assertNotIn(secret_prefix, example)

    def test_runtime_fails_closed_when_database_parent_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            environment = {
                **os.environ,
                "STRIPE_SECRET_KEY": "rk_test_example",
                "STRIPE_WEBHOOK_SECRET": "whsec_example",
                "STRIPE_TICKERPULSE_PRICE_ID": "price_1UIW1FJMVS0qQfgEkAA4kLPY",
                "STRIPE_INTEGRATION_IDENTIFIER": "tickerpulse_fastapi_qzrmhptk",
                "CHECKOUT_BASE_URL": "https://pay.ediacarian.dedyn.io",
                "SQLITE_PATH": str(Path(tempdir) / "missing" / "payments.sqlite3"),
            }
            result = subprocess.run(
                [sys.executable, "-c", "import payments_api.runtime"],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("rk_test_example", result.stderr)
        self.assertNotIn("whsec_example", result.stderr)
