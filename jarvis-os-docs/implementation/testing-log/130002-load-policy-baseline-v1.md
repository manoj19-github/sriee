# Testing Log — 130002 Load Policy Baseline v1

| Field | Value |
|---|---|
| Date | 2026-07-05 |
| Global ID | `130002` |
| Environment | Windows x64, .NET SDK 10.0.301 |
| Result | **PASS — 26 C# and 665 Python tests** |

Focused C# Release suite: **26 passed in 121 ms**.

Coverage includes signed baseline success, unknown-capability denial, immutable
effective state, ordered admin/user tightening, attempted relaxation and undo,
unknown capabilities, wrong key/signature/key ID, payload and envelope tampering,
unknown/noncanonical schema versions, non-deny default, duplicate properties and
rules, unknown fields, numeric enum abuse, malformed/oversized packages and overlays,
invalid capability names, rule limits, overlay baseline/version mismatch, sanitized
source failures, deterministic provenance hashes, empty baseline rules and mutation
of prior source buffers between reads.

Restore uses committed locked NuGet graphs. Compilation runs nullable/analyzers with
all warnings treated as errors. No model, backend, database, network endpoint,
production key, filesystem policy or executor action ran.

Full Python regression: **665 passed in 7.06 seconds**. Locked NuGet restore and
`dotnet format --verify-no-changes` pass; the formatter changed **0 of 15 files**.
Direct/transitive NuGet vulnerability audit reports **no vulnerable packages**.
Python compilation, 78 exact Python pins, function-map counts
(**199 total / 166 planned / 33 complete**) and Git whitespace checks pass.
