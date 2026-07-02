# Testing Log — 110002 Authenticate Desktop Session v1

| Field | Value |
|---|---|
| Record | TEST-20260702-110002 |
| Date | 2026-07-02 |
| Global ID | 110002 |
| Environment | Windows, Python 3.14.4, exact temporary dependency set |
| Suite | complete `backend/tests/unit` suite |
| Final result | **PASS — 33 passed in 0.60 seconds, 0 warnings** |

## Authentication coverage

1. Valid session binds actor, device, session and selected contract to request state.
2. Authenticated principal is immutable.
3. Loopback request without credentials returns 401.
4. Tampered and expired tokens return 401.
5. Unsigned `alg=none` token returns 401.
6. Token missing a required claim returns 401.
7. Revoked device or session returns 401.
8. Actor, device and session-epoch mismatches return 401.
9. Expired registry session returns 401.
10. Header device must match the signed device.
11. Unsupported contract returns 426.
12. Contract rejection does not consume the request nonce.
13. Replayed request nonce returns 401.
14. Missing authenticator returns 503.
15. Existing settings and lifecycle suites remain green.

Decision: function 110002 may be marked `complete/current/v1`.
