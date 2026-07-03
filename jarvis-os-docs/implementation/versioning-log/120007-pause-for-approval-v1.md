# Versioning Log — 120007 Pause For Approval v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120007` |
| Version | `v1` |
| Lifecycle | `current` |

## Added contract

- `pauseForApproval(state, service=...)` accepts an awaiting-approval graph state.
- `PendingApprovalStore` atomically creates approval+event or returns the exact row.
- `PendingApprovalRequest` is stable across interrupt replay.
- `ApprovalActionPreview` contains the exact bounded action contract.
- `ApprovalInterruptPayload` is the durable trusted-desktop prompt.
- `ApprovalResumeCandidate` allows only approval ID, digest and approve/deny.
- `sha256-v1` binds all security-relevant action and preliminary-policy fields.

## Compatibility

The function writes the existing `pending_approval` and `status` graph fields. It
uses LangGraph's existing checkpointer/thread configuration and does not alter REST,
WebSocket, provider, database schema or package versions.

120008 remains responsible for authenticating, matching, expiring and consuming the
resume candidate. 120009 remains the first node permitted to request side effects.

## Rollback

Remove the approval module exports and restore 120007 to planned. Never replace the
dynamic interrupt with an in-process wait or dispatch before approval validation.
