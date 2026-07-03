# Versioning Log — 120008 Resume Approval v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120008` |
| Version | `v1` |
| Lifecycle | `current` |

## Added contract

- `resumeApproval(state, service=..., runtime_thread_id=...)` accepts only an
  awaiting-approval checkpoint created by `pauseForApproval`.
- `ApprovalCheckpoint` strictly models the persisted request/event/times and resume
  candidate with cross-field binding validation.
- `ApprovalResolutionRequest` carries the complete approval, workflow identity,
  pending-event, time, digest and decision scope to atomic storage.
- `ApprovalResolutionStore` authenticates and claims one decision once.
- `ApprovalResolutionRecord` permits only time-consistent approved, denied or
  expired outcomes.
- `ApprovalResult` is the bounded `approval.result` v1 graph projection.

## Compatibility

The function reuses the existing `pending_approval` and `status` graph fields, so the
v1 `JarvisState` schema and graph topology do not change. Before resolution, the
field has the 120007 pending shape; afterward it has the versioned result shape.
Existing exact package pins remain unchanged.

The concrete database adapter must bridge the authenticated decision/outbox
transaction from 110007 to this one-time graph claim. Final desktop policy and
approval validation remain required immediately before execution under 130003–130006.

## Rollback

Remove the resume module exports and restore 120008 to planned. Do not bypass the
runtime-thread check, accept a non-atomic resolver, or route directly from the
interrupt resume candidate to dispatch.
