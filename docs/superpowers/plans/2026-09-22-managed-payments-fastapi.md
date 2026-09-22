# TickerPulse Managed Payments FastAPI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a VPS-hosted FastAPI service that creates $1/month TickerPulse Managed Payments Checkout Sessions and idempotently records verified `checkout.session.completed` webhooks.

**Architecture:** Keep the static Nginx payment page as the public landing page and route `/api` on the same hostname to a separate FastAPI container. The API uses a Stripe SDK `StripeClient`, stores opaque checkout-to-Stripe identifier mappings in SQLite, and verifies webhook signatures before atomically recording completion events.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, Stripe Python SDK 15.4.0, SQLite, standard-library `unittest`, FastAPI `TestClient`, Docker Compose, Traefik, existing SOPS/age workflow.

**Spec:** `docs/superpowers/specs/2026-09-22-managed-payments-fastapi-design.md`

## Global Constraints

- Reuse Product `prod_VJ8HawUafhUacx` and recurring Price `price_1UIW1FJMVS0qQfgEkAA4kLPY`; do not create a replacement Product or Price.
- Create subscription-mode Checkout Sessions with `managed_payments.enabled=true` and amount USD $1.00 per month.
- Retain product tax code `txcd_10103000`; do not substitute the blueprint's download-specific code.
- Do not pass `payment_method_types` or `automatic_tax`; Managed Payments owns both behaviors.
- Instantiate `stripe.StripeClient` without an explicit API version and call methods on that client.
- Run the FastAPI service and SQLite database on the VPS; do not route payment ingress or persistence through the DGX.
- Store no email, card data, API credential, or webhook signing secret in SQLite.
- Keep `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` in the existing ignored `.env` and SOPS/age workflow only.
- Keep all changes in sandbox/test mode; live-mode configuration and deployment are outside this plan.
- Do not modify or remove unrelated `.specstory/` or `tests/__pycache__/` files already present in the worktree.

## Review Focus

- A successful API response containing a non-Stripe redirect URL must be rejected by the browser rather than navigated to; Task 4 adds the test.
- Concurrent or repeated delivery of the same Stripe Event ID must update a checkout at most once and return success; Task 2 adds the test.
- A validly signed completion event with an unknown checkout reference must roll back the Event ID claim so Stripe can retry; Task 2 adds the test.
- A Stripe session created before local persistence completes must leave a visible failed record and never be represented as ready; Task 3 adds the test.
- Missing secrets, an invalid base URL, a malformed integration identifier, or an unwritable database path must prevent readiness; Tasks 1 and 5 add the tests.

---

## File structure

- `payments_api/__init__.py`: package marker only.
- `payments_api/config.py`: validated environment-backed `Settings` dataclass.
- `payments_api/store.py`: SQLite schema and transactional checkout/event operations.
- `payments_api/stripe_gateway.py`: Stripe SDK boundary and response normalization.
- `payments_api/main.py`: dependency-injected FastAPI application factory and routes.
- `payments_api/runtime.py`: production-only environment wiring for Uvicorn.
- `tests/test_api_config.py`: settings validation contracts.
- `tests/test_checkout_store.py`: SQLite state and idempotency contracts.
- `tests/test_checkout_api.py`: Checkout endpoint and Stripe request contracts.
- `tests/test_webhook_api.py`: signature and webhook response contracts.
- `tests/test_payment_page.py`: existing page tests plus browser redirect behavior.
- `requirements.txt`: pinned runtime/test dependencies.
- `Dockerfile.api`: unprivileged FastAPI image.
- `.dockerignore`: minimal build context and secret exclusions.
- `compose.yaml`: FastAPI service, SQLite volume, health check, and scoped Traefik route.
- `.env.example`: non-secret configuration contract.
- `README.md`: sandbox configuration, deployment, webhook, and acceptance procedure.

### Task 1: Validate runtime configuration and initialize SQLite

**Files:**
- Create: `payments_api/__init__.py`
- Create: `payments_api/config.py`
- Create: `payments_api/store.py`
- Create: `tests/test_api_config.py`
- Create: `tests/test_checkout_store.py`

**Interfaces:**
- Consumes: environment mapping with Stripe, URL, and database values.
- Produces: `Settings.from_mapping(values: Mapping[str, str]) -> Settings` and `CheckoutStore(path: str)` with `initialize()`, `create_checkout(reference)`, `attach_session(reference, session_id)`, `mark_creation_failed(reference)`, `complete_checkout(event)`, and `get_checkout(reference)`.

- [ ] **Step 1: Write failing settings tests**

Create `tests/test_api_config.py` with cases asserting that this complete valid mapping succeeds:

```python
VALID = {
    "STRIPE_SECRET_KEY": "rk_test_example",
    "STRIPE_WEBHOOK_SECRET": "whsec_example",
    "STRIPE_TICKERPULSE_PRICE_ID": "price_1UIW1FJMVS0qQfgEkAA4kLPY",
    "STRIPE_INTEGRATION_IDENTIFIER": "tickerpulse_fastapi_qzrmhptk",
    "CHECKOUT_BASE_URL": "https://pay.ediacarian.dedyn.io",
    "SQLITE_PATH": ":memory:",
}
```

Add individual tests requiring `ValueError` for every missing key, non-HTTPS or credential-bearing `CHECKOUT_BASE_URL`, a non-`price_` Price ID, an integration identifier whose suffix is not exactly eight lowercase ASCII letters, and an empty SQLite path.

- [ ] **Step 2: Run the settings tests and verify red**

Run: `python3 -m unittest tests/test_api_config.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'payments_api'`.

- [ ] **Step 3: Implement immutable settings validation**

Create `payments_api/config.py` with a frozen `Settings` dataclass containing `stripe_secret_key`, `stripe_webhook_secret`, `price_id`, `integration_identifier`, `checkout_base_url`, and `sqlite_path`. Implement `from_mapping` using `urllib.parse.urlsplit`, require HTTPS with a hostname and no username/password/query/fragment, remove a trailing slash from the accepted origin, and validate the Price and integration-identifier patterns with full-match regular expressions.

- [ ] **Step 4: Run the settings tests green**

Run: `python3 -m unittest tests/test_api_config.py -v`

Expected: all settings tests PASS.

- [ ] **Step 5: Write failing SQLite state tests**

Create `tests/test_checkout_store.py` using a temporary database file. Require the following behavior:

```python
store.initialize()
store.create_checkout("checkout-ref")
store.attach_session("checkout-ref", "cs_test_123")
record = store.get_checkout("checkout-ref")
self.assertEqual(record.state, "pending")
self.assertEqual(record.session_id, "cs_test_123")
```

Add tests proving `mark_creation_failed` sets state `creation_failed`; a completion writes Customer and Subscription IDs; duplicate Event IDs return `False` without a second update; unknown checkout references raise `UnknownCheckoutReference` and do not retain the Event ID; and initialization fails on an unwritable/nonexistent parent path.

- [ ] **Step 6: Run the store tests and verify red**

Run: `python3 -m unittest tests/test_checkout_store.py -v`

Expected: FAIL because `CheckoutStore` is not defined.

- [ ] **Step 7: Implement the transactional store**

Create `payments_api/store.py` with:

```sql
CREATE TABLE IF NOT EXISTS checkout_records (
  checkout_reference TEXT PRIMARY KEY,
  session_id TEXT UNIQUE,
  customer_id TEXT,
  subscription_id TEXT,
  state TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stripe_events (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  processed_at TEXT NOT NULL
);
```

Use one SQLite connection per method with `PRAGMA foreign_keys=ON`, explicit `BEGIN IMMEDIATE` for webhook completion, ISO-8601 UTC timestamps, and a `CheckoutRecord` frozen dataclass. Define `CheckoutCompletion(event_id, event_type, checkout_reference, session_id, customer_id, subscription_id)` and `UnknownCheckoutReference`. Insert the Event ID only after the checkout row has been found and updated so failures roll back cleanly.

- [ ] **Step 8: Run Task 1 tests green**

Run: `python3 -m unittest tests/test_api_config.py tests/test_checkout_store.py -v`

Expected: all tests PASS.

- [ ] **Step 9: Commit Task 1**

```bash
git add payments_api tests/test_api_config.py tests/test_checkout_store.py
git commit -m "feat: add payment service configuration and store"
```

### Task 2: Add the Stripe SDK gateway and Checkout endpoint

**Files:**
- Create: `payments_api/stripe_gateway.py`
- Create: `payments_api/main.py`
- Create: `tests/test_checkout_api.py`
- Create: `requirements.txt`

**Interfaces:**
- Consumes: `Settings`, `CheckoutStore`, and Stripe's Checkout Sessions API.
- Produces: `StripeGateway.create_subscription_checkout(checkout_reference: str) -> HostedCheckout`, `StripeGateway.construct_event(payload: bytes, signature: str) -> Mapping[str, object]`, and `create_app(settings, gateway, store) -> FastAPI`.

- [ ] **Step 1: Add pinned dependencies**

Create `requirements.txt` with direct pins:

```text
fastapi==0.119.0
httpx==0.28.1
stripe==15.4.0
uvicorn==0.37.0
```

Install them in an isolated environment before running tests. If a listed FastAPI or Uvicorn release is unavailable from the configured package index, stop and update the pin to the newest available release supported by Python 3.12, documenting the resolved pin in the commit rather than using an unpinned dependency.

- [ ] **Step 2: Write the failing Checkout API tests**

Create `tests/test_checkout_api.py` with a `FakeStripeGateway` that captures `checkout_reference` and returns `HostedCheckout(session_id="cs_test_123", url="https://checkout.stripe.com/c/pay/test")`. Use `TestClient(create_app(...))` and assert:

- `POST /api/checkout-sessions` returns HTTP 201 with only `checkout_url`;
- the store contains the generated reference and `cs_test_123` in `pending` state;
- two requests generate distinct references;
- a gateway exception returns HTTP 502, marks the reference `creation_failed`, and exposes no exception text; and
- a gateway URL outside `https://checkout.stripe.com` returns HTTP 502 and marks creation failed.

- [ ] **Step 3: Run the endpoint tests and verify red**

Run: `python3 -m unittest tests/test_checkout_api.py -v`

Expected: FAIL because the gateway and application factory do not exist.

- [ ] **Step 4: Implement the Stripe gateway**

In `payments_api/stripe_gateway.py`, define frozen `HostedCheckout` and `StripeGateway`. Construct `stripe.StripeClient(settings.stripe_secret_key)` without an API-version argument. Call:

```python
self._client.v1.checkout.sessions.create({
    "mode": "subscription",
    "line_items": [{"price": settings.price_id, "quantity": 1}],
    "managed_payments": {"enabled": True},
    "success_url": (
        f"{settings.checkout_base_url}/?checkout=success"
        "&session_id={CHECKOUT_SESSION_ID}"
    ),
    "cancel_url": f"{settings.checkout_base_url}/?checkout=cancelled",
    "client_reference_id": checkout_reference,
    "metadata": {"product": "tickerpulse", "environment": "sandbox"},
    "integration_identifier": settings.integration_identifier,
})
```

Do not add `payment_method_types`, `automatic_tax`, an explicit API version, or the publishable key. Normalize the response to non-empty `id` and HTTPS `checkout.stripe.com` URL fields, otherwise raise `InvalidStripeResponse`.

- [ ] **Step 5: Implement the Checkout route**

In `payments_api/main.py`, implement `create_app`. On `POST /api/checkout-sessions`, generate `uuid.uuid4().hex`, create the local row before the Stripe call, attach the returned session, and return `JSONResponse(status_code=201, content={"checkout_url": hosted.url})`. On any gateway or persistence failure after record creation, best-effort mark it `creation_failed`, log only the exception class and checkout reference, and return `{"detail": "Checkout is temporarily unavailable."}` with HTTP 502.

- [ ] **Step 6: Run Checkout tests green**

Run: `python3 -m unittest tests/test_checkout_api.py -v`

Expected: all Checkout tests PASS.

- [ ] **Step 7: Commit Task 2**

```bash
git add requirements.txt payments_api/stripe_gateway.py payments_api/main.py tests/test_checkout_api.py
git commit -m "feat: create managed payments checkout sessions"
```

### Task 3: Verify and persist signed Checkout webhooks

**Files:**
- Modify: `payments_api/stripe_gateway.py`
- Modify: `payments_api/main.py`
- Create: `tests/test_webhook_api.py`

**Interfaces:**
- Consumes: raw HTTP body, `Stripe-Signature`, Stripe Event mappings, and `CheckoutStore.complete_checkout`.
- Produces: idempotent `POST /api/stripe/webhook` responses and completed checkout records.

- [ ] **Step 1: Write failing webhook tests**

Create `tests/test_webhook_api.py` with a fake verifier that returns this event:

```python
{
    "id": "evt_test_123",
    "type": "checkout.session.completed",
    "data": {"object": {
        "id": "cs_test_123",
        "client_reference_id": "checkout-ref",
        "customer": "cus_test_123",
        "subscription": "sub_test_123",
    }},
}
```

Seed `checkout-ref` first. Assert a valid event returns HTTP 200 and persists all three Stripe IDs; the same event twice returns HTTP 200 and one Event row; missing signature and verifier rejection return HTTP 400 with no database changes; unknown references and missing required Stripe IDs return HTTP 500 without retaining the Event ID; expanded `customer` and `subscription` objects normalize their `id`; and unrelated valid event types return HTTP 200 without adding an Event row.

- [ ] **Step 2: Run the webhook tests and verify red**

Run: `python3 -m unittest tests/test_webhook_api.py -v`

Expected: FAIL because `/api/stripe/webhook` is absent.

- [ ] **Step 3: Implement signature verification and event normalization**

Add `StripeGateway.construct_event(payload, signature)` using `stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)`. In `main.py`, add a helper that accepts either a Stripe ID string or an expanded mapping with a non-empty `id`, and rejects all other forms.

- [ ] **Step 4: Implement the webhook route**

Read `await request.body()` before any JSON parsing. Require `Stripe-Signature`. Map Stripe signature/payload exceptions to HTTP 400. For `checkout.session.completed`, validate Event ID, session ID, reference, Customer ID, and Subscription ID, then call `store.complete_checkout`. Return `{"received": True, "duplicate": bool}`. Map validation, unknown-reference, and persistence failures to HTTP 500 so Stripe retries. Do not log the raw body, signature, API key, signing secret, Checkout URL, or customer data.

- [ ] **Step 5: Run all API and store tests green**

Run: `python3 -m unittest tests/test_api_config.py tests/test_checkout_store.py tests/test_checkout_api.py tests/test_webhook_api.py -v`

Expected: all tests PASS.

- [ ] **Step 6: Commit Task 3**

```bash
git add payments_api/stripe_gateway.py payments_api/main.py tests/test_webhook_api.py
git commit -m "feat: verify and record Stripe checkout webhooks"
```

### Task 4: Connect the static TickerPulse action to FastAPI

**Files:**
- Modify: `site/index.html`
- Modify: `site/app.js`
- Modify: `site/styles.css`
- Modify: `site/config.js`
- Modify: `tests/test_payment_page.py`

**Interfaces:**
- Consumes: `POST /api/checkout-sessions -> {checkout_url: string}`.
- Produces: an accessible Subscribe button that navigates only to an HTTPS `checkout.stripe.com` destination.

- [ ] **Step 1: Write failing browser-contract tests**

Extend the existing Node-backed test harness to mock `fetch` and `window.location.assign`. Add tests asserting that clicking Subscribe sends one empty POST to `/api/checkout-sessions`, sets `disabled` and `aria-busy` during the request, redirects to a valid Stripe Checkout URL, restores the button after network/API/JSON failures, and refuses `http`, credentials, subdomain lookalikes, or non-Stripe hostnames returned by the API.

Update the existing URL-configuration tests so they cover only Custom Service, Tip, and Customer Portal; TickerPulse no longer consumes a committed Payment Link URL.

- [ ] **Step 2: Run the page tests and verify red**

Run: `python3 -m unittest tests/test_payment_page.py -v`

Expected: FAIL because TickerPulse remains a configured anchor.

- [ ] **Step 3: Implement the Checkout button flow**

Replace the TickerPulse anchor with:

```html
<button id="tickerPulseCheckoutButton" class="button" type="button">
  Subscribe
</button>
<p id="tickerPulseCheckoutError" class="checkout-error" role="alert" hidden></p>
```

Add `isAllowedCheckoutUrl`, `setTickerPulseBusy`, and `configureTickerPulseCheckout` to `site/app.js`. Validate `url.protocol === "https:"`, `url.hostname === "checkout.stripe.com"`, and empty username/password before calling `window.location.assign`. Use the generic message `Checkout is temporarily unavailable. Please try again.` for every failure. Remove `tickerPulsePaymentLinkUrl` from `site/config.js` and preserve the other three public URL settings.

- [ ] **Step 4: Run the page tests green**

Run: `python3 -m unittest tests/test_payment_page.py -v`

Expected: all page tests PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add site tests/test_payment_page.py
git commit -m "feat: start TickerPulse checkout through FastAPI"
```

### Task 5: Containerize and route the FastAPI service on the VPS

**Files:**
- Create: `payments_api/runtime.py`
- Create: `Dockerfile.api`
- Create: `.dockerignore`
- Modify: `compose.yaml`
- Modify: `.env.example`
- Modify: `tests/test_payment_page.py`

**Interfaces:**
- Consumes: ignored `.env`, `payments_api.runtime:app`, external `vps-srv_traefik_public`, and Docker volume `payments_data`.
- Produces: internal FastAPI port 8000, public `/api` routing, private `/healthz`, and durable `/data/stripe-payments.sqlite3`.

- [ ] **Step 1: Write failing deployment-contract tests**

Extend `tests/test_payment_page.py` to require a `payments-api` Compose service that:

- builds `Dockerfile.api`, has no `ports`, and joins only `traefik_public`;
- loads `.env`, mounts `payments_data:/data`, uses `read_only: true`, and has a health check;
- routes exactly `Host(pay.ediacarian.dedyn.io) && PathPrefix(/api)` with priority greater than the static router;
- targets internal port 8000 and reuses the security-header middleware;
- configures `SQLITE_PATH=/data/stripe-payments.sqlite3`; and
- declares `payments_data` as a named volume.

Add tests that `.dockerignore` excludes `.env`, `secrets`, `.git`, SQLite files, caches, and `.specstory`; `.env.example` contains only placeholders; and `payments_api/runtime.py` fails startup when the database parent is not writable.

- [ ] **Step 2: Run deployment tests and verify red**

Run: `python3 -m unittest tests/test_payment_page.py -v`

Expected: FAIL because the API image and Compose service are absent.

- [ ] **Step 3: Implement production runtime and image**

Create `payments_api/runtime.py` to call `Settings.from_mapping(os.environ)`, initialize the store, construct `StripeGateway`, and expose `app = create_app(...)`. Add `GET /healthz` in `create_app` that executes `SELECT 1` through `store.is_ready()` and returns HTTP 200 only when ready.

Create `Dockerfile.api` based on `python:3.12-slim`, install `requirements.txt`, copy only `payments_api`, create an unprivileged `payments` user, and run:

```text
uvicorn payments_api.runtime:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=*
```

- [ ] **Step 4: Add scoped Compose routing and storage**

Add the `payments-api` service with `.env`, read-only root filesystem, `/tmp` tmpfs, the named data volume, internal health check, and Traefik labels. Use router priority `200`, keep the static router at its existing default priority, and do not add a host-port mapping or a DGX/Tailscale network.

- [ ] **Step 5: Update non-secret environment templates**

Set these exact placeholder/default lines in `.env.example`:

```dotenv
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_TICKERPULSE_PRICE_ID=price_1UIW1FJMVS0qQfgEkAA4kLPY
STRIPE_INTEGRATION_IDENTIFIER=tickerpulse_fastapi_qzrmhptk
CHECKOUT_BASE_URL=https://pay.ediacarian.dedyn.io
SQLITE_PATH=/data/stripe-payments.sqlite3
```

Do not add the supplied publishable key because this hosted Checkout flow does not use it.

- [ ] **Step 6: Run deployment verification green**

Run: `python3 -m unittest discover -s tests -v`

Run: `docker compose config --quiet`

Run: `docker build -f Dockerfile.api -t stripe-payments-api:test .`

Run: `git diff --check`

Expected: all tests PASS, Compose validates, the image builds, and no whitespace errors are reported.

- [ ] **Step 7: Commit Task 5**

```bash
git add payments_api/runtime.py Dockerfile.api .dockerignore compose.yaml .env.example tests/test_payment_page.py
git commit -m "feat: deploy FastAPI payments service behind Traefik"
```

### Task 6: Document secure operation and verify the complete local slice

**Files:**
- Modify: `README.md`
- Modify: `secrets/README.md`
- Modify: `tests/test_payment_page.py`

**Interfaces:**
- Consumes: the implemented service, existing SOPS scripts, sandbox Price, and public HTTPS hostname.
- Produces: a reproducible operator procedure without plaintext credentials.

- [ ] **Step 1: Write failing documentation tests**

Require the README files to name the exact sandbox Product and Price IDs, FastAPI routes, Managed Payments behavior, SQLite volume, restricted-key recommendation, SOPS commands, webhook event type, and sandbox acceptance procedure. Assert they state that the publishable key is unused and live mode is out of scope.

- [ ] **Step 2: Run documentation tests and verify red**

Run: `python3 -m unittest tests/test_payment_page.py -v`

Expected: FAIL because documentation still describes Payment Links only.

- [ ] **Step 3: Replace obsolete TickerPulse Payment Link instructions**

Document this operator sequence:

1. use `scripts/secrets/edit.sh .env` to enter a sandbox restricted key and webhook signing secret without printing either value;
2. run `scripts/secrets/check.sh` and confirm `.env` restores with mode 600;
3. run all unit tests, Compose validation, and the API image build;
4. deploy with `docker compose -p stripe-payments up -d --build`;
5. verify `/`, `/api` routing behavior, container health, and normal TLS;
6. create the sandbox webhook destination only after the public endpoint is healthy;
7. test Checkout with Stripe's published sandbox payment method; and
8. verify one completed local record and idempotent webhook replay.

State that Custom Service and Tip remain separate Payment Link work and are not made available by this slice.

- [ ] **Step 4: Run full local verification**

Run: `python3 -m unittest discover -s tests -v`

Run: `docker compose config --quiet`

Run: `docker build -f Dockerfile.api -t stripe-payments-api:test .`

Run: `bash scripts/secrets/check.sh`

Run: `git diff --check`

Run: `git status --short`

Expected: tests and validation PASS; secret round-trip succeeds without plaintext output; only known unrelated untracked paths remain.

- [ ] **Step 5: Commit Task 6**

```bash
git add README.md secrets/README.md tests/test_payment_page.py
git commit -m "docs: explain managed payments operation"
```

### Task 7: Deploy the sandbox endpoint and complete Stripe acceptance

**Files:**
- Create: `docs/deployments/2026-09-22-managed-payments-fastapi.md`

**Interfaces:**
- Consumes: reviewed commit, encrypted sandbox credentials, VPS Docker/Traefik access, and Stripe sandbox `acct_1UIUebJMVS0qQfgE`.
- Produces: healthy public API, one Stripe webhook destination, one completed sandbox subscription, and redacted evidence.

- [ ] **Step 1: Verify the release preconditions**

Record the exact commit, image digest, current public listeners, existing `pay-page` state, and absence of any webhook endpoint in the sandbox. Do not print `.env`, Docker environment values, SOPS plaintext, API keys, or signing secrets.

- [ ] **Step 2: Deploy without disturbing other services**

Run the repository's documented deployment command for Compose project `stripe-payments`. Verify both containers are healthy, only Traefik publishes ports 80/443, the API container has no host port, and no Traefik, SciFact, TickerPulse, procurement, or DGX service was restarted.

- [ ] **Step 3: Verify public routing before webhook registration**

Require normal TLS validation, `/` HTTP 200, an unsupported method or path under `/api` returning an application response from FastAPI, and direct container `/healthz` HTTP 200 from the VPS. Confirm the webhook URL is reachable without following insecure redirects.

- [ ] **Step 4: Register exactly one sandbox webhook destination**

Create `https://pay.ediacarian.dedyn.io/api/stripe/webhook` for only `checkout.session.completed` in sandbox `acct_1UIUebJMVS0qQfgE`. Enter the returned signing secret directly into the SOPS edit workflow without echoing, logging, committing, or pasting it into chat, then redeploy only `payments-api`. Re-read Stripe's webhook endpoint list and confirm one enabled destination.

- [ ] **Step 5: Complete an interactive sandbox Checkout**

Start Checkout from the deployed page, confirm the hosted page displays TickerPulse at $1/month with Managed Payments, use Stripe's test payment details, and return to the success URL. This user-visible payment confirmation remains a distinct acceptance action from API/session creation.

- [ ] **Step 6: Verify webhook and persistence evidence**

Confirm Stripe reports one successful `checkout.session.completed` delivery. Query only non-secret SQLite columns to verify the matching Checkout Session, Customer, and Subscription IDs and `completed` state. Redeliver the same Event and confirm the row counts and identifiers do not change.

- [ ] **Step 7: Re-read the Stripe subscription**

Using the Stripe connector, retrieve the created Subscription and its Price. Confirm sandbox mode, active/trialing status as applicable, amount 100 USD minor units monthly, TickerPulse Product ID, and Managed Payments provenance. Do not infer entitlements from the browser redirect alone.

- [ ] **Step 8: Record redacted deployment evidence and commit**

Write `docs/deployments/2026-09-22-managed-payments-fastapi.md` with timestamps, commit/image digests, HTTP status evidence, Stripe resource IDs, webhook delivery status, database row counts, and explicit live-mode/entitlement exclusions. Exclude all credentials, request signatures, card test data, and customer details.

```bash
git add docs/deployments/2026-09-22-managed-payments-fastapi.md
git commit -m "docs: record managed payments sandbox acceptance"
```
