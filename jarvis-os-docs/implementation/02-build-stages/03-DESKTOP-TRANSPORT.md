# Stage 03 — WPF Desktop and Secure Transport

## Dependencies

Stages 00–02 complete; no production Windows adapter beyond safe observations/open test app.

## Functions

110008–110009, 130000–130007, 150000–150006, 160000–160006, 160012–160013.

## Steps

1. Create .NET solution/projects and enable nullable, analyzers and warnings-as-errors.
2. Build WPF MVVM shell with command bar, connection state and accessible task timeline.
3. Generate/load shared contract models and golden fixtures.
4. Create per-install device identity and authenticated session handshake.
5. Implement WebSocket negotiation, subscriptions, heartbeat, reconnect and REST event resync.
6. Build local signed policy baseline and capability manifest.
7. Implement action validation, resource canonicalization, lease, idempotency and durable receipt store.
8. Implement trusted approval dialog bound to digest/actor/device/expiry.
9. Add one harmless adapter: open/focus a registered test application.
10. Stream action request/result through the full backend/graph/desktop path.
11. Implement cancellation and independent process/window verification.
12. Add diagnostics with redaction and contract/version details.

## Required tests

Socket loss/replay, duplicate frames, stale contract, forged device, forged/expired/changed approval, app path substitution, duplicate idempotency key, desktop restart before/after receipt, user cancel, screen-reader/keyboard approval flow.

## Exit gate

One approved test-app action completes end to end with receipt and postcondition. Every approval and duplicate/restart attack fails locally. Desktop remains unelevated and backend cannot invoke arbitrary executable paths.
