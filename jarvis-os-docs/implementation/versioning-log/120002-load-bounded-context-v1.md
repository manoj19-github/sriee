# Versioning Log — 120002 Load Bounded Context v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120002` |
| Version | `v1` |
| Lifecycle | `current` |

## Added contract

- Context kinds: `project`, `capability`, `policy`, `memory`.
- Opaque ID prefixes: `prj_`, `cap_`, `pol_`, `mem_`.
- Classifications: `internal`, `personal`, `sensitive`.
- Required semantic version and actor ownership on every reference.
- Required device ownership for policy and capability references.
- Default limits: project 4, capability 1, policy 1, memory 8, total 16.
- Default per-source deadline: 2 seconds.
- Fixed source ordering in graph state.
- Safe retryable optional-source errors and fail-closed required-source errors.

## Compatibility

This adds the concrete `120002` node and reference/source protocols without changing
the existing seventeen-field graph schema. The node writes existing `context_refs`
and append-reduced `errors` fields. Graph topology, REST, WebSocket, provider, database,
policy and prompt contracts remain compatible.

No dependency changed.

## Rollback

Remove the context module/export and tests. No source data, database record, checkpoint,
external resource or migration requires rollback.
