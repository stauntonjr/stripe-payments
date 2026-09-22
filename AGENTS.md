# Repository guidance

This is a public repository. Never commit plaintext secrets or private age keys.
Use the SOPS/age manifest workflow documented in secrets/README.md. Public Stripe
Payment Link URLs are not secrets. Never print decrypted credentials in logs.

Current scope is repository setup only. Do not treat the README's planned payment
flows as implemented. Use test mode for future development; live payment changes
and deployment require explicit user direction.

Before pushing changes to the secrets tooling, verify encrypt/decrypt round-trip,
restored file permissions, and plaintext Git ignore rules. Do not introduce real
credentials just to test encryption.
