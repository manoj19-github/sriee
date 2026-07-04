# Versioning Log — 120015 Propose Task Reflection v1

| Field | Value |
|---|---|
| Date | 2026-07-04 |
| Global ID | `120015` |
| Version | `v1` |
| Lifecycle | `current` |

## Contract

- Candidate IDs: `rfc_` plus 24 semantic digest hex characters.
- Correction IDs: `ucr_`.
- Candidate kinds: prompt review, test improvement, verification review.
- Fixed recommendation and correction codes.
- Current version kinds: prompt, test, tool, policy.
- Mandatory review; automatic application is structurally false.

Uses existing verified evidence/result contracts and an injected immutable store.
No graph state, topology, API, dependency or mutation contract changed.

Rollback removes the reflection module/exports/tests/docs; persisted candidates remain
review records and confer no authority.
