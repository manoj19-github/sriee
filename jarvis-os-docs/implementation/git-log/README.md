# Git Delivery Logs

Create one delivery record after a tested implementation commit so the record can contain the real commit SHA and push result.

## Required fields

- Date and Global ID/task.
- Branch and upstream.
- Implementation commit SHA and exact message.
- Files/scope summary.
- Test command and result.
- Push command, result, and remote commit confirmation.
- Follow-up Git-log commit when the record itself is added.

## Rules

Only stage files belonging to the current task. Never commit secrets, `.env`, temporary dependencies, caches, virtual environments, or unrelated user work. Use Conventional Commits. A failed push is recorded honestly and retried only when credentials/network are available.
