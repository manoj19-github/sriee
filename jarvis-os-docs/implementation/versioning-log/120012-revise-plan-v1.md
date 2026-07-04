# Versioning Log — 120012 Revise Plan v1

| Field | Value |
|---|---|
| Date | 2026-07-04 |
| Global ID | `120012` |
| Version | `v1` |
| Lifecycle | `current` |

## Added contract

- `revisePlan(..., runtime_thread_id, scope_correction=None)`.
- Revision IDs: `prv_` plus 24 semantic digest hex characters.
- Corrected-scope IDs: `scp_`; fixed reasons `target_corrected`,
  `resource_corrected`, `constraint_added`.
- Revision range: prior `0..1`, new `1..2`.
- One structured model repair and one immutable load-or-record revision.
- Prompt contract: `plan-revision-v1`.

## Compatibility

The node reuses `PlanDraft`, planning bundle, verification evidence, result and
provider contracts. Existing graph fields are replaced/reset only as designed;
append reducers are not cleared. The next existing node revalidates the revision,
then policy evaluates it from an empty decision set.

No dependency, API, WebSocket, database schema or graph topology changed.

## Rollback

Remove revision code/exports/tests/docs and restore 120012 to planned. Persisted
revision records and prior append-only evidence remain immutable audit history.
