# Step-by-Step Testing Log

Each completion claim needs a test receipt linked to Global IDs. Record failures honestly; a rerun gets a new entry.

## Entry template

### TEST-YYYYMMDD-NNN — Run

| Field | Value |
|---|---|
| Date/runner | |
| Build/commit | |
| Stage/environment | |
| Global IDs | |
| Test level | unit / contract / graph / integration / VM / E2E / security / evaluation |
| Command/suite | |
| Seed/dataset | |
| Passed/failed/skipped | |
| Artifacts | |
| Decision | pass / fail / conditional |
| Follow-up owner | |

Failure details and reproduction:

1. 

## Required completion evidence

- P0: unit + contract + relevant integration/VM/security cases.
- P1: unit + integration and failure cases before release.
- AI behavior: golden evaluation plus injection/faithfulness cases.
- Side effect: idempotency, cancellation, timeout, restart and independent postcondition.
- Schema/migration: empty install, upgrade, rollback/restore rehearsal and unrelated-schema check.

## TEST-20260702-001 — Documentation structure

| Field | Value |
|---|---|
| Date/runner | 2026-07-02 / Codex |
| Build/commit | local documentation workspace |
| Stage/environment | documentation / Windows |
| Global IDs | registry and all function maps |
| Test level | static documentation verification |
| Command/suite | recursive PowerShell inventory, link, ID, status, placeholder and encoding scans |
| Passed/failed/skipped | PASS: 83 Markdown files; 125 function rows; 124 planned; 1 complete; 0 duplicate IDs; 0 invalid canonical names; 0 empty files; 0 broken links; 0 encoding/placeholder findings; 0 missing headings |
| Artifacts | console verification output |
| Decision | pass |
| Follow-up owner | none |
