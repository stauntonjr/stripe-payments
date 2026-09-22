# TickerPulse Managed Payments sandbox acceptance

## Scope and result

The TickerPulse FastAPI integration was deployed to the existing VPS and passed
sandbox acceptance on 2026-09-22. This evidence covers only Stripe sandbox
account `acct_1UIUebJMVS0qQfgE`; no live-mode resource or credential was used.

The accepted service sells the automated TickerPulse digital subscription. It
does not establish application entitlements, RSS or Telegram provisioning,
Custom Service payments, Tip payments, or live-payment readiness.

## Deployment identity

- Git commit: `76687da01b344954feedf9a3733db57f4a306664`
- VPS checkout: `/home/ubuntu/stripe-payments`
- Compose project: `stripe-payments`
- API image: `sha256:f87336c60b63e754e0ab42650c94daaa205343a46c3003ef430777bbd8a676e7`
- Static image: `sha256:47ce8258a10e28ce4b4498588c25ef77ae328f4c56cbe3e8d5dcf4f6d8019997`
- Verification timestamp: `2026-09-22T18:07:28Z`

Both payment containers had empty host-port bindings. Traefik remained the only
owner of public edge ports 80 and 443. Existing Traefik, procurement, DDNS, and
Alloy container IDs were unchanged across deployment. No SciFact, TickerPulse,
or DGX service was restarted.

The initial uncached Python image build temporarily saturated the 956 MB VPS and
caused slow SSH/TLS responses plus one transient procurement health-check
failure. The build completed without an OOM kill; the existing procurement
container returned healthy without restart. The final cached rebuild did not
repeat the saturation.

## DNS, TLS, and routing

- deSEC RRset: CNAME `pay` to `ediacarian.dedyn.io.`, TTL 3600
- Resolved address: `193.122.204.110`
- `GET https://pay.ediacarian.dedyn.io/`: HTTP 200, TLS verification result 0
- `GET https://pay.ediacarian.dedyn.io/api/not-found`: FastAPI JSON HTTP 404,
  TLS verification result 0
- Container-internal `GET /healthz`: HTTP 200
- Certificate subject: `CN=pay.ediacarian.dedyn.io`
- Issuer: Let's Encrypt YR1
- Validity: 2026-09-22 16:22:38 UTC through 2026-12-21 16:22:37 UTC
- SHA-256 fingerprint:
  `07:33:C7:41:AB:88:E8:18:C3:0E:1A:29:43:94:C2:6D:48:9D:0B:87:0C:A2:B7:59:01:2D:D7:8E:04:88:9D:63`

Traefik used its existing deSEC DNS-01 resolver and configured 300-second
propagation delay. No alternate certificate mechanism or TLS bypass was used.

## Stripe resources

- Product: `prod_VJ8HawUafhUacx`, TickerPulse, active, sandbox
- Product tax code: `txcd_10103000`
- Price: `price_1UIW1FJMVS0qQfgEkAA4kLPY`
- Price terms: 100 USD minor units monthly, quantity 1, tax inclusive
- Webhook endpoint: `we_1UIXlSJMVS0qQfgEF40q13Ae`, enabled, sandbox
- Webhook URL: `https://pay.ediacarian.dedyn.io/api/stripe/webhook`
- Enabled event: `checkout.session.completed` only
- Checkout Session:
  `cs_test_a1hpmetUvc82bdVdOrSNDcIlGhAvrXMhRa37DMMvytP7XlByPBMjZjHTak`
- Checkout result: complete and paid, 100 USD minor units total, Managed
  Payments enabled, automatic tax complete
- Subscription: `sub_1UIXrGJMVS0qQfgE2KtO9jME`, active, sandbox, Managed
  Payments enabled
- Customer: `cus_VJABc3q6Onluuf`
- Completion Event: `evt_1UIXrJJMVS0qQfgEh2yVFD3z`

No credentials, webhook signatures, payment-method data, or customer contact and
address details are retained in this record.

## Webhook and persistence acceptance

The first production delivery exposed an SDK integration defect: Stripe Python
15 returned an Event object without `.get()`. Commit `76687da` normalizes verified
SDK events to plain mappings and adds a real-SDK regression test. Stripe then
redelivered the original Event successfully.

After the first successful delivery:

- the matching checkout state was `completed`;
- Session, Customer, and Subscription IDs were persisted;
- `checkout_records` contained 2 rows (one preflight Session and one completed
  interactive Session); and
- `stripe_events` contained exactly 1 row for the completion Event.

The same Event was redelivered a second time. Both deliveries returned HTTP 200,
the checkout identifiers and completion timestamp remained unchanged, and
`stripe_events` remained at exactly 1 row. This verifies deployed idempotency.

The success return page was also corrected to display “Subscription checkout
completed. Your payment is being confirmed.” rather than the unrelated warning
for unconfigured Custom Service and Tip links.

## Verification gates

- Complete local unit suite: 44 tests passed
- Local API image build: passed
- Compose validation: passed
- SOPS encrypted round trip: passed; restored `.env` mode 600
- Public root/TLS check: passed
- Public API routing check: passed
- Internal database-backed health check: passed
- Signed completion webhook: passed
- Duplicate signed webhook replay: passed and idempotent
- Stripe Subscription and Price re-read: passed

Browser success alone was not treated as fulfillment evidence. Acceptance
required the signed completion Event, persisted identifiers, and Stripe-side
Subscription re-read. Application entitlement provisioning remains outside this
integration and must not be inferred from these results.
