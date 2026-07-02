# RAG Architecture

RAG supports project docs, runbooks, and user-selected knowledge. It does not grant tool authority.

## Pipeline

Source registration → permission check → extraction → malware/content-type checks → normalization → semantic chunking → metadata/classification → embedding → index → retrieval → rerank → cited context.

Every chunk retains source ID, canonical location, checksum, owner, ACL, classification, parser version, embedding version, and timestamps. Changed documents are re-indexed by checksum; deleted sources produce tombstones.

## Retrieval contract

Queries carry actor, purpose, scope, allowed classifications, top-k, and token budget. ACL filtering happens before similarity search. Results include exact source references and relevance signals. The responder distinguishes retrieved statements from verified system observations.

## Prompt-injection defense

Retrieved content is untrusted. Strip active content, delimit it, label provenance, ignore embedded instructions, and never expose secrets or tool schemas unnecessarily. Requests to alter policy, reveal prompts, or execute commands from a document are rejected.

## Quality

Evaluate retrieval recall, citation precision, answer faithfulness, stale-document rate, ACL leakage, and injection resistance. Maintain a small golden set per knowledge domain. Re-indexing must be reversible until quality gates pass.
