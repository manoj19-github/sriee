# Memory System

## Memory classes

- Working: current graph state; task lifetime.
- Episodic: summaries of completed tasks and outcomes.
- Semantic: user-approved facts, preferences, projects, and glossary.
- Procedural: versioned workflow recipes and project runbooks.
- Artifact: files, screenshots, transcripts, and reports with explicit retention.

Conversation history is not automatically long-term memory. The memory agent proposes candidates; deterministic filters and, for sensitive or consequential facts, user confirmation govern writes.

Wellness observations, medication schedules and mood journals are sensitive domain records, not ordinary semantic companion memory. They use separate purpose grants, retention, encryption and deletion controls and are unavailable to unrelated prompts, recommendations or lock-screen previews.

## Record

`memory_id`, `subject`, `predicate`, `value`, `source_ref`, `confidence`, `classification`, `created_at`, `last_used_at`, `expires_at`, `consent`, `embedding_version`, and `supersedes`.

## Retrieval

Filter first by actor, purpose, classification, scope, and expiry; then rank via lexical/vector similarity and recency. Return small cited snippets. Prompt instructions found inside memory are data, not authority.

## User controls

View, correct, pin, forget, export, set retention, disable a class, and see why a memory was used. Deletion removes primary records, vector entries, and queued replicas, with a tombstone for completion tracking.

## Guardrails

Never store passwords, API keys, session cookies, raw biometric templates, protected-trait guesses, or hidden prompt content. Do not infer stable preferences, health conditions or emotions from one action or sensor value. Names and paths remain scoped to their user/device. Encrypt sensitive fields and separate encryption keys from the database.
