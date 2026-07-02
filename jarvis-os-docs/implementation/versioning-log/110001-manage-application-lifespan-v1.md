# Versioning Log — 110001 Manage Application Lifespan v1

| Field | Value |
|---|---|
| Record | VERSION-110001-v1 |
| Date | 2026-07-02 |
| Function version | v1 |
| Lifecycle | current |
| Compatibility | first implementation |

## Added

- `ApplicationRuntime` lifecycle state machine.
- `ManagedResource`, `DrainableResource`, `ResourceSpec` and `DependencyHealth` contracts.
- Immutable `RuntimeReadiness`.
- Sanitized startup and shutdown errors.
- Canonical FastAPI `manageApplicationLifespan`.
- `create_application` application factory.

## Package changes

Added exact pins to root `requirements.txt`:

- `httpx2==2.5.0`
- `httpcore2==2.5.0`
- `truststore==0.10.4`

Existing `fastapi==0.138.1`, `starlette==1.3.1`, `httpx==0.28.1`, Pydantic and pytest pins remain unchanged.

No API, event, database migration, policy or prompt version changed.
