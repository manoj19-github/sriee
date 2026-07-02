# Git Workflow

Use trunk-based development with short-lived branches:

- `main` is protected and releasable.
- Branches: `feat/`, `fix/`, `docs/`, `chore/`, `security/`.
- Changes enter through reviewed pull requests with passing required checks.
- Squash merge by default; preserve commits when they carry meaningful migration steps.
- Signed release tags: `vX.Y.Z`.

Commits are small, imperative, and reference the requirement/issue. Generated contracts and migrations are committed with their source change. CODEOWNERS require security review for policy, executor, native/elevation, update, auth, secrets, and plugin code.

Never commit `.env`, credentials, personal runtime data, model caches, screenshots, diagnostic bundles, or build output. Secret scanning runs locally and in CI. Emergency fixes still receive retrospective review and tests.
