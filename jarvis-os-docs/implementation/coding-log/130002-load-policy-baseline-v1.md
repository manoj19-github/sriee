# Coding Log — 130002 Load Policy Baseline v1

| Field | Value |
|---|---|
| Date | 2026-07-05 |
| Global ID | `130002` |
| Status | Complete |

## Delivered

- Bootstrapped the documented `desktop/` C# structure with a `Jarvis.Security`
  library and mirrored MSTest project.
- Pinned the active .NET 10 LTS SDK to `10.0.301` with roll-forward disabled,
  nullable reference types, .NET analyzers, deterministic builds and warnings as
  errors.
- Added a trusted-source-only loader; no model/backend policy argument exists.
- Verified a domain-separated v1 package using a pinned key ID and P-256/SHA-256
  signature before deserializing the policy payload.
- Enforced strict case-sensitive JSON, duplicate/unmapped-member rejection,
  canonical base64, bounded documents/rules, canonical `1.x.y` versions, valid
  capability IDs and mandatory deny-by-default semantics.
- Applied admin then user overlays only when bound to the exact baseline and every
  known rule is equal or stricter than the current decision.
- Snapshotted each source immediately, preventing a later source read from mutating
  previously supplied bytes.
- Returned an immutable effective policy containing decisions, versions, signer ID
  and SHA-256 provenance only; unknown capabilities always deny.

No Python package changed; `requirements.txt` retains 78 exact pins. The test project
declares exact `MSTest` `4.0.2`, and committed lock files capture every transitive
NuGet version and content hash.

## Evidence

- Focused C# Release suite: **26 passed in 121 ms**.
- Full Python regression: **665 passed in 7.06 seconds**.
- Locked restore and `dotnet format --verify-no-changes`: **PASS**.
- Direct/transitive NuGet vulnerability audit: **no vulnerable packages**.
- Function maps: **199 total / 166 planned / 33 complete**.
- Analyzers and compiler warnings are errors.
- Full C# and Python regression evidence is recorded in the testing log.
