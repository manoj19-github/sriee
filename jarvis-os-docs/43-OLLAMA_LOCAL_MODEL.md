# Model Runtime Routing

## Decision

Development and test may use the explicitly allowlisted Ollama-compatible endpoint
`http://qwen.msqube.in/api/chat` with `qwen3.6:27b`. Production remains local-only:
it uses an Ollama service on loopback with an installed Qwen or Gemma model. Routing
is selected by `JARVIS_ENV`; there is no automatic remote/local fallback.

The model is a reasoning component, not an authority boundary. Model responses remain
untrusted data and must pass typed output validation, deterministic policy, approval
and executor checks before any side effect.

## Local setup

Install the signed Ollama Windows application, then pull and verify the configured
model:

```powershell
ollama pull qwen3:4b-instruct
ollama list
ollama --version
```

The desktop installation normally supervises the local service. Production health
checks use `GET /api/version` and `GET /api/tags`; no prompt is needed to establish
provider readiness.

## Configuration

Development/test configuration:

```text
JARVIS_ENV=development
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_CHAT_URL=http://qwen.msqube.in/api/chat
OLLAMA_API_KEY=<provider-issued-bearer-token>
OLLAMA_MODEL=qwen3.6:27b
OLLAMA_TIMEOUT_SECONDS=120
OLLAMA_CONNECT_TIMEOUT_SECONDS=5
OLLAMA_NUM_CTX=8192
OLLAMA_MAX_OUTPUT_TOKENS=1024
OLLAMA_TEMPERATURE=0.2
OLLAMA_KEEP_ALIVE=5m
```

`OLLAMA_API_KEY` is optional in the schema but currently required by the supplied
endpoint, which returned `unauthorized` without it. Store the real value only in the
ignored `.env` or a secret manager. Never commit it.

Production configuration:

```text
JARVIS_ENV=production
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:4b-instruct
```

Production rejects remote chat URLs and provider credentials. Development/test
accepts only the exact allowlisted host and `/api/chat` path; arbitrary hosts,
credentials embedded in URLs, query strings and fragments fail configuration.

## Prompt and output flow

1. Deployment code loads `01-MASTER_PROMPT.md` as a system message.
2. Only bounded, purpose-authorized context is added.
3. The caller supplies a typed response JSON Schema when structured output is needed.
4. The compatible provider returns text or a JSON object plus token/duration
   metadata; separate
   provider thinking output is disabled.
5. The owning graph node validates semantic output; invalid output is repaired once
   or fails safely.
6. No model response is executed directly.

The gateway never logs raw prompts or responses. Product telemetry may record only
content-free model name, token counts, duration and safe outcome codes.

## Hardware profile

`qwen3:4b-instruct` is the current hardware-balanced local example for a 16 GB RAM /
4 GB VRAM Windows laptop. Production may select a validated local Qwen or Gemma model.
Larger models require latency, memory, quality and safety evidence plus a version
record.

## Failure behavior

- Service unavailable: readiness is degraded; deterministic desktop functions remain
  available.
- Model missing: readiness reports `model_unavailable`; no automatic download occurs
  inside the backend.
- Timeout or HTTP failure: return a fixed safe code without response content.
- Malformed or mismatched response: reject it as `ollama_response_invalid`.
- Remote provider URL in production: configuration fails before client creation.
- Development endpoint 401/403: readiness is unavailable until a valid secret token
  is configured.

Model installation is an explicit developer/user action. The backend never silently
downloads, updates or replaces a model.

Remote development sends prompt content outside the machine. Use synthetic or
explicitly approved development data only; never send credentials, personal memory,
biometric data, camera/microphone content or production records.
