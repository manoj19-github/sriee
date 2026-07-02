# Ollama Local Model Runtime

## Decision

Ollama is the default local language-model runtime for JARVIS development. The
hardware-balanced default model is `qwen3:4b-instruct`; cloud fallback is disabled.
The provider listens only on `http://127.0.0.1:11434`.

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

The desktop installation normally supervises the local service. Development health
checks use `GET /api/version` and `GET /api/tags`; no prompt is needed to establish
provider readiness.

## Configuration

Copy the secret-free Ollama fields from `.env.example` into an ignored local `.env`
or provide them through the process environment:

```text
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:4b-instruct
OLLAMA_TIMEOUT_SECONDS=120
OLLAMA_CONNECT_TIMEOUT_SECONDS=5
OLLAMA_NUM_CTX=8192
OLLAMA_MAX_OUTPUT_TOKENS=1024
OLLAMA_TEMPERATURE=0.2
OLLAMA_KEEP_ALIVE=5m
```

The gateway rejects remote, HTTPS, credential-bearing, path-bearing and portless
provider URLs. It does not accept provider tokens because the supported runtime is
loopback-only.

## Prompt and output flow

1. Deployment code loads `01-MASTER_PROMPT.md` as a system message.
2. Only bounded, purpose-authorized context is added.
3. The caller supplies a typed response JSON Schema when structured output is needed.
4. Ollama returns text or a JSON object plus token/duration metadata; separate
   provider thinking output is disabled.
5. The owning graph node validates semantic output; invalid output is repaired once
   or fails safely.
6. No model response is executed directly.

The gateway never logs raw prompts or responses. Product telemetry may record only
content-free model name, token counts, duration and safe outcome codes.

## Hardware profile

`qwen3:4b-instruct` is selected for responsive development on a 16 GB RAM / 4 GB VRAM
Windows laptop. Larger models may be evaluated separately, but changing the default
requires latency, memory, quality and safety evidence plus a version record.

## Failure behavior

- Service unavailable: readiness is degraded; deterministic desktop functions remain
  available.
- Model missing: readiness reports `model_unavailable`; no automatic download occurs
  inside the backend.
- Timeout or HTTP failure: return a fixed safe code without response content.
- Malformed or mismatched response: reject it as `ollama_response_invalid`.
- Remote provider URL: configuration fails before client creation.

Model installation is an explicit developer/user action. The backend never silently
downloads, updates or replaces a model.
