# Versioning Log — 130000 Register Device Identity v1

| Field | Value |
|---|---|
| Date | 2026-07-05 |
| Global ID | `130000` |
| Version | `v1` |
| Lifecycle | `current` |

## Contract

- Registration requires explicit Boolean consent and a canonical version-4
  installation UUID.
- The trusted actor binding is the current Windows token SID; session 0 is rejected.
- Production keys are current-user persisted P-256 keys in Windows CNG with private
  export disabled.
- Public keys use uncompressed SEC1 format and `ECDSA_P256_SHA256`; device IDs use
  `dev_` plus the first 128 bits of the public-key SHA-256 digest.
- Repeat registration for the same install and actor is idempotent. Rebinding,
  missing keys, public-key mismatch and identity collisions fail closed.
- Database-safe records contain public identity only. Private key bytes are never
  returned by this contract.

No API route, graph topology, database migration or dependency version changed.
Rollback removes the module, exports, tests and records; any test key is deleted by
the test and production keys require an explicit future lifecycle/revocation path.
