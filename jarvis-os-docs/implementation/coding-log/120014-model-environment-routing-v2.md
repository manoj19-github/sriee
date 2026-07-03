# Coding Log — 120014 Model Environment Routing v2

| Field | Value |
|---|---|
| Date | 2026-07-03 |
| Global ID | `120014` |
| Status | Complete |

## Delivered behavior

1. Added explicit `development`, `test` and `production` provider routing.
2. Allowlisted only `qwen.msqube.in/api/chat` for remote development/test use.
3. Configured the development example for `qwen3.6:27b`.
4. Kept production strictly on loopback HTTP Ollama with no remote fallback.
5. Remote requests use the supplied minimal `model/messages/stream/think` payload;
   local requests retain bounded Ollama options and keep-alive.
6. Added optional `OLLAMA_API_KEY` Bearer authentication as a Pydantic `SecretStr`.
7. Rejects provider credentials for local production and never includes them in
   diagnostics or exceptions.
8. Remote health uses a non-prompt endpoint probe and treats 401/403/404/5xx as not
   ready; local health retains version/tag/model checks.
9. Updated the ignored `.env` for development and the secret-safe `.env.example`.

## Live endpoint finding

A content-minimal live request using the supplied `"hii"` payload reached the endpoint
but returned `{"error":"unauthorized"}`. No credential was supplied or discovered.
The gateway therefore supports a caller-provided secret token, while the local
ignored `.env` intentionally contains no guessed or placeholder credential.

## Security and package impact

Remote development is explicit egress and should use synthetic/approved data only.
URLs with arbitrary hosts, embedded credentials, query strings or fragments fail
closed. No package changed; root `requirements.txt` retains 75 exact pins.
