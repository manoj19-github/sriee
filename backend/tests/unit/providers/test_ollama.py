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
SECRET_MARKER = "provider-secret-must-not-escape"


def settings(**overrides: Any) -> OllamaSettings:
    values = {
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
        "loopback_only": True,
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

    assert str(captured.value) == "Invalid local model configuration"
    assert base_url not in str(captured.value)


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
