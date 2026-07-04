# Versioning Log — 120011 Verify Outcome v1

| Field | Value |
|---|---|
| Date | 2026-07-04 |
| Global ID | `120011` |
| Version | `v1` |
| Lifecycle | `current` |

## Added contract

- `verifyOutcome(state, service=..., runtime_thread_id=...)`.
- Probe source/read-only literals: `independent_read` / `true`.
- Criterion verdicts: `passed`, `failed`, `uncertain`.
- Aggregate outcomes: `succeeded`, `partially_succeeded`, `failed`, `uncertain`.
- Opaque evidence prefix: `evd_`.
- Stable verification/observation prefixes: `vrf_` / `obs_` with 24-hex digests.
- Default per-probe timeout: `5` seconds.
- Default maximum concurrent probes: `4`.
- Maximum revision count: `2`.
- One immutable verification persistence record per plan/revision identity.

## Compatibility

The function consumes the existing `PlanDraft` v1 and `PriorActionResult` v1
contracts. It appends JSON-safe records to the existing `observations` reducer and
sets only existing canonical workflow statuses. No `JarvisState`, REST, WebSocket,
model-provider, action-result or graph-topology field changed.

The injected store may be implemented by the future data-layer adapter. Probe
implementations belong to their registered capability adapters; this function
defines and verifies the orchestration boundary without claiming any native probe is
currently installed.

## Status compatibility

The canonical terminal status set has no `uncertain` value. Non-recoverable
verification uncertainty therefore retains outcome `uncertain` in typed evidence and
maps safely to task `failed`. Recoverable uncertainty maps to `planning`, which the
existing graph routes to bounded revision.

## Rollback

Remove the verification module/export/tests and documentation additions, then restore
120011 to planned. Persisted v1 verification records and appended observations are
immutable evidence and must not be rewritten or interpreted as executor success.
