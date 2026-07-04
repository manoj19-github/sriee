# Versioning Log — 130001 Authenticate Session v1

| Field | Value |
|---|---|
| Date | 2026-07-05 |
| Global ID | `130001` |
| Version | `v1` |
| Lifecycle | `current` |

## Contract

- Challenges are device/actor/backend bound, carry 256-bit random nonces and live
  between 5 and 120 seconds; the default is 30 seconds.
- The `jarvis.session-proof.v1` transcript is canonical ASCII JSON and binds both
  nonces, registered identity, Windows session, backend and requested contracts.
- Proof signatures are 64-byte raw P-256 `r || s` values over SHA-256.
- Valid challenges are single use. Invalid signatures do not consume a challenge.
- Sessions live between 30 seconds and 10 minutes; the default is five minutes.
- Successful authentication atomically revokes the prior device session and increments
  its epoch. Issued tokens bind the actor, device, session, epoch, backend instance,
  Windows session and negotiated contract range.
- Outstanding in-memory challenges default to four per device and 1024 globally.
  Durable implementations must preserve equivalent atomicity and bounds.

## Compatibility and dependencies

The existing 110002 token format remains compatible for legacy session records.
Records created by 130001 require the new user-session and backend-instance claims.

Added exact pins: `cryptography==46.0.5`, `cffi==2.0.0`,
`pycparser==2.23`. No graph, task, event, database schema or API route changed.
