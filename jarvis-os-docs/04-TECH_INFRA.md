# Technical Infrastructure

## Baseline

| Layer | Choice | Notes |
|---|---|---|
| Desktop | C# on current supported .NET LTS, WPF | Pin exact SDK in `global.json`; reassess WinUI only for a measured need |
| Backend | Python 3.12+, FastAPI, Pydantic v2 | Async I/O; lifespan-managed resources |
| Orchestration | LangGraph 1.x | Durable checkpointer, interrupts, typed state |
| Data | PostgreSQL 16+ | App data, audit index, graph checkpoints |
| Ephemeral | Redis 7+ | Optional cache, presence, rate limits, distributed leases |
| AI | Provider-neutral gateway | Local default; OpenAI/Anthropic/Gemini optional |
| Telemetry | OpenTelemetry | Traces, metrics, structured logs; local collector |
| Packaging | MSIX for desktop; signed Python bundle/container | Reproducible, checksummed artifacts |

Use supported versions at implementation time; this document intentionally avoids pretending today’s minor versions will remain current. Record pins and upgrade dates in lockfiles and `35-VERSIONING.md`.

## Environments

- Dev: loopback services, disposable DB, fake executor, seeded scenarios.
- Test: isolated Windows VM plus containerized dependencies.
- Preview: signed prerelease on a dedicated test device.
- Production: per-user local installation; optional managed cloud control plane later.

## Configuration hierarchy

Defaults < machine config < user config < environment < command-line emergency override. Secrets use Windows Credential Manager/DPAPI or a managed vault; never `.env` in production. Validate configuration at startup and log only safe fingerprints.

## Network posture

Bind backend to `127.0.0.1` unless remote mode is explicitly designed. Generate per-install device credentials. Require TLS/mTLS for non-loopback traffic. Deny arbitrary outbound destinations; provider and research connectors use allowlisted domains and quotas.

## Data classes

Public, internal, personal, sensitive, secret. Each field and artifact declares classification, retention, encryption, and allowed model destinations. Screenshots default to sensitive and short-lived; credentials are secret and prohibited from prompts.

## Capacity starting point

One active user, four concurrent read-only graph branches, one side-effect lane per resource, bounded queues, 25 MB artifact limit, and explicit backpressure. Scale only from measurements.
