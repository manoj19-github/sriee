# Versioning Log — 130002 Load Policy Baseline v1

| Field | Value |
|---|---|
| Date | 2026-07-05 |
| Global ID | `130002` |
| Version | `v1` |
| Lifecycle | `current` |

## Contract

- Envelope version: `1`.
- Signature transcript:
  `JARVIS-POLICY-BASELINE-V1\0<envelope-version>\0<key-id>\0<payload>`.
- Signature: ECDSA P-256, SHA-256, RFC 3279 DER sequence; signer key ID and Subject
  Public Key Info are pinned by trusted desktop composition.
- Baseline schema: `1`; supported policy versions: canonical `1.x.y`.
- Default decision: exactly `deny`.
- Decisions order from least to most authority: `deny`, `ask`, `allow`.
- Baseline and overlay documents are bounded to 65,536 and 16,384 bytes; rules are
  bounded to 256.
- Admin overlay applies before user overlay. Both target the exact baseline version,
  may reference known capabilities only and may only retain or reduce authority.
- Effective state is immutable; missing/unknown capabilities return `deny`.

## Toolchain and dependencies

- SDK: exact `10.0.301`, roll-forward disabled; target framework `net10.0`.
- Test package: exact `MSTest` `4.0.2`.
- NuGet transitive versions and content hashes are committed in lock files.
- Runtime `Jarvis.Security` has no external NuGet dependency.

No Python contract, database schema, graph topology, API route or requirement pin
changed. A future schema requires a new signed envelope/payload version and explicit
compatibility review.
