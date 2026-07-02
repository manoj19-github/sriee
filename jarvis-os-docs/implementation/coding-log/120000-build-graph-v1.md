# Coding Log — 120000 Build Graph v1

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120000` |
| Status | Complete |

## Delivered behavior

1. Added the canonical seventeen-field `JarvisState` with explicit append reducers
   for action results, observations and errors.
2. Added versioned node, build-setting and durable-checkpointer specifications.
3. Requires exactly the thirteen nodes owned by Global IDs `120001` through `120013`;
   missing, extra, non-callable or version-mismatched entries fail before compilation.
4. Validates exact state fields/types, required keys and reducer compatibility.
5. Added deterministic policy, approval and verification routers driven only by
   explicit workflow status; unknown states fail closed.
6. Compiles the fixed allow, ask, deny and bounded-revision topology with the injected
   checkpointer and stable graph name.
7. Converts construction failures to sanitized `GraphContractError` codes without
   exposing node objects, settings, saver details or exception text.
8. Exposes the graph contracts through `jarvis.graph` without constructing a graph at
   import time.

## Side-effect boundary

Graph construction registers callables but never invokes them. It does not initialize
a model, inspect files, call an OS tool, open a socket or connect to PostgreSQL/Redis.
The production PostgreSQL checkpointer adapter and migrations remain planned under
Global ID `140004`.

## Package impact

No package change. The implementation uses the existing exact `langgraph==1.2.7`
and `langgraph-checkpoint==4.1.1` pins plus Python standard-library modules.
