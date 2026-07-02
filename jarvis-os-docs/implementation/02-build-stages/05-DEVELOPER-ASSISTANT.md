# Stage 05 — Developer Assistant

## Dependencies

Stage 04 proven in Windows VM; scoped workspace and action receipt guarantees are stable.

## Functions

160009, 170007–170008 and richer use of 170012, plus coding/reviewer/debugger prompts.

## Steps

1. Add bounded repository reader and instruction precedence model.
2. Define patch proposal contract with preimage hashes, scope and rollback metadata.
3. Implement patch preview, approval where policy requires, atomic application and diff verification.
4. Register project-specific format, lint, type and test ProcessSpecs.
5. Add coding workflow: inspect → propose → patch → validate → review → summarize.
6. Add secret scan and unrelated-change preservation tests.
7. Implement exact staging/local commit preview and receipt.
8. Implement remote push only behind R3 action-specific approval and remote-ref verification.
9. Add debugger timeline using events/checkpoints/receipts without replaying side effects.
10. Build evaluation set from small representative repositories and fault cases.

## Required tests

Path/junction escape, changed preimage, malformed patch, existing uncommitted work, test timeout, huge output, malicious repository instructions, secret in diff, commit contains unrelated file, wrong remote/branch, rejected push, cancellation and rollback.

## Exit gate

Golden coding tasks produce minimal reviewed diffs, preserve unrelated changes, run declared validation with honest results, and cannot commit/push/install/migrate outside explicit independently approved actions.
