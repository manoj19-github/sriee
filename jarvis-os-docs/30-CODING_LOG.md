# Coding Log

Append one entry per meaningful work unit. Link commits/PRs when a repository exists; never rewrite prior entries except to correct a factual error with a note.

## Template

### DEV-YYYYMMDD-NNN — Short outcome

- Date/author:
- Requirement/issue:
- Scope:
- Files/components:
- Decisions and rationale:
- Contract/data changes:
- Security/privacy impact:
- Commands run:
- Tests and results:
- Known limitations:
- Rollback:
- Follow-ups:
- Commit/PR:

## DEV-20260702-001 — Documentation baseline

- Date/author: 2026-07-02 / Codex
- Requirement: create the JARVIS OS master, infrastructure, service, function, logging, testing, and versioning documents.
- Scope: documentation only; existing notebook, environment, and requirements untouched.
- Decisions: Python plans; C# independently validates and executes. WPF is the initial Windows shell. PostgreSQL is authoritative; Redis is optional. High-risk approval is action-bound and durable.
- Security impact: established deny-by-default capability model and hard exclusions.
- Verification: Markdown inventory, link/reference scan, placeholder scan, encoding scan.
- Known limitations: no application code or executable schemas exist yet.
- Follow-up: ADR-001 and the MVP contracts/vertical slice.
