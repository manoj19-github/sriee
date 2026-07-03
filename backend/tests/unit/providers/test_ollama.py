from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from jarvis.providers import (
    OllamaChatRequest,
    OllamaMessage,
    OllamaModelGateway,
    OllamaProviderError,
    OllamaSettings,
    OllamaSettingsError,
    callLocalModel,
    loadOllamaSettings,
)


MODEL = "qwen3:4b-instruct"
REMOTE_MODEL = "qwen3.6:27b"
REMOTE_CHAT_URL = "http://qwen.msqube.in/api/chat"
SECRET_MARKER = "provider-secret-must-not-escape"


def settings(**overrides: Any) -> OllamaSettings:
    values = {
        "JARVIS_ENV": "production",
        "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
        "OLLAMA_MODEL": MODEL,
        "OLLAMA_TIMEOUT_SECONDS": 30,
        "OLLAMA_CONNECT_TIMEOUT_SECONDS": 2,
        "OLLAMA_NUM_CTX": 4096,
        "OLLAMA_MAX_OUTPUT_TOKENS": 256,
        "OLLAMA_TEMPERATURE": 0.1,
        "OLLAMA_KEEP_ALIVE": "1m",
    }
    values.update(overrides)
    return loadOllamaSettings(overrides=values)


def remote_settings(**overrides: Any) -> OllamaSettings:
    values = {
        "JARVIS_ENV": "development",
        "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
        "OLLAMA_CHAT_URL": REMOTE_CHAT_URL,
        "OLLAMA_MODEL": REMOTE_MODEL,
        "OLLAMA_TIMEOUT_SECONDS": 30,
        "OLLAMA_CONNECT_TIMEOUT_SECONDS": 2,
        "OLLAMA_NUM_CTX": 4096,
        "OLLAMA_MAX_OUTPUT_TOKENS": 256,
        "OLLAMA_TEMPERATURE": 0.1,
        "OLLAMA_KEEP_ALIVE": "1m",
    }
    values.update(overrides)
    return loadOllamaSettings(overrides=values)


def client_for(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url="http://127.0.0.1:11434",
        transport=httpx.MockTransport(handler),
    )


def request(*, structured: bool = False) -> OllamaChatRequest:
    return OllamaChatRequest(
        messages=(
            OllamaMessage(
                role="system",
                content="Return only the requested bounded result.",
            ),
            OllamaMessage(role="user", content="Summarize this task."),
        ),
        response_schema=(
            {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
                "additionalProperties": False,
            }
            if structured
            else None
        ),
    )


def api_response(*, content: str = "Local response", model: str = MODEL):
    return {
        "model": model,
        "message": {"role": "assistant", "content": content},
        "done": True,
        "prompt_eval_count": 12,
        "eval_count": 5,
        "total_duration": 123_456,
    }


def test_loads_safe_loopback_settings_and_diagnostics() -> None:
    loaded = settings()

    assert loaded.base_url == "http://127.0.0.1:11434"
    assert loaded.model == MODEL
    assert loaded.num_ctx == 4096
    assert loaded.safe_diagnostics() == {
        "provider": "ollama",
        "environment": "production",
        "routing": "local_ollama",
        "remote_egress": False,
        "model": MODEL,
        "num_ctx": 4096,
        "max_output_tokens": 256,
        "structured_output_supported": True,
    }


@pytest.mark.parametrize(
    "base_url",
    [
        "https://127.0.0.1:11434",
        "http://example.com:11434",
        "http://user:password@127.0.0.1:11434",
        "http://127.0.0.1:11434/api",
        "http://127.0.0.1",
    ],
)
def test_rejects_non_loopback_or_ambiguous_provider_urls(
    base_url: str,
) -> None:
    with pytest.raises(OllamaSettingsError) as captured:
        settings(OLLAMA_BASE_URL=base_url)

    assert str(captured.value) == "Invalid model provider configuration"
    assert base_url not in str(captured.value)


def test_allows_only_explicit_remote_endpoint_in_development_or_test() -> None:
    loaded = remote_settings()

    assert loaded.chat_endpoint == REMOTE_CHAT_URL
    assert loaded.remote_development is True
    assert loaded.safe_diagnostics() == {
        "provider": "ollama",
        "environment": "development",
        "routing": "remote_development",
        "remote_egress": True,
        "model": REMOTE_MODEL,
        "num_ctx": 4096,
        "max_output_tokens": 256,
        "structured_output_supported": True,
    }
    assert remote_settings(JARVIS_ENV="test").remote_development is True


@pytest.mark.parametrize(
    ("environment", "chat_url"),
    [
        ("production", REMOTE_CHAT_URL),
        ("development", "http://example.com/api/chat"),
        ("test", "http://user:password@qwen.msqube.in/api/chat"),
        ("development", "http://qwen.msqube.in/other"),
        ("development", "http://qwen.msqube.in:8080/api/chat"),
        ("development", "http://qwen.msqube.in/api/chat?secret=value"),
    ],
)
def test_rejects_remote_endpoint_outside_allowlisted_development_policy(
    environment: str,
    chat_url: str,
) -> None:
    with pytest.raises(OllamaSettingsError) as captured:
        remote_settings(
            JARVIS_ENV=environment,
            OLLAMA_CHAT_URL=chat_url,
        )

    assert str(captured.value) == "Invalid model provider configuration"
    assert chat_url not in str(captured.value)


def test_rejects_provider_credentials_for_local_production() -> None:
    with pytest.raises(OllamaSettingsError) as captured:
        settings(OLLAMA_API_KEY=SECRET_MARKER)

    assert str(captured.value) == "Invalid model provider configuration"
    assert SECRET_MARKER not in str(captured.value)


def test_message_and_schema_contracts_are_bounded() -> None:
    with pytest.raises(ValidationError):
        OllamaMessage(role="user", content=" ")
    with pytest.raises(ValidationError):
        OllamaMessage(role="user", content="unsafe\x00content")
    with pytest.raises(ValidationError):
        OllamaChatRequest(
            messages=(OllamaMessage(role="user", content="hello"),),
            response_schema={"type": "array"},
        )
    with pytest.raises(ValidationError):
        OllamaChatRequest(
            messages=(OllamaMessage(role="user", content="hello"),),
            response_schema={
                "type": "object",
                "invalid": object(),
            },
        )


def test_health_requires_started_gateway_and_configured_model() -> None:
    async def handler(http_request: httpx.Request) -> httpx.Response:
        if http_request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.31.1"})
        if http_request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": MODEL}]})
        raise AssertionError("unexpected path")

    async def exercise():
        client = client_for(handler)
        gateway = OllamaModelGateway(settings(), client=client)
        before = await gateway.check_health()
        await gateway.start()
        after = await gateway.check_health()
        await gateway.close()
        return before, after, client.is_closed

    before, after, closed = asyncio.run(exercise())

    assert before.ready is False
    assert before.code == "not_started"
    assert after.ready is True
    assert after.code == "ready"
    assert closed is True


def test_health_reports_missing_model_without_leaking_response() -> None:
    async def handler(http_request: httpx.Request) -> httpx.Response:
        if http_request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.31.1"})
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "different-model", "details": SECRET_MARKER}
                ]
            },
        )

    async def exercise():
        gateway = OllamaModelGateway(
            settings(),
            client=client_for(handler),
        )
        await gateway.start()
        health = await gateway.check_health()
        await gateway.close()
        return health

    health = asyncio.run(exercise())

    assert health.ready is False
    assert health.code == "model_unavailable"
    assert SECRET_MARKER not in health.code


def test_remote_development_health_uses_non_prompt_endpoint_probe() -> None:
    captured: list[tuple[str, str]] = []

    async def handler(http_request: httpx.Request) -> httpx.Response:
        captured.append((http_request.method, str(http_request.url)))
        return httpx.Response(405)

    async def exercise():
        gateway = OllamaModelGateway(
            remote_settings(),
            client=client_for(handler),
        )
        await gateway.start()
        health = await gateway.check_health()
        await gateway.close()
        return health

    health = asyncio.run(exercise())

    assert health.ready is True
    assert health.code == "ready"
    assert captured == [("GET", REMOTE_CHAT_URL)]


def test_remote_health_rejects_unauthorized_endpoint() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": SECRET_MARKER})

    async def exercise():
        gateway = OllamaModelGateway(
            remote_settings(),
            client=client_for(handler),
        )
        await gateway.start()
        health = await gateway.check_health()
        await gateway.close()
        return health

    health = asyncio.run(exercise())

    assert health.ready is False
    assert health.code == "unavailable"
    assert SECRET_MARKER not in health.code


def test_chat_sends_bounded_local_options_and_returns_typed_metadata() -> None:
    captured: dict[str, Any] = {}

    async def handler(http_request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(http_request.content))
        return httpx.Response(200, json=api_response())

    async def exercise():
        gateway = OllamaModelGateway(
            settings(),
            client=client_for(handler),
        )
        await gateway.start()
        result = await callLocalModel(gateway, request())
        await gateway.close()
        return result

    result = asyncio.run(exercise())

    assert captured == {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Return only the requested bounded result.",
            },
            {"role": "user", "content": "Summarize this task."},
        ],
        "stream": False,
        "think": False,
        "keep_alive": "1m",
        "options": {
            "temperature": 0.1,
            "num_ctx": 4096,
            "num_predict": 256,
        },
    }
    assert result.model == MODEL
    assert result.content == "Local response"
    assert result.prompt_tokens == 12
    assert result.output_tokens == 5
    assert result.total_duration_ns == 123_456
    assert result.structured is False


def test_remote_development_chat_uses_supplied_endpoint_and_minimal_payload() -> None:
    captured: dict[str, Any] = {}

    async def handler(http_request: httpx.Request) -> httpx.Response:
        captured["url"] = str(http_request.url)
        captured["payload"] = json.loads(http_request.content)
        return httpx.Response(
            200,
            json=api_response(
                content="Hello from development",
                model=REMOTE_MODEL,
            ),
        )

    async def exercise():
        gateway = OllamaModelGateway(
            remote_settings(),
            client=client_for(handler),
        )
        await gateway.start()
        result = await gateway.chat(
            OllamaChatRequest(
                messages=(OllamaMessage(role="user", content="hii"),)
            )
        )
        await gateway.close()
        return result

    result = asyncio.run(exercise())

    assert captured == {
        "url": REMOTE_CHAT_URL,
        "payload": {
            "model": REMOTE_MODEL,
            "messages": [{"role": "user", "content": "hii"}],
            "stream": False,
            "think": False,
        },
    }
    assert result.model == REMOTE_MODEL
    assert result.content == "Hello from development"


def test_remote_bearer_credential_is_request_scoped_and_not_diagnostic() -> None:
    captured_authorization = ""

    async def handler(http_request: httpx.Request) -> httpx.Response:
        nonlocal captured_authorization
        captured_authorization = http_request.headers["Authorization"]
        return httpx.Response(
            200,
            json=api_response(model=REMOTE_MODEL),
        )

    selected_settings = remote_settings(OLLAMA_API_KEY=SECRET_MARKER)

    async def exercise():
        gateway = OllamaModelGateway(
            selected_settings,
            client=client_for(handler),
        )
        await gateway.start()
        result = await gateway.chat(request())
        await gateway.close()
        return result

    result = asyncio.run(exercise())

    assert captured_authorization == f"Bearer {SECRET_MARKER}"
    assert result.model == REMOTE_MODEL
    assert SECRET_MARKER not in str(selected_settings)
    assert SECRET_MARKER not in str(selected_settings.safe_diagnostics())


def test_structured_request_passes_schema_and_requires_json_object() -> None:
    captured: dict[str, Any] = {}

    async def handler(http_request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(http_request.content))
        return httpx.Response(
            200,
            json=api_response(content='{"summary":"Ready"}'),
        )

    async def exercise():
        gateway = OllamaModelGateway(
            settings(),
            client=client_for(handler),
        )
        await gateway.start()
        result = await gateway.chat(request(structured=True))
        await gateway.close()
        return result

    result = asyncio.run(exercise())

    assert captured["format"]["type"] == "object"
    assert captured["format"]["additionalProperties"] is False
    assert json.loads(result.content) == {"summary": "Ready"}
    assert result.structured is True


def test_chat_requires_started_gateway() -> None:
    gateway = OllamaModelGateway(settings(), client=client_for(lambda _: None))

    with pytest.raises(OllamaProviderError) as captured:
        asyncio.run(gateway.chat(request()))

    assert captured.value.code == "ollama_not_started"


@pytest.mark.parametrize(
    ("exception", "code"),
    [
        (httpx.ReadTimeout(SECRET_MARKER), "ollama_timeout"),
        (httpx.ConnectError(SECRET_MARKER), "ollama_unavailable"),
    ],
)
def test_transport_failures_are_sanitized(
    exception: httpx.HTTPError,
    code: str,
) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        raise exception

    async def exercise():
        gateway = OllamaModelGateway(
            settings(),
            client=client_for(handler),
        )
        await gateway.start()
        try:
            await gateway.chat(request())
        finally:
            await gateway.close()

    with pytest.raises(OllamaProviderError) as captured:
        asyncio.run(exercise())

    assert captured.value.code == code
    assert SECRET_MARKER not in str(captured.value)


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (
            httpx.Response(500, text=SECRET_MARKER),
            "ollama_unavailable",
        ),
        (
            httpx.Response(404, text=SECRET_MARKER),
            "ollama_model_unavailable",
        ),
        (
            httpx.Response(200, text="not-json"),
            "ollama_response_invalid",
        ),
        (
            httpx.Response(
                200,
                json=api_response(model="unexpected-model"),
            ),
            "ollama_response_invalid",
        ),
    ],
)
def test_provider_and_response_failures_are_sanitized(
    response: httpx.Response,
    code: str,
) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return response

    async def exercise():
        gateway = OllamaModelGateway(
            settings(),
            client=client_for(handler),
        )
        await gateway.start()
        try:
            await gateway.chat(request())
        finally:
            await gateway.close()

    with pytest.raises(OllamaProviderError) as captured:
        asyncio.run(exercise())

    assert captured.value.code == code
    assert SECRET_MARKER not in str(captured.value)


def test_structured_response_rejects_non_json_content() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=api_response(content=SECRET_MARKER),
        )

    async def exercise():
        gateway = OllamaModelGateway(
            settings(),
            client=client_for(handler),
        )
        await gateway.start()
        try:
            await gateway.chat(request(structured=True))
        finally:
            await gateway.close()

    with pytest.raises(OllamaProviderError) as captured:
        asyncio.run(exercise())

    assert captured.value.code == "ollama_response_invalid"
    assert SECRET_MARKER not in str(captured.value)
