# stripe-payments

Public repository for exploring Stripe one-time payments, subscriptions, and tips.

## Status

Repository and SOPS/age secrets workflow are set up. No payment application,
Stripe account configuration, products, prices, webhook endpoint, or deployment
has been created yet. The encrypted environment file contains empty placeholders,
not real credentials. No live payments can be collected by this repository yet.

## Intended first integration

Use Stripe-hosted Payment Links for three website actions:

- **Pay:** a fixed-price, one-time purchase.
- **Subscribe:** a recurring plan with a customer portal link to manage billing.
- **Leave a tip:** a one-time, customer-chosen amount.

Public Payment Link URLs can be committed as ordinary website configuration.
They do not require a secret API key. If a later integration unlocks paid content,
use server-side verified payment/subscription events, not a browser redirect, to
control access. Keep API keys and webhook signing secrets on the server.

Start in Stripe test mode. Live-mode activation and deployment are separate steps.
Subscription checkout should show the amount and billing interval clearly and
provide an accessible cancellation route.

## Secrets setup

This follows the dotfiles SOPS/age convention: `.sops.yaml`, a manifest,
`secrets/store/**/*.sops`, and local helper scripts. Only the public age recipient
is reused; no dotfiles credentials or private keys were copied.

On macOS, install prerequisites if needed:

```sh
brew install sops age
```

The existing age private key must be available locally at
`~/.config/sops/age/keys.txt`, or through `SOPS_AGE_KEY_FILE` / `SOPS_AGE_KEY`.
Never add that private key to this repository. See [secrets instructions](secrets/README.md).

```sh
# Verify decryption without leaving plaintext behind
bash scripts/secrets/check.sh

# Restore ignored .env with mode 600
bash scripts/secrets/decrypt-all.sh

# Edit locally and re-encrypt
EDITOR=nano bash scripts/secrets/edit.sh .env

# Or encrypt after editing .env yourself
bash scripts/secrets/encrypt-all.sh
```

Review and commit the encrypted file after changes. The edit/decrypt commands
leave `.env` locally; it is ignored by Git. Delete it when no longer needed.

## References

- [Stripe Payment Links](https://docs.stripe.com/payment-links)
- [Stripe customer portal](https://docs.stripe.com/customer-management)
- [Stripe webhook signatures](https://docs.stripe.com/webhooks/signature)
- [SOPS](https://github.com/getsops/sops)
