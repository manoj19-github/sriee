# Coding Log — 130000 Register Device Identity v1

| Field | Value |
|---|---|
| Date | 2026-07-05 |
| Global ID | `130000` |
| Status | Complete |

## Delivered

- Added explicit-setup-only registration using a canonical installation UUID.
- Resolved the actor from the current Windows process-token SID and rejected
  non-interactive session 0; no caller-supplied user identity is accepted.
- Added current-user Microsoft Software KSP P-256 key creation with export policy
  disabled. Python receives only SEC1 public material and an opaque key reference.
- Derived stable `dev_` identity from the public-key SHA-256 digest and exposed a
  database-safe record that omits key reference and registration-session metadata.
- Made repeat registration idempotent, prevented user/install and device collisions,
  checked stored identities against the local public key, and removed newly created
  keys after failed registry persistence.
- Added an atomic in-memory registry and protocols for a durable registry, trusted
  user resolver and platform key store.

No package was added. The implementation uses Python's standard library and Windows
CNG APIs; `requirements.txt` retains all exact pins.

## Evidence

- Focused suite: **24 passed in 0.36 seconds**.
- Full backend regression: **641 passed in 4.87 seconds**.
- Live Windows checks created/reopened/deleted a persisted CNG key and resolved the
  current process token SID and interactive session.
- Full regression and repository integrity evidence are recorded in the testing log.
