# Testing Log — 130000 Register Device Identity v1

| Field | Value |
|---|---|
| Date | 2026-07-05 |
| Global ID | `130000` |
| Environment | Windows, repository Python environment |
| Result | **PASS — 641 passed in 4.87 seconds** |

Focused `test_device_identity.py`: **24 passed in 0.36 seconds**.

Coverage includes explicit consent type, canonical install identity, trusted
interactive-user binding, sanitized resolver failures, idempotency, anti-rebinding,
local/public key matching, unique device identity, concurrent convergence, registry
failure cleanup, pre-existing-key preservation, malformed public material and
timezone validation.

The focused suite also uses the real Microsoft Software Key Storage Provider to
create, reopen and delete a current-user persisted P-256 key, and uses the real
process token to resolve a Windows SID and interactive session. No private key,
credential, environment value or raw external failure is logged.

Full backend: **641 passed in 4.87 seconds**. Python compilation, 75 exact dependency
pins, function-map counts (**199 total / 168 planned / 31 complete**) and Git
whitespace checks pass. No database, network endpoint or production registration ran.
