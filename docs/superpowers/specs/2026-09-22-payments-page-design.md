# Payments Page Design

## Purpose

Publish a small, public payment landing page at
`https://pay.ediacarian.dedyn.io` that directs visitors to Stripe-hosted,
**test-mode** Checkout flows. The page must let a visitor select a
USD $1.00/month TickerPulse subscription, a customer-entered USD amount for
Custom Service, or a customer-entered USD amount for a Tip.

The page is a checkout directory, not a payment processor. Stripe collects
payment data and owns the Checkout UI. The service does not create Checkout
Sessions, verify payment events, unlock content, store customer data, or
contain a Stripe secret.

## Selected approach

Use three independent Stripe Payment Links and a static site container on the
existing VPS. The static page has one card per payment option and redirects a
visitor to the configured Stripe-hosted URL. Each Payment Link is a public
configuration value, so it can be source controlled without using the secrets
workflow.

In the Stripe Dashboard, create these test-mode products/prices and Payment
Links:

| Page action | Stripe price configuration | Checkout behavior |
| --- | --- | --- |
| TickerPulse | USD 1.00, recurring monthly | Starts a subscription |
| Custom Service | USD, one-time, `custom_unit_amount` enabled | Stripe prompts for a customer-chosen amount |
| Tip | USD, one-time, `custom_unit_amount` enabled | Stripe prompts for a customer-chosen amount |

The Stripe Billing customer portal login link is a fourth public configuration
value. It gives existing subscribers a clear, Stripe-hosted management and
cancellation route. The Dashboard must enable the customer portal login link
and subscription cancellation before the page is published.

## Page and configuration

The application is a dependency-minimal static HTML/CSS/JavaScript site served
by a non-root container. It presents:

- a TickerPulse card with the recurring price and a **Subscribe** link;
- a Custom Service card explaining that Stripe will collect a one-time USD
  amount and a **Choose amount** link;
- a Tip card with the same Stripe-hosted custom-amount behavior and a
  **Leave a tip** link; and
- a visible **Manage TickerPulse subscription** link to the Stripe customer
  portal login page.

All external links use `https`, open normally in the same browser tab, and are
disabled with an explicit configuration-error message when their configured URL
is absent or malformed. The static asset contains no Stripe publishable key,
secret key, webhook secret, card field, or customer information.

Public configuration lives in a committed example/config file with four
placeholder URLs:

- `TICKERPULSE_PAYMENT_LINK_URL`
- `CUSTOM_SERVICE_PAYMENT_LINK_URL`
- `TIP_PAYMENT_LINK_URL`
- `STRIPE_CUSTOMER_PORTAL_URL`

The deploy manifest receives those same values as ordinary environment
variables. Production secrets remain out of the image, repository, and page.

## Hosting and public edge

The page runs directly on the existing VPS in a dedicated Compose project. Its
container joins the externally managed `vps-srv_traefik_public` Docker network,
has no `ports:` mapping, and uses a hostname-specific Traefik router label for
`pay.ediacarian.dedyn.io`. Traefik stays the sole public listener on ports 80
and 443, redirects HTTP to HTTPS, and uses the existing `desecresolver` TLS
configuration. The service does not use DGX, Tailscale Serve, or any SciFact,
TickerPulse, or procurement service network.

Create a DNS record for `pay.ediacarian.dedyn.io` pointing to the existing VPS
address only after confirming it is unused. Prefer a CNAME to
`ediacarian.dedyn.io.` so the hostname follows the established edge address.
Do not restart Traefik, DDNS, SciFact, TickerPulse, procurement, or DGX
workloads; Docker's provider discovers the new service independently.

## Failure handling and security

The page must distinguish a missing public payment URL from a valid payment
destination, and must never manufacture or accept an amount itself. Browser
security headers applied by the route include HSTS, frame denial,
`X-Content-Type-Options: nosniff`, and a strict referrer policy. The only
outbound browser destinations are the configured Stripe HTTPS URLs.

The initial launch remains strictly in Stripe test mode. Switching any link to
live mode, enabling a live payment method, creating a webhook, or deploying
payment-gated functionality is out of scope and requires a separate explicit
decision.

## Verification and acceptance

Local verification covers HTML/config rendering, missing/malformed URL states,
the exact card labels and copy, and Compose configuration. Deployment evidence
must record the deployed image/config digest and verify all of the following:

1. DNS resolves `pay.ediacarian.dedyn.io` to the existing VPS edge.
2. HTTP redirects to HTTPS and normal TLS validation succeeds for the hostname.
3. The page returns HTTP 200 through Traefik.
4. Only Traefik exposes public 80/443; the page container exposes no host port.
5. Each configured Checkout destination is an HTTPS Stripe URL, and the
   customer portal link is present.
6. Stripe Dashboard test-mode checkout confirms the $1.00 monthly subscription
   and both custom-amount flows; that interactive Stripe-account verification is
   recorded separately from static page checks.

## Scope boundary

This design deliberately does not create the Stripe products, prices, Payment
Links, portal configuration, or DNS record automatically. Those are account or
DNS authority changes that require access to the relevant dashboards. The
implementation prepares the page and deployment configuration, and the release
run uses the user-supplied public test-mode URLs to publish it.
