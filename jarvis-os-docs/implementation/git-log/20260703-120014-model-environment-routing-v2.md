# Git Delivery Log — 120014 Model Environment Routing v2

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120014` |
| Branch | `master` |
| Upstream | `origin/master` |
| Implementation commit | `0c869afe876c10cfffea9c2cc42713b18876c306` |
| Commit message | `feat(provider): route development qwen safely` |
| Push result | **SUCCESS** |
| Remote update | `cc8ccac..0c869af master -> master` |

## Delivered scope

- Explicit development/test and production model-routing policy.
- Exact allowlist for `qwen.msqube.in/api/chat` on default HTTP/HTTPS ports.
- Development model configuration for `qwen3.6:27b`.
- Production-only loopback Ollama enforcement for local Qwen or Gemma.
- Minimal remote payload and bounded local Ollama options.
- Optional secret Bearer authentication with redacted diagnostics.
- Non-prompt remote readiness and existing local model/version health.
- Safe example environment, architecture/provider documentation and 120014 v2 map.
- Required coding, testing and versioning logs.

## Verification

- Focused provider suite: **31 passed in 0.42 seconds**.
- Complete backend unit suite: **360 passed in 4.69 seconds**.
- Function maps: **174 rows / 154 planned / 20 complete**.
- Duplicate Global IDs: **0**.
- Root requirements: **75 exact pins**; no package change.
- `git diff --check`: **PASS** with expected Windows line-ending notices only.

## Live endpoint result

The supplied non-sensitive `"hii"` request reached the endpoint, which returned
`unauthorized` without a credential. The implementation supports
`OLLAMA_API_KEY`, but no token was guessed, requested from another system, written to
source or committed. A successful live model completion requires a provider-issued
Bearer token in the ignored local `.env` or secret manager.

## Worktree isolation

The implementation commit contains only the twelve provider-v2 files. The real
`.env`, temporary dependencies, virtual environments, caches and unrelated files
were not committed.
