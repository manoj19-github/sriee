# Function Map — Data, Memory, and RAG

Source: [database design](../../25-DATABASE_DESIGN.md), [memory system](../../09-MEMORY_SYSTEM.md), and [RAG architecture](../../10-RAG_ARCHITECTURE.md).

Technology: PostgreSQL schema `jarvis`, migration tool, encrypted artifact storage, optional vector extension/index.

| Global ID | Canonical name | Function | Description | Reads | Writes | Status | Notes |
|---|---|---|---|---|---|---|---|
| 140000 | `postgres-data-own-schema-mandatory-p0-complete-current-v1` | `ownJarvisSchema` | Provides isolated PostgreSQL namespace for JARVIS objects owned by the configured database role. | PostgreSQL catalog | db: schema `jarvis` | complete/current/v1 | Infrastructure-only completion; no application tables exist yet. |
| 140001 | `python-data-run-migrations-mandatory-p0-planned-current-v1` | `runMigrations` | Applies ordered checksummed migrations with schema-qualified objects and records version. | migration files; migration table | db: tables/indexes/version | planned/current/v1 | Rehearse backup and compatibility; never auto-run destructive change. |
| 140002 | `python-data-store-task-mandatory-p0-planned-current-v1` | `storeTaskAggregate` | Transactionally creates/updates task projection with optimistic concurrency. | domain task transition | db: tasks | planned/current/v1 | Events remain authoritative history. |
| 140003 | `python-data-append-task-event-mandatory-p0-planned-current-v1` | `appendTaskEvent` | Appends immutable per-task sequenced event and outbox record in one transaction. | domain event; expected sequence | db: task_events, outbox | planned/current/v1 | Unique event ID and task sequence prevent duplicates. |
| 140004 | `python-data-persist-graph-checkpoint-mandatory-p0-planned-current-v1` | `persistGraphCheckpoint` | Stores versioned LangGraph thread checkpoints and writes for durable resume/recovery. | graph state delta; thread/checkpoint IDs | db: checkpoint tables | planned/current/v1 | JSON-safe state; secrets/artifacts excluded. |
| 140005 | `python-data-store-action-receipt-mandatory-p0-planned-current-v1` | `storeActionReceipt` | Persists action attempts, idempotency keys and executor receipts for reconciliation. | action dispatch/result | db: actions, attempts, receipts | planned/current/v1 | Effective-once side effects depend on this plus desktop receipt store. |
| 140006 | `python-memory-propose-candidate-mandatory-p1-planned-current-v1` | `proposeMemoryCandidate` | Produces classified memory candidate with source, confidence, expiry and consent requirement. | completed task evidence; memory prompt | graph/db: candidate only | planned/current/v1 | Does not persist stable memory by itself. |
| 140007 | `python-memory-save-approved-mandatory-p1-planned-current-v1` | `saveApprovedMemory` | Validates candidate, consent and prohibited-data rules before versioned memory write. | candidate; policy; user confirmation | db: memory record/index | planned/current/v1 | Secrets/biometric/protected-trait inference denied. |
| 140008 | `python-memory-retrieve-scoped-mandatory-p1-planned-current-v1` | `retrieveScopedMemory` | Filters by actor, purpose, scope, classification and expiry before ranking relevant records. | query; memory DB/index; ACL | graph: cited memory references | planned/current/v1 | Filter before vector similarity. |
| 140009 | `python-memory-forget-record-mandatory-p1-planned-current-v1` | `forgetMemory` | Removes primary memory, index entries and replicas; tracks completion with non-content tombstone. | authenticated deletion request | db/index: deletion/tombstone | planned/current/v1 | User-visible deletion status. |
| 140010 | `python-rag-index-source-optional-p1-planned-current-v1` | `indexKnowledgeSource` | Validates source permission/type, extracts, chunks, classifies, embeds and indexes by checksum. | registered source/artifact | db/vector/artifact: chunks/index metadata | planned/current/v1 | Active content stripped; source instructions untrusted. |
| 140011 | `python-rag-retrieve-context-optional-p1-planned-current-v1` | `retrieveKnowledgeContext` | ACL-filters, searches, reranks and returns bounded source-cited context. | query; source ACL; indexes | graph: context references | planned/current/v1 | Citation and injection evaluations required. |
| 140012 | `python-data-enforce-retention-mandatory-p1-planned-current-v1` | `enforceRetention` | Expires events/artifacts/memories by class while preserving required audit metadata. | retention policy; record metadata | db/artifacts/index: deletion records | planned/current/v1 | Legal/security policy and user deletion have explicit precedence. |

## Change rule

Update this map before any schema, migration, retention, checkpoint serialization, memory, embedding, ACL, or deletion behavior change.
