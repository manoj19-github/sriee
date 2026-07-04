# Versioning Log — 120016 Coordinate Specialists v1

| Field | Value |
|---|---|
| Date | 2026-07-04 |
| Global ID | `120016` |
| Version | `v1` |
| Lifecycle | `current` |

## Contract

- Workflow IDs use `wfl_`; stable execution IDs use `swf_`; provenance uses `spv_`.
- Roles are planner, research, coder, reviewer, security and verifier.
- Each step binds an exact specialist version and fixed output contract.
- Workflows contain at most eight steps, depth is at most two and every deadline is
  between 0.1 and 60 seconds.
- Handoffs contain typed metadata and opaque references only.
- Specialist descriptors are structurally read-only and cannot delegate.
- Aggregate output explicitly declares consensus non-evidentiary and proposed side
  effects subject to the standard action pipeline.

No graph topology, state schema, API or dependency version changed. Rollback removes
the coordinator module, exports, tests and documentation; existing observations remain
non-authoritative provenance and confer no action authority.
