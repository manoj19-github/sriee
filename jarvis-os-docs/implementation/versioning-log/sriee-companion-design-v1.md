# Versioning Log — Sriee Companion Design v1

| Field | Value |
|---|---|
| Date | 2026-07-02 |
| Design version | `0.1.0-design` |
| Lifecycle | Proposed/current |
| Compatibility | Additive, disabled until implemented and explicitly enabled |

## Added allocations

- `180011–180016`: Sriee voice, camera session, presence, local face enrollment/matching and visible-expression observation.
- `210000–210011`: companion profile, greeting routine, briefing, affectionate dialogue, uncertain observations, preferences/routines, contextual care, machine capability routing, relationship safeguards and stop/revoke.

## Contract impact

- No REST, WebSocket, database or executable prompt contract changed.
- No package versions changed.
- Existing permission tiers and capability-specific approvals remain authoritative.
- Companion mode grants no sensor or machine capability automatically.

## Rollback

Revert the planning documentation change. No runtime migration or user-data transformation is required.
