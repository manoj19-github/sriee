# Stage 00 — Repository and Contract Foundation

## Goal

Create a buildable, testable skeleton with no OS side effects. This stage prevents Python and C# from inventing different meanings for the same action.

## Functions introduced

Planning scaffolds for 110000–110002, 120000, 130000–130004, 150000, 160000–160002, 190000, 190006.

## Steps

1. Initialize Git; add secret-safe `.gitignore`, editor settings, contribution rules and CODEOWNERS.
2. Create the folder structure from `28-FOLDER_STRUCTURE.md`.
3. Pin Python and .NET SDK/tool versions; add reproducible dependency lock strategy.
4. Define JSON Schemas for ID types, `ActionRequest`, `ActionResult`, task events, approval and capability manifest.
5. Add canonical JSON/digest test vectors shared by Python and C#.
6. Generate or implement typed contract models on both sides.
7. Build an in-memory fake executor that returns scripted results and receipts.
8. Define configuration fields and secret handles; commit examples with fake values only.
9. Add formatting, linting, typing, unit, contract and secret-scan CI jobs.
10. Write ADR-001 for planning/execution separation and first threat model.
11. Append coding/test log entries and change relevant functions to `in-progress`, then `complete` only after gates.

## Required tests

- Both languages accept valid golden fixtures and reject invalid/unknown-major fixtures.
- Canonical serialization yields identical action digest.
- Unknown capability/version fails closed.
- Seeded passwords/tokens are caught by scanning and telemetry redaction tests.
- Fake executor handles success, failure, timeout, cancellation and duplicate action ID.

## Exit gate

Clean checkout builds offline from available caches/locked sources; required CI passes; contract fixtures and digest agree byte-for-byte; no production credentials exist in source; no real executor adapter is enabled.
