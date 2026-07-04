# Testing Log — 130001 Authenticate Session v1

| Field | Value |
|---|---|
| Date | 2026-07-05 |
| Global ID | `130001` |
| Environment | Windows, repository Python environment |
| Result | **PASS — 665 passed in 5.68 seconds** |

Focused `test_session_auth.py`: **24 passed in 0.35 seconds**.

Coverage includes successful proof/token binding, compatibility with authenticated
requests, missing-bound-claim rejection, epoch rotation and prior-session revocation,
single and eight-way concurrent replay, invalid-proof recovery, challenge expiry and
bounds, malformed/noncanonical inputs, wrong keys, swapped public identities, revoked
and unknown devices, contract intersection/no-overlap, cross-backend proof rejection,
sanitized storage failures, rotation conflicts and lifetime bounds.

The suite uses a real current-user Windows CNG key to sign a transcript and the
backend verifier to authenticate it without exporting private material.

Full backend: **665 passed in 5.68 seconds**. Python compilation, 78 exact dependency
pins, function-map counts (**199 total / 167 planned / 32 complete**) and Git
whitespace checks pass. No database, network endpoint or production session
authority ran.
