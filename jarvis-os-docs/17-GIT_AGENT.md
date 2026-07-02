# Git Agent

## Safe reads

Repository root, branch, status, diff summary, remotes with credentials redacted, ahead/behind, log, and conflict state.

## Mutations

Branch creation and local commits are medium-risk. Fetch is networked but non-mutating locally beyond refs. Pull/rebase/merge can alter working state and require a clean-state strategy. Push, tag publication, remote branch deletion, force operations, and credential changes require explicit approval; force push is denied by default.

## Invariants

- Never discard, stash, stage, or commit unrelated user changes silently.
- Pin repository by canonical path and remote by normalized URL.
- Show branch and commit range before remote mutation.
- Commit messages identify intent, not “AI generated” boilerplate.
- Verification re-reads HEAD/status and, for pushes, confirms remote ref.

Secrets detected in proposed commits stop the workflow.
