# TickerPulse Managed Payments FastAPI Design

## Purpose

Extend the existing test-mode TickerPulse payment page with a small FastAPI
service that creates Stripe-hosted Managed Payments Checkout Sessions and
receives signed Stripe webhook events. The integration reuses the existing
Stripe resources:

- Product `prod_VJ8HawUafhUacx` (`TickerPulse`);
- Price `price_1UIW1FJMVS0qQfgEkAA4kLPY` (USD $1.00 recurring monthly); and
- product tax code `txcd_10103000` (online SaaS, personal use).

TickerPulse is a fully automated digital service. Customers configure news
feeds and consume them through RSS or a Telegram bot; the purchase includes no
consulting, human customization, or manual fulfillment. This is the product
eligibility basis for using Managed Payments. The integration remains sandbox
only. Live-mode activation is a separate decision.

## Selected architecture

Keep the existing static landing page and add one FastAPI container behind the
same Traefik edge. The browser calls a same-origin endpoint to create a fresh
Checkout Session and is redirected to the returned Stripe-hosted URL. Stripe
sends `checkout.session.completed` events to a second endpoint. The service
verifies every webhook signature before processing the payload and persists
the Stripe resource identifiers in SQLite.

FastAPI is preferred over a serverless function or converting the entire page
to a dynamic application because it fits the repository's Python tests, keeps
the static page intact, and can run in the existing Docker Compose deployment.
A Managed Payments Payment Link remains a simpler alternative, but it would not
implement the blueprint's required Checkout Sessions API and webhook flow.

## Components and boundaries

### Static payment page

The TickerPulse action becomes a button that sends an empty `POST` request to
`/api/checkout-sessions`. On success, JavaScript redirects the current tab to
the returned Checkout URL. It shows a recoverable error if session creation
fails and prevents double submission while a request is in flight.

The browser never receives a Stripe secret or restricted key. This hosted
Checkout integration does not require Stripe.js or the publishable key.

The existing Custom Service, Tip, and customer-portal actions remain unchanged
and disabled until their public URLs are configured. They are not part of this
Managed Payments slice.

### FastAPI service

The service exposes:

- `POST /api/checkout-sessions`: generates an opaque checkout reference,
  creates a Stripe Checkout Session, stores the pending mapping, and returns
  only the hosted Checkout URL;
- `POST /api/stripe/webhook`: reads the unmodified request body, verifies the
  `Stripe-Signature` header, and idempotently handles
  `checkout.session.completed`; and
- `GET /healthz`: reports process/database readiness for container health
  checks and is not routed publicly by Traefik.

The Stripe SDK is instantiated as a `StripeClient` with a key read from the
environment. The application does not set an API version, so the account and
SDK defaults apply as required by the supplied blueprint.

Checkout Session creation uses:

- `mode: subscription`;
- one line item containing the existing $1 monthly Price and quantity 1;
- `managed_payments.enabled: true`;
- the generated checkout reference as `client_reference_id`;
- fixed metadata identifying TickerPulse and the sandbox environment;
- same-origin success and cancellation URLs;
- a stable integration identifier ending in eight random letters; and
- no `payment_method_types`, `automatic_tax`, shipping, Connect, or custom
  statement-descriptor parameters.

Managed Payments controls eligible payment methods, customer address
collection, indirect tax calculation, and Stripe's merchant-of-record
behavior. The current online-SaaS tax code is retained; the blueprint's
download-specific code does not describe how TickerPulse is delivered.

### Persistence

SQLite is stored on a dedicated Docker volume and initialized automatically.
It contains two narrowly scoped tables:

1. `checkout_records`: opaque checkout reference, Checkout Session ID,
   Customer ID, Subscription ID, state, and timestamps.
2. `stripe_events`: Stripe Event ID, type, and processed timestamp.

The Event ID is unique. A webhook transaction first claims that ID, updates the
matching checkout record, and commits both changes atomically. Duplicate event
delivery returns success without applying the event twice. The database stores
Stripe identifiers only; it stores no card data, API credentials, webhook
secrets, or customer email address.

There is no existing TickerPulse user model in this repository. The opaque
checkout reference provides a durable association point without inventing an
authentication system. A future authenticated TickerPulse application can add
its user ID to the record before creating Checkout.

### Deployment routing

The existing static container remains the fallback router for
`pay.ediacarian.dedyn.io`. The FastAPI container joins only the existing
`vps-srv_traefik_public` network. A higher-priority Traefik router forwards
`Host(pay.ediacarian.dedyn.io) && PathPrefix(/api)` to FastAPI's internal port.
No service publishes a host port.

The payment service stays on the VPS. It is a small public-ingress and
persistence workload with no GPU requirement, so routing it through Tailscale
to the DGX would add an avoidable availability dependency. The DGX remains the
TickerPulse feed-processing tier. A future entitlement handoff may send an
authenticated, retryable internal notification from the VPS to TickerPulse,
but webhook receipt, signature verification, and Stripe state persistence must
complete on the VPS first.

The webhook destination is registered only after the deployed endpoint passes
normal TLS and health checks. Its URL is:

`https://pay.ediacarian.dedyn.io/api/stripe/webhook`

The destination subscribes only to `checkout.session.completed`, matching the
authoritative blueprint. Expansion to delayed-payment events or subscription
lifecycle events requires a separate entitlement/lifecycle design.

## Secrets and configuration

Runtime configuration uses these environment variables:

- `STRIPE_SECRET_KEY`: preferably a sandbox restricted key with only the
  permissions needed to create Checkout Sessions and read referenced catalog
  resources;
- `STRIPE_WEBHOOK_SECRET`: the sandbox endpoint signing secret;
- `STRIPE_TICKERPULSE_PRICE_ID`: defaults operationally to the accepted sandbox
  Price ID but remains configurable;
- `STRIPE_INTEGRATION_IDENTIFIER`: a non-secret label with an eight-letter
  random suffix;
- `CHECKOUT_BASE_URL`: the public HTTPS origin; and
- `SQLITE_PATH`: the container database path.

Only placeholders are committed. API and webhook secrets use the existing
SOPS/age manifest workflow and must never appear in browser code, source,
Compose labels, command output, or test fixtures. The supplied publishable key
is not required and is not committed.

## Failure handling

- Missing or malformed runtime configuration prevents the FastAPI process from
  becoming ready.
- Stripe session-creation failures produce a generic browser error and a
  structured server log without request headers, credentials, or Checkout URL.
- Missing or invalid webhook signatures return HTTP 400 without modifying the
  database.
- A valid event that cannot be persisted returns HTTP 500 so Stripe retries it.
- Unsupported valid event types return HTTP 200 without side effects.
- A completed session that does not match a known checkout reference fails
  closed and is retained as an operational error rather than granting access.

## Verification and acceptance

Automated tests must cover:

1. the exact Checkout Session request contract, including $1 recurring Price,
   Managed Payments, subscription mode, and omission of forbidden parameters;
2. browser redirect, disabled-in-flight state, and recoverable API errors;
3. valid webhook signature processing and identifier persistence;
4. invalid signatures, duplicate Event IDs, unknown checkout references, and
   transactional rollback;
5. Compose isolation, route priority, no host ports, and persistent SQLite
   storage; and
6. secret placeholders and Git-ignore/SOPS contracts.

Sandbox acceptance then requires:

1. creating a fresh Checkout Session through the deployed page;
2. completing Stripe-hosted Checkout with a Stripe test payment method;
3. observing exactly one verified `checkout.session.completed` event;
4. confirming the stored Checkout Session, Customer, and Subscription IDs;
5. confirming the resulting Stripe Subscription is $1/month and has Managed
   Payments enabled; and
6. replaying the event to prove idempotency.

The already-created exploratory session
`cs_test_a1Anvx4aGQzVFaEYAowONnrZQpwwVhhzTUHlfTxXXsNhPzPRZGqs1HG2lj`
demonstrates that the existing Price and tax code are accepted by a sandbox
Managed Payments Checkout Session. It is evidence of API compatibility, not a
substitute for deployed end-to-end acceptance.

## Scope boundary

This design implements only new TickerPulse sandbox subscriptions. It does not
activate live mode, migrate existing subscriptions, implement entitlement
checks, add login or user accounts, handle cancellation or renewal lifecycle
events, create Custom Service or Tip flows, or deploy credentials outside the
documented SOPS workflow.
