# stripe-payments

Sandbox Stripe Checkout service for the public payment page at
`https://pay.ediacarian.dedyn.io`.

## Current integration

TickerPulse is a fully automated digital subscription: customers customize news
feeds and consume them through RSS or a Telegram bot. There is no consulting or
manual fulfillment.

- Stripe account: `acct_1UIUebJMVS0qQfgE` (sandbox/test mode)
- Product: `prod_VJ8HawUafhUacx`
- Monthly USD $1.00 Price: `price_1UIW1FJMVS0qQfgEkAA4kLPY`
- Product tax code: `txcd_10103000`
- Checkout creation: `POST /api/checkout-sessions`
- Stripe webhook: `POST /api/stripe/webhook`
- Completion event: `checkout.session.completed`
- Tip Product: `prod_VJAuMeMaOB1xOn`
- Tip variable USD Price: `price_1UIYYcJMVS0qQfgEKTxbyYg0`
- Tip Payment Link: `plink_1UIYZ2JMVS0qQfgEftCM4ssO`

The browser asks the FastAPI service for a fresh subscription Checkout Session,
then redirects only to `https://checkout.stripe.com`. The service enables Managed
Payments, uses the existing Price, and sends the blueprint-required
`2026-02-25.preview` API version on that request. It persists the checkout
reference, Session ID, Customer ID, and Subscription ID in SQLite. Webhook
signatures are verified before state changes and duplicate events are idempotent.

Stripe hosts all payment fields. The supplied publishable key is not used by this
hosted Checkout flow. Keep secret and restricted keys server-side.
Live mode is out of scope; this repository and its defaults are sandbox-only.

The Tip action uses a separate sandbox Payment Link where the customer chooses
a one-time USD amount from $1.00 through $500.00, with $5.00 suggested. It uses
standard Stripe Payments with dynamic payment methods and does not enable
Managed Payments because no eligible digital product is delivered for a tip.
Tip completions are acknowledged by the shared webhook but do not create a
subscription record or trigger fulfillment. Custom Service and customer-portal
buttons remain separate work and are not available.

## Architecture and safety

The `pay-page` Nginx container serves the static site. The `payments-api`
container runs FastAPI as an unprivileged user with a read-only root filesystem,
no host port, and a private health check. Traefik sends only `/api` requests to
FastAPI; all other paths remain on the static site. SQLite is stored in the named
`payments_data` volume at `/data/stripe-payments.sqlite3`.

Use a restricted sandbox key for `STRIPE_SECRET_KEY`, initially granting Checkout
Sessions write access and expanding it only if Stripe reports a specific required
permission. Do not use a live key or commit any plaintext credential.

## Configure encrypted sandbox secrets

The repository uses SOPS/age and maps the ignored `.env` file through
`secrets/manifest.tsv`. With the age private key available locally, edit the
encrypted payload without printing values:

```sh
EDITOR=nano bash scripts/secrets/edit.sh .env
```

Set `STRIPE_SECRET_KEY` to the restricted sandbox key and
`STRIPE_WEBHOOK_SECRET` to the sandbox endpoint's signing secret. Retain the
non-secret defaults from `.env.example`. Then verify the encrypted round trip and
that restored `.env` permissions are mode 600:

```sh
bash scripts/secrets/check.sh
bash scripts/secrets/decrypt-all.sh
stat -c '%a %n' .env
```

If the webhook destination has not been created yet, use a non-secret temporary
sentinel for `STRIPE_WEBHOOK_SECRET` only for the initial health deployment. Once
the HTTPS endpoint is healthy, create the destination, replace the sentinel with
the real signing secret through `scripts/secrets/edit.sh .env`, and recreate the
API container before testing payment completion.

## Verify and deploy on the VPS

Run the local verification gates:

```sh
.venv/bin/python -m unittest discover -s tests -v
docker compose config --quiet
docker build -f Dockerfile.api -t stripe-payments-api:test .
bash scripts/secrets/check.sh
git diff --check
```

Deploy the sandbox services from this repository's VPS checkout:

```sh
bash scripts/secrets/decrypt-all.sh
docker compose -p stripe-payments up -d --build
docker compose -p stripe-payments ps
docker compose -p stripe-payments logs --tail=100 payments-api pay-page
curl -fsSI https://pay.ediacarian.dedyn.io/
curl -fsS https://pay.ediacarian.dedyn.io/api/not-found
```

The first URL must return the static page with normal TLS validation. The second
should return FastAPI's JSON 404, demonstrating that `/api` reaches the API
router. `docker compose ps` must show the API container as healthy; `/healthz` is
container-internal and intentionally not exposed by Traefik.

After the public API is healthy, create a sandbox webhook destination for:

```text
https://pay.ediacarian.dedyn.io/api/stripe/webhook
```

Subscribe it to `checkout.session.completed`, securely store its `whsec_...`
value as described above, and recreate `payments-api`.

## Sandbox acceptance

1. Open the public page and choose TickerPulse Subscribe.
2. Confirm Stripe Checkout displays USD $1.00 per month and Managed Payments.
3. Complete Checkout with a Stripe-published sandbox payment method and try
   different billing addresses when checking tax behavior.
4. Confirm the webhook receives HTTP 200.
5. Inspect the SQLite record without displaying credentials and verify it is
   `completed` with Session, Customer, and Subscription IDs.
6. Replay the same signed event and verify it remains a single stored event and
   returns HTTP 200 as a duplicate.

A browser success redirect alone is not fulfillment evidence. The signed
`checkout.session.completed` event is the completion signal. Do not activate
live mode or deploy live credentials without a separate explicit authorization.

## References

- [Stripe Checkout](https://docs.stripe.com/payments/checkout)
- [Stripe test cards](https://docs.stripe.com/testing)
- [Stripe webhook signatures](https://docs.stripe.com/webhooks/signature)
- [SOPS](https://github.com/getsops/sops)
