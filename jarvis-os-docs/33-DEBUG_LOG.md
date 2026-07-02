# Debug Log

Use this for a concrete defect investigation. Keep secrets and personal artifacts out; reference a protected diagnostic bundle.

## Template

### BUG-YYYYMMDD-NNN — Symptom

- First seen/build/environment:
- User impact and severity:
- Expected/actual:
- Reproduction:
- Correlation/task/action IDs:
- Timeline:
- Evidence:
- Hypotheses tested:
- Root cause:
- Fix:
- Regression tests:
- Rollback/mitigation:
- Owner/status:

## Debugging order

Preserve evidence → identify task timeline → validate contract versions → inspect policy decision and action digest → inspect checkpoint/interrupt → inspect dispatch and executor receipt → reconcile OS postcondition → inspect model trace last. Do not begin by guessing from the final natural-language response.

Production debugging MUST NOT replay side effects. Fork checkpoint state into a fake executor or use read-only reconciliation.
