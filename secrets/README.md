# Secrets workflow

`manifest.tsv` maps a repo-relative plaintext file to its encrypted `.sops` file
and restored permissions. The initial entry is `.env` with permissions `600`.
All values are encrypted as a binary SOPS payload; the public age recipient and
SOPS metadata remain visible. The initial payload has empty Stripe placeholders.

Use the same age private key as dotfiles. The private key stays outside Git.
Anyone with this private key can decrypt files encrypted to this recipient in
either repository. Store a secure backup separately.

Run helpers from any working directory:

- `bash scripts/secrets/check.sh`: decrypt into a temporary directory, then clean up.
- `bash scripts/secrets/decrypt-all.sh`: restore local plaintext files.
- `bash scripts/secrets/encrypt-all.sh`: encrypt local plaintext files.
- `EDITOR=nano bash scripts/secrets/edit.sh .env`: decrypt, edit, and re-encrypt.

These commands do not print secret values. Do not use shell tracing (`set -x`)
while handling credentials. Editors can create backups; use an editor configured
not to persist sensitive backups. Local plaintext remains after editing.

Before adding another manifest entry, add its plaintext path to `.gitignore`.
Never force-add a plaintext file. Commit only the encrypted result. Ignore rules
cannot prevent deliberately forced additions or detect secrets in arbitrary files.
If a credential enters public Git history, revoke/rotate it immediately; encrypting
the latest version does not erase earlier commits.

Do not copy your age private key into public CI. Public validation should not need
production secrets. Configure deployment credentials separately when hosting is
chosen. Hosted Payment Links alone need no API credentials.
