# Secrets workflow

`manifest.tsv` maps the repo-relative plaintext `.env` to
`secrets/store/dotenv/env.sops` and restores it with mode 600. The encrypted file
may be committed; `.env` and the age private key must never be committed.

For this sandbox service, `.env` contains:

- `STRIPE_SECRET_KEY`: a restricted sandbox key, not a live or unrestricted key.
- `STRIPE_WEBHOOK_SECRET`: the sandbox webhook destination signing secret.
- `STRIPE_TICKERPULSE_PRICE_ID`: the non-secret existing Price ID.
- `STRIPE_INTEGRATION_IDENTIFIER`: the non-secret integration identifier.
- `CHECKOUT_BASE_URL`: the public HTTPS origin.
- `SQLITE_PATH`: the container database path.

The browser publishable key is not required for Stripe-hosted Checkout and should
not be added. Start from `.env.example`; it contains placeholders and non-secret
defaults only.

Use the same age private key as dotfiles. The private key stays outside Git and
must be available at `~/.config/sops/age/keys.txt` or through
`SOPS_AGE_KEY_FILE` / `SOPS_AGE_KEY`.

Run helpers from any working directory:

- `bash scripts/secrets/check.sh`: decrypt into a temporary directory, verify the
  manifest, then clean up without printing values.
- `bash scripts/secrets/decrypt-all.sh`: restore ignored plaintext files with
  their manifest permissions.
- `bash scripts/secrets/encrypt-all.sh`: encrypt local plaintext files.
- `EDITOR=nano bash scripts/secrets/edit.sh .env`: decrypt, edit, and re-encrypt.

After editing, verify the round trip and restored mode 600:

```sh
bash scripts/secrets/check.sh
bash scripts/secrets/decrypt-all.sh
stat -c '%a %n' .env
```

These commands do not print secret values. Do not use shell tracing (`set -x`).
Use an editor that does not persist backups. Local plaintext remains after an
edit or restore and is ignored by Git, but ignore rules cannot prevent a forced
addition.

Before adding a manifest entry, add its plaintext path to `.gitignore`. Commit
only the encrypted result. If a credential enters public Git history, revoke or
rotate it immediately; encrypting a later revision does not erase history.

Do not copy the age private key into public CI. Never introduce real credentials
only to test encryption. Live Stripe credentials and live deployment require
separate explicit authorization.
