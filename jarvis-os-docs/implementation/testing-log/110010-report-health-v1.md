# Testing Log — 110010 Report Health v1

| Field | Value |
|---|---|
| Date | 2026-07-02 |
| Global ID | `110010` |
| Environment | Windows, Python 3.14.4, exact pinned temporary dependencies |
| Result | **PASS — 105 passed in 2.62 seconds** |

## Focused verification

Health and lifecycle suite: **13 passed in 0.48 seconds**.

Coverage includes:

1. Liveness and readiness use separate response contracts.
2. Healthy readiness reports all six dependencies in stable order.
3. Provider outage returns 503, marks runtime acceptance false and leaves liveness at 200.
4. A later healthy probe restores readiness and runtime acceptance.
5. Dependency exception text and configured secrets never reach responses.
6. Health-check timeout fails closed with a safe code.
7. Missing runtime is live but not ready.
8. Content-free metric counters track probes and failures.
9. Existing startup, rollback, drain and shutdown behavior remains green.
10. Full settings, security, task, control and WebSocket regressions remain green.

## Warning

The suite reports one existing `StarletteDeprecationWarning`: FastAPI's current `TestClient` imports the deprecated httpx compatibility path and recommends `httpx2`. This does not affect test results or the health contract; both packages are already exactly pinned for controlled migration.

## Intermediate correction

An added assertion intended to prove liveness performs no dependency probes initially ran after the test had already requested readiness, producing one expected-count failure. The readiness request was moved after the liveness-only assertion; no production code changed for this correction.
