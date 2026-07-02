# JARVIS OS Repository Rules

## Golden rule

For every implemented function:

1. Update the matching Global ID in the function map before or with the code change.
2. Maintain exact package versions in `requirements.txt` for every Python package used.
3. Add a coding record under `jarvis-os-docs/implementation/coding-log/`.
4. Add a testing record under `jarvis-os-docs/implementation/testing-log/`.
5. Add a version record under `jarvis-os-docs/implementation/versioning-log/`.
6. Change the function status to `complete` only after required tests pass and the testing record contains evidence.
7. Update `jarvis-os-docs/implementation/STATUS-DASHBOARD.md` in the same change.

Never expose credentials, tokens, connection strings, or raw secret values in source, documentation, tests, diagnostics, or logs.
