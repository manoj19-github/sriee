# Versioning Log — 110002 Authenticate Desktop Session v1

| Field | Value |
|---|---|
| Record | VERSION-110002-v1 |
| Date | 2026-07-02 |
| Function version | v1 |
| Lifecycle | current |
| Compatibility | first implementation |

## Added

- Desktop session JWT codec and strict claim validation.
- Device/session registry contracts.
- Atomic request-nonce replay contract.
- Semantic contract-range negotiation.
- Immutable request principal.
- FastAPI authentication dependency and application-factory integration.

## Package changes

Added exact root requirement:

- `PyJWT==2.13.0`

Existing FastAPI, Pydantic, packaging, httpx2 and pytest pins remain unchanged.

## Request contract

Protected desktop requests require:

- `Authorization: Bearer <desktop-session-token>`
- `X-Device-Id`
- `X-Contract-Version`
- `X-Request-Nonce` as a canonical UUID

No database migration, event, prompt or policy version changed.
