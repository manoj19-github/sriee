# FastAPI Backend

## Modules

`api`, `application`, `domain`, `graph`, `policy`, `providers`, `persistence`, `telemetry`, and `workers`. API handlers authenticate, validate, invoke use cases, and map domain errors; they do not contain graph or SQL logic.

## Lifecycle

FastAPI lifespan initializes settings, DB pools, checkpointer, model clients, telemetry, and bounded workers; shutdown rejects new tasks, drains safe work, closes sockets, and releases leases.

## API behavior

REST creates/queries durable resources. WebSocket streams task events and accepts control messages. All mutations require authentication, idempotency key, contract version, and audit context. Error responses use stable machine codes and correlation IDs.

## Reliability

Use transactions and outbox for state/events. Apply deadlines and cancellation. Retries cover classified transient reads; never blanket-retry model or side-effect calls. Health endpoints distinguish liveness, readiness, and dependency status. OpenAPI is generated and diff-checked.

## Local model provider

The Ollama adapter is lifecycle-managed as the `providers` runtime resource. It binds
only to an allowlisted loopback URL, verifies the configured model through version/tag
health endpoints, sends bounded non-streaming chat requests and supports optional JSON
Schema output. Provider errors are sanitized and do not include prompts, responses,
URLs or exception text. There is no automatic cloud fallback or model download.
