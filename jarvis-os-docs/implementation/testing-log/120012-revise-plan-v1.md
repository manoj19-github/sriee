# Testing Log — 120012 Revise Plan v1

| Field | Value |
|---|---|
| Date | 2026-07-04 |
| Global ID | `120012` |
| Environment | Windows, repository Python environment, configured Qwen endpoint |
| Result | **PASS — 558 passed in 6.06 seconds** |

## Focused verification

`python -m pytest backend/tests/unit/graph/test_revision.py -q -p no:cacheprovider`

Result: **40 passed in 1.06 seconds**.

Coverage includes immutable executed actions/criteria, automatic corrective-action
merge, unsuccessful dependency blocking, one repair, revision exhaustion, corrected
scope identity/resources, fresh policy/approval reset, stable store replay, malformed
state/evidence/record rejection, sanitization, cancellation and settings/clock bounds.

## Live configured-model smoke

Using synthetic failure evidence and resources, the configured Qwen-compatible
gateway proposed one registered corrective action. Application code merged the
executed inspection action/criterion, persisted a two-action revision, incremented
revision to 1 and cleared policy/approval. No action was executed and no secret,
path, database, Redis or desktop content was printed.

## Regression

- Graph suite: **405 passed in 3.03 seconds**.
- Full backend suite: **558 passed in 6.20 seconds**.
- Compilation and `git diff --check`: **PASS**.

Final post-documentation evidence:

- Focused revision suite: **40 passed in 1.06 seconds**.
- Full backend suite: **558 passed in 6.06 seconds**.
- Compilation and diff whitespace checks: **PASS**.
- Function maps: **199 total / 172 planned / 0 in progress / 27 complete**.
