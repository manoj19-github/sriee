# Coding Log — 130001 Authenticate Session v1

| Field | Value |
|---|---|
| Date | 2026-07-05 |
| Global ID | `130001` |
| Status | Complete |

## Delivered

- Added short-lived random challenges bound to the registered device, actor and
  backend instance.
- Added a deterministic, domain-separated proof transcript covering server and client
  nonces, device, actor, Windows session and requested contract bounds.
- Extended the non-exportable Windows CNG key store with SHA-256/P-256 signing; only
  the fixed-width signature crosses the platform boundary.
- Verified registered SEC1 public keys and raw P-256 signatures with the pinned
  `cryptography` implementation, including device-ID/public-key consistency.
- Consumed challenges atomically only after proof verification, preventing both
  replay races and invalid-proof challenge burning.
- Added bounded challenge storage with expired-state cleanup and atomic session
  rotation that revokes the prior session and advances the device epoch.
- Issued five-minute JWTs bound to backend instance and Windows session. Extended the
  existing 110002 validator to require those bindings whenever session metadata does.
- Added strict rotation-result validation and sanitized all external failures.

`requirements.txt` adds exact pins for `cryptography==46.0.5` and its declared
runtime dependencies `cffi==2.0.0` and `pycparser==2.23` (78 exact pins total).

## Evidence

- Focused 130001 suite: **24 passed in 0.35 seconds**.
- Full backend regression: **665 passed in 5.68 seconds**.
- Live Windows CNG proof generation and backend public-key verification: **PASS**.
