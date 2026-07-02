# Versioning Log — 120000 Build Graph v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120000` |
| Version | `v1` |
| Lifecycle | `current` |

## Added contract

- Graph contract version: `1.0`.
- State schema version: `1.0`.
- Compiled graph name: `jarvis-core-v1`.
- Exact thirteen-node registry for functions `120001` through `120013`.
- Canonical seventeen-field state with append reducers on action results,
  observations and errors.
- Deterministic status routes for policy, approval and verification.
- Explicit durable checkpointer binding with matching graph/state versions.
- Sanitized startup failure codes for settings, state, reducer, node, checkpointer,
  route and compile incompatibility.

## Compatibility

This adds the first LangGraph construction contract. Existing REST, WebSocket, task,
health, database, prompt and policy contracts are unchanged.

No dependency changed; existing exact LangGraph pins are used.

## Rollback

Remove the `jarvis.graph` package and graph tests. No database record, checkpoint,
external side effect or migration requires rollback.
