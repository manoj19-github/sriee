# FastAPI Backend

## Modules

`api`, `application`, `domain`, `graph`, `policy`, `providers`, `persistence`, `telemetry`, and `workers`. API handlers authenticate, validate, invoke use cases, and map domain errors; they do not contain graph or SQL logic.

## Lifecycle

FastAPI lifespan initializes settings, DB pools, checkpointer, model clients, telemetry, and bounded workers; shutdown rejects new tasks, drains safe work, closes sockets, and releases leases.

## API behavior

REST creates/queries durable resources. WebSocket streams task events and accepts control messages. All mutations require authentication, idempotency key, contract version, and audit context. Error responses use stable machine codes and correlation IDs.

## Reliability

Use transactions and outbox for state/events. Apply deadlines and cancellation. Retries cover classified transient reads; never blanket-retry model or side-effect calls. Health endpoints distinguish liveness, readiness, and dependency status. OpenAPI is generated and diff-checked.

## Model provider routing

The Ollama-compatible adapter is lifecycle-managed as the `providers` runtime
resource. Development/test may use the single allowlisted Qwen endpoint with an
optional secret Bearer token; production accepts only loopback Ollama and rejects
remote URLs or provider credentials. Requests are bounded and non-streaming, separate
thinking output is disabled, and optional JSON Schema output is supported. Provider
errors are sanitized and do not include prompts, responses, URLs, credentials or
exception text. There is no automatic fallback or model download.
