# Versioning Log — 120003 Classify Intent v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120003` |
| Version | `v1` |
| Lifecycle | `current` |

## Added contract

- Intent names: `continue_project`, `modify_project`, `run_developer_tool`,
  `desktop_control`, `task_control`, `information_request`, `conversation`, `unknown`.
- Scope targets: `project`, `desktop`, `task`, `general`, `none`.
- Fixed ambiguity codes: `missing_project`, `ambiguous_target`, `unclear_action`,
  `conflicting_context`, `low_confidence`, `unsupported_request`.
- Default consequential confidence threshold: `0.70`.
- Maximum authorized references: `16`.
- Maximum summary length: `2,000` characters; aggregate: `12,000` characters.
- Default resolver deadline: `5` seconds.
- Exactly one content-free structured-output repair.
- Prompt contract: `intent-classifier-v1`.

## Compatibility

This adds the concrete `120003` node and injected resolver/model protocols without
changing the existing seventeen-field graph schema. The node writes the existing
`intent` field. It consumes `120002` opaque references and the existing `120014`
loopback model gateway contract.

No dependency, REST, WebSocket, database or graph-topology contract changed.

## Rollback

Remove the classifier module/export, prompt document and tests. No checkpoint,
database record, external action, migration or model installation requires rollback.
