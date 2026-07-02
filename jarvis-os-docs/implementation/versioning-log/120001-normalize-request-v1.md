# Versioning Log — 120001 Normalize Request v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120001` |
| Version | `v1` |
| Lifecycle | `current` |

## Added contract

- Accepts a graph-state mapping with v1 contract, actor/device IDs, task request,
  created/planning status and optional task/thread IDs.
- Accepts the existing text/transcript input contract up to 16,000 characters.
- Defaults serialized request size to 65,536 bytes.
- Preserves valid `tsk_` and `thr_` identifiers.
- Generates an opaque `tsk_` identifier when absent and derives the matching `thr_`
  identifier from its token.
- Returns a five-field normalized state delta with `status=planning`.
- Uses fixed safe failure codes without rejected-value reflection.

## Compatibility

This adds the first concrete node for the existing `120000` topology. Graph structure,
state fields/reducers, REST, WebSocket, task, database, policy and prompt contracts are
unchanged.

No dependency changed.

## Rollback

Remove the normalization module/export and tests. No checkpoint, database record,
external resource or migration requires rollback.
