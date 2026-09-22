# Payments Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Publish a test-mode Stripe payment directory at https://pay.ediacarian.dedyn.io with TickerPulse subscription, Custom Service, and Tip actions.

**Architecture:** A static page validates four public Stripe HTTPS URLs in site/config.js and renders three checkout actions plus a portal-management link. An unprivileged Nginx container serves it on the VPS and existing Traefik discovers it; it publishes no host port and has no DGX, Tailscale, or application-service dependency.

**Tech Stack:** Static HTML/CSS/vanilla JavaScript; Python standard-library unittest; Docker Compose; nginxinc/nginx-unprivileged; existing VPS Traefik/deSEC DNS-01 TLS.

**Spec:** docs/superpowers/specs/2026-09-22-payments-page-design.md

## Global Constraints

- Launch only with Stripe test-mode Payment Links and a test-mode customer-portal login link.
- Do not include a Stripe secret key, webhook secret, publishable key, card field, customer data, or Checkout Session API.
- The page has no host ports mapping. Existing Traefik remains the only public listener.
- Join only vps-srv_traefik_public and use pay.ediacarian.dedyn.io with a pay-page router/service and desecresolver.
- Do not restart Traefik, DDNS, SciFact, TickerPulse, procurement, or DGX workloads.
- Public Payment Links and portal URLs are committed configuration values; never add credentials for this static page.

## Review Focus

- Unset URLs must be visibly unavailable and never become empty or javascript links; Task 1.
- Non-HTTPS or non-Stripe URLs must be rejected; Task 1.
- Custom Service and Tip must not collect or calculate any amount locally; Task 1.
- Compose must not publish a host port or route a hostname other than pay.ediacarian.dedyn.io; Task 2.
- Test-mode only must be explicit in operator documentation; Task 3.

## File Structure

- site/index.html: semantic card layout and four action anchors.
- site/styles.css: responsive accessible styling.
- site/config.js: four public Stripe URL values, initially empty.
- site/app.js: URL validation and disabled-action state.
- tests/test_payment_page.py: portable page and deployment-contract tests.
- compose.yaml: unprivileged static service and scoped Traefik labels.
- README.md: dashboard and release instructions.

### Task 1: Build and test the static payment directory

**Files:**
- Create: site/index.html
- Create: site/styles.css
- Create: site/config.js
- Create: site/app.js
- Create: tests/test_payment_page.py

**Interfaces:**
- Consumes: window.PAYMENT_PAGE_CONFIG, with tickerPulsePaymentLinkUrl, customServicePaymentLinkUrl, tipPaymentLinkUrl, and customerPortalUrl string keys.
- Produces: configurePaymentPage(document, config), which adds an href only when isAllowedStripeUrl(value) accepts it.

- [ ] **Step 1: Write the failing page-contract tests**

Create tests/test_payment_page.py:

~~~python
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PaymentPageTests(unittest.TestCase):
    def test_page_has_requested_offerings(self):
        page = (ROOT / "site/index.html").read_text(encoding="utf-8")
        for copy in ("TickerPulse", "$1.00/month", "Custom Service", "Tip",
                     "Manage TickerPulse subscription"):
            self.assertIn(copy, page)

    def test_client_limits_destinations_to_https_stripe(self):
        app = (ROOT / "site/app.js").read_text(encoding="utf-8")
        self.assertIn("function isAllowedStripeUrl", app)
        self.assertIn('url.protocol !== "https:"', app)
        self.assertIn("buy.stripe.com", app)
        self.assertIn("billing.stripe.com", app)

    def test_amounts_are_collected_by_stripe(self):
        page = (ROOT / "site/index.html").read_text(encoding="utf-8")
        self.assertNotIn('type="number"', page)
        self.assertNotIn('name="amount"', page)
~~~

- [ ] **Step 2: Run the new test to verify it fails**

Run: python3 -m unittest tests/test_payment_page.py -v

Expected: FAIL because site/index.html and site/app.js do not exist.

- [ ] **Step 3: Implement the minimal site**

Create site/config.js:

~~~javascript
window.PAYMENT_PAGE_CONFIG = Object.freeze({
  tickerPulsePaymentLinkUrl: "",
  customServicePaymentLinkUrl: "",
  tipPaymentLinkUrl: "",
  customerPortalUrl: "",
});
~~~

Create site/app.js with an isAllowedStripeUrl function that accepts only HTTPS
URLs whose hostname equals buy.stripe.com or billing.stripe.com. Its
configurePaymentPage loop finds the action with each configuration key as its
ID. Valid actions receive href=value; invalid actions have href removed,
aria-disabled=true, and title "This Stripe test checkout has not been configured
yet." Add URL-policy comments for accepted buy.stripe.com and billing.stripe.com
links, and rejected HTTP, example.test, and javascript URLs.

Implement four anchor IDs matching configuration keys. Place $1.00/month beside
TickerPulse. State clearly that Stripe accepts a one-time USD amount for Custom
Service and Tip. Load config.js before app.js with defer. Use visible focus
states and a readable 320px layout.

- [ ] **Step 4: Run the page tests green**

Run: python3 -m unittest tests/test_payment_page.py -v

Expected: PASS with page copy, URL policy, and no-local-amount-input contracts.

- [ ] **Step 5: Commit the tested static site**

~~~bash
git add site tests/test_payment_page.py
git commit -m "feat: add Stripe payment landing page"
~~~

### Task 2: Add the isolated VPS Compose and Traefik contract

**Files:**
- Create: compose.yaml
- Modify: tests/test_payment_page.py

**Interfaces:**
- Consumes: site/ from Task 1 and external network vps-srv_traefik_public.
- Produces: pay-page on internal port 8080 and a router only for pay.ediacarian.dedyn.io.

- [ ] **Step 1: Write the failing isolation tests**

Append tests requiring compose.yaml to contain vps-srv_traefik_public, external:
true, a Traefik router Host rule exactly scoped to pay.ediacarian.dedyn.io,
desecresolver, and service port 8080. Assert that its text does not contain
"ports:".

- [ ] **Step 2: Run the test to verify it fails**

Run: python3 -m unittest tests/test_payment_page.py -v

Expected: FAIL because compose.yaml does not exist.

- [ ] **Step 3: Implement the Compose service**

Create one pay-page service using image nginxinc/nginx-unprivileged:1.27-alpine,
restart unless-stopped, read_only true, tmpfs for /tmp, /var/cache/nginx, and
/var/run, and a read-only ./site to /usr/share/nginx/html bind mount. Attach it
only to an external traefik_public network named vps-srv_traefik_public.

Add Docker-provider labels enabling Traefik, identifying
vps-srv_traefik_public, selecting websecure, routing only
pay.ediacarian.dedyn.io, resolving TLS with desecresolver, and load balancing
to port 8080. Add a dedicated router middleware with contentTypeNosniff,
frameDeny, referrerPolicy=strict-origin-when-cross-origin,
stsSeconds=63072000, stsIncludeSubdomains=true, and stsPreload=true.

- [ ] **Step 4: Run full static and Compose verification**

Run: python3 -m unittest tests/test_payment_page.py -v && docker compose config --quiet && git diff --check

Expected: PASS; Compose validates without starting a container or requiring the VPS network locally.

- [ ] **Step 5: Commit the deployment contract**

~~~bash
git add compose.yaml tests/test_payment_page.py
git commit -m "feat: add isolated payment page deployment"
~~~

### Task 3: Document configuration and prepare the test-mode release

**Files:**
- Modify: README.md
- Modify: tests/test_payment_page.py

**Interfaces:**
- Consumes: Task 1 public configuration keys, Task 2 service, and Stripe Dashboard-created test-mode links.
- Produces: an operator procedure that changes public URLs only and deploys the committed revision.

- [ ] **Step 1: Write the failing README contract**

Add a test requiring README.md to contain TICKERPULSE_PAYMENT_LINK_URL,
CUSTOM_SERVICE_PAYMENT_LINK_URL, TIP_PAYMENT_LINK_URL,
STRIPE_CUSTOMER_PORTAL_URL, and case-insensitive "test mode".

- [ ] **Step 2: Run the test to verify it fails**

Run: python3 -m unittest tests/test_payment_page.py -v

Expected: FAIL because README lacks the static payment-page contract.

- [ ] **Step 3: Write the exact operator instructions**

Add a Test-mode payment page section that directs the operator to create the
three spec-defined Products/Prices and Payment Links in test mode; enable the
Stripe customer-portal login and cancellation; map the four uppercase names to
site/config.js's camel-case keys; enter only HTTPS buy.stripe.com or
billing.stripe.com test URLs; deploy the committed checkout with
docker compose -p stripe-payments up -d; and verify ps, tail=100 pay-page logs,
normal-TLS curl to https://pay.ediacarian.dedyn.io/, and every Stripe checkout.
State that live links, credentials, webhooks, and entitlements are outside this
release.

- [ ] **Step 4: Run full repository verification**

Run: python3 -m unittest tests/test_payment_page.py -v && docker compose config --quiet && git diff --check && git status --short

Expected: PASS with no unexpected files.

- [ ] **Step 5: Commit the operator documentation**

~~~bash
git add README.md tests/test_payment_page.py
git commit -m "docs: explain test-mode payment page release"
~~~

### Task 4: Make the authorized public release and record evidence

**Files:**
- Modify: site/config.js only with the four public test-mode URLs supplied by the Stripe Dashboard.
- Create: docs/deployments/2026-09-22-payments-page.md

**Interfaces:**
- Consumes: reviewed implementation, four valid public test-mode URLs, DNS authority, and VPS SSH access.
- Produces: one pay-page container behind Traefik and redacted reproducible release evidence.

- [ ] **Step 1: Capture VPS pre-release state**

Run SSH commands to record Docker public ports, vps-srv_traefik_public, and the
Traefik image without printing environment files or credentials. Confirm that
Traefik owns 80/443 and pay-page does not yet exist.

- [ ] **Step 2: Create and verify DNS**

After confirming pay is unused, create the deSEC CNAME pay to
ediacarian.dedyn.io. Verify both default DNS and 1.1.1.1 resolve the hostname
to the existing VPS edge. If either is empty, wait for propagation; do not alter
Traefik or ACME configuration.

- [ ] **Step 3: Deploy only the payment Compose project**

Copy the committed checkout to a dedicated VPS directory, add only four public
test-mode URLs to site/config.js, then run docker compose -p stripe-payments up
-d, ps, and logs --tail=100 pay-page. Confirm no host port mapping and no
restart of an existing workload.

- [ ] **Step 4: Verify public edge and Stripe checkout**

Verify HTTP redirects to HTTPS, HTTPS returns 200 with normal certificate
validation, and pay-page PortBindings are null or empty. In a browser, follow
each action and confirm Stripe test Checkout displays the $1.00/month
subscription, Custom Service amount entry, Tip amount entry, and the portal
login route. Do not enter live cards or use live URLs.

- [ ] **Step 5: Commit redacted deployment evidence**

Record deployed Git SHA, image/config digests, DNS results, certificate
issuer/SAN, HTTP statuses, port binding result, and test-mode flow confirmation
in docs/deployments/2026-09-22-payments-page.md. Exclude credentials, customer
data, and non-public account information. Commit site/config.js and the evidence
with message: docs: record test-mode payment page deployment.

## Plan self-review

- **Spec coverage:** Tasks 1–3 implement the page, payment boundary, isolation, route, and operator documentation. Task 4 covers DNS, TLS, deployment, and Stripe test-mode verification.
- **Placeholder scan:** Blank Stripe URLs are deliberate public runtime configuration, not unfinished work.
- **Type consistency:** The four PAYMENT_PAGE_CONFIG keys match their action IDs and README mapping; pay-page is the only Compose/router/service identity.
- **Review-focus coverage:** Every listed risk has an explicit Task 1, Task 2, or Task 3 check.

