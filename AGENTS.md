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
8. Add a Git delivery record under `jarvis-os-docs/implementation/git-log/`.
9. After all required tests pass, stage only files belonging to the current task and create a clear Conventional Commit message: `<type>(<scope>): <outcome>`.
10. Push the commit to the configured upstream branch. If no upstream, credentials, or network is available, record the exact failure in the Git delivery log and report it; never claim a push succeeded when it did not.

Never expose credentials, tokens, connection strings, or raw secret values in source, documentation, tests, diagnostics, or logs.
Never commit `.env`, `.tmp/`, `tmp/`, virtual environments, caches, generated test artifacts, or unrelated user changes.
