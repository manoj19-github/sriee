# Coding Log — 110011 Map Domain Errors v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `110011` |
| Status | Complete |

## Delivered behavior

1. Added `mapDomainErrors` as the single allowlisted mapping for typed task,
   approval, validation, HTTP and WebSocket failures.
2. Added immutable API envelope models containing code, static message, safe
   correlation ID, retryability and bounded details.
3. Installed production FastAPI handlers for HTTP, request-validation, typed domain
   and unexpected exceptions.
4. Added a safe response `X-Correlation-Id` and preserved only the fixed Bearer
   authentication challenge where required.
5. Reduced validation evidence to at most 20 issue locations/types without rejected
   input, validator messages or context.
6. Mapped unexpected exceptions to non-retryable `internal_error` without exposing
   exception text or stack traces.
7. Upgraded WebSocket protocol errors to the same public fields and allowlisted
   unknown codes to `unknown_frame`.
8. Updated API and WebSocket contract documentation and the implementation dashboard.
9. Hardened the production boundary to catch Starlette routing exceptions in addition
   to endpoint-raised FastAPI exceptions.
10. Preserved valid 4xx/5xx statuses for generic HTTP exceptions while continuing to
    replace arbitrary detail text with a fixed safe message.

## Intermediate correction

The first focused run exposed that FastAPI's `RequestValidationError.errors()` wrapper
does not accept Pydantic filtering keyword arguments. The mapper now reads the issues
once and builds a new safe projection containing only location and type. A correlation
test fixture was also corrected because its original value was syntactically valid
under the documented identifier contract.

Integration against the advanced remote branch exposed two boundary cases: router
404 exceptions used Starlette's base exception type, and fallback HTTP codes could
collapse an otherwise valid status to 400. The final mapper handles the framework
base type and preserves the source status unless an explicit allowlisted domain code
selects the public contract.

## Security and privacy

No raw exception, traceback, rejected request value, validation message/context,
arbitrary HTTP detail, frame content, credential or secret is copied to the public
contract. Incoming correlation IDs are reused only when they satisfy the bounded safe
identifier grammar; otherwise an opaque ID is generated.

## Package impact

No package change. All imports use Python standard-library modules and FastAPI/Pydantic
packages already exactly pinned in root `requirements.txt`.
