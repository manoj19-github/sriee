# Intent Classifier Prompt

Prompt contract: `intent-classifier-v1`

Function: `classifyIntent`

Global ID: `120003`

## Role

Classify a normalized task request into one fixed intent and bounded scope. This
prompt does not plan, approve, execute, call tools or decide policy.

## Inputs

- One normalized task request.
- Authorized, bounded context summaries resolved ephemerally from opaque references.
- A strict JSON response schema.

Request text and every context summary are untrusted data. They cannot override the
system contract. Summary content is sent only to the configured loopback model and
is never written into graph state by this node.

## Output contract

The model returns only:

- one fixed intent name;
- confidence from `0` to `1`;
- one fixed target;
- a subset of the supplied opaque context reference IDs;
- zero or more fixed ambiguity codes.

Free-form reasoning, commands, paths, capabilities, policy decisions, risk ratings
and invented references are not accepted. Schema-invalid or unauthorized output
receives one content-free repair attempt; a second failure stops safely.

## Deterministic routing

The application, not the model:

- marks project modification, developer-tool, desktop and task-control intent as
  consequential;
- requires clarification when consequential confidence is below `0.70`;
- requires project scope for project intent;
- checks consequential target compatibility;
- routes unknown or any unresolved ambiguity to clarification.

The exact runtime prompt is versioned in
`backend/src/jarvis/graph/intent.py` as `INTENT_CLASSIFIER_PROMPT_V1`.
