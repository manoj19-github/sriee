# Versioning Log — 120004 Create Plan Draft v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120004` |
| Version | `v1` |
| Lifecycle | `current` |

## Added contract

- Capability IDs are lower-case dotted/dashed registered identifiers with exact
  semantic versions.
- Parameter kinds: `boolean`, `integer`, `number`, `enum`, `identifier`, `resource`.
- Maximum capabilities: `16`; parameters per capability: `12`.
- Maximum actions: `8`; criteria: `16`; total arguments: `64`.
- Maximum context summary: `2,000` characters; aggregate: `12,000`.
- Default context resolver deadline: `5` seconds.
- Dependencies may reference only earlier unique step IDs.
- Every action requires at least one declared verification criterion.
- Stable IDs use `act_`/`crt_` plus a 24-hex task/semantic digest.
- Exactly one content-free structured-output repair.
- Prompt contract: `plan-draft-v1`.

## Compatibility

This adds the concrete `120004` node and planning/capability protocols without
changing the existing seventeen-field graph schema. It writes the existing `plan`
field and consumes `120003` intent plus `120002` context references through an
injected resolver. It uses the existing `120014` loopback model gateway.

The future executor capability manifest (`160000`) may implement the injected
contract after transport negotiation. This planning contract does not claim that the
executor or any native capability is currently implemented.

No dependency, REST, WebSocket, database or graph-topology contract changed.

## Rollback

Remove the planner module/export, tests and prompt/architecture additions. No action
was dispatched and no checkpoint migration, database record or external resource
requires rollback.
