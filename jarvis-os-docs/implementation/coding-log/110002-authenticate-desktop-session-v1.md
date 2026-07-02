# Coding Log — 110002 Authenticate Desktop Session v1

| Field | Value |
|---|---|
| Record | CODE-20260702-110002 |
| Date | 2026-07-02 |
| Global ID | 110002 |
| Canonical name | `python-fastapi-authenticate-desktop-mandatory-p0-complete-current-v1` |
| Status transition | `planned → complete` after full backend tests |
| Source | `backend/src/jarvis/security/desktop_auth.py`, `backend/src/jarvis/main.py` |
| Tests | `backend/tests/unit/security/test_desktop_auth.py` plus all backend unit suites |

## Implementation steps

1. Added strict HS256 desktop-session tokens with fixed issuer and audience.
2. Required expiry, issued-at, not-before, subject, token ID, device, session, epoch, contract bounds and token type claims.
3. Added immutable device, session, contract-range and authenticated-principal models.
4. Added asynchronous device/session registry and atomic nonce-store contracts.
5. Added development/test in-memory registry and nonce implementations.
6. Cross-checked signed actor/device/session/epoch against current registry records and revocation state.
7. Computed the intersection of server, token, device and session contract ranges.
8. Required a canonical per-request UUID nonce and rejected replay.
9. Bound the validated principal to `request.state.principal`.
10. Returned generic 401 for credential/registry mismatch, 426 for incompatible contract, and 503 when authentication is not configured.
11. Integrated an optional authenticator into the FastAPI application factory.

## Security properties

Loopback address is never considered identity. Token algorithm selection is not controlled by the token. Invalid signatures, expiry, missing claims, unsigned tokens, revoked records, epoch mismatch and binding mismatch all fail before nonce consumption and before principal creation.

No tokens, secrets, connection details or raw header values are written to logs or errors.
