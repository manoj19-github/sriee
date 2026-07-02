# Coding Log — 120001 Normalize Request v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120001` |
| Status | Complete |

## Delivered behavior

1. Added `normalizeRequest` as a pure LangGraph-compatible node.
2. Reuses the existing frozen `CreateTaskRequest` contract for text/transcript,
   non-blank, NUL-free and 16,000-character validation.
3. Validates actor/device identifiers, the supported v1 contract major and
   created/planning entry status.
4. Preserves existing valid task and thread IDs without invoking the ID generator.
5. Assigns a missing task ID through an injected/default opaque generator and derives
   the missing thread ID from that task token.
6. Canonically serializes only for a byte-size check; returned user content remains
   exactly as supplied, including Unicode, whitespace and line endings.
7. Returns only contract version, task ID, thread ID, normalized request and planning
   status; it does not mutate the caller's state.
8. Added fixed content-free errors for settings, status, identity, contract, payload,
   size and ID-generation failures.

## Side-effect and privacy boundary

The node does not call a model, database, Redis, network, filesystem or OS adapter.
Validation failures never include rejected content, identifiers or validator text.

## Package impact

No package change. The implementation uses existing exact Pydantic and Packaging pins
plus Python standard-library modules.
