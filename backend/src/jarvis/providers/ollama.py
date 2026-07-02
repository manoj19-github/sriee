"""Loopback-only Ollama gateway for Global ID 120014."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal, Mapping
from urllib.parse import urlsplit

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from jarvis.runtime.lifecycle import DependencyHealth


MODEL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


class OllamaSettingsError(RuntimeError):
    """Sanitized local-provider configuration failure."""


class OllamaProviderError(RuntimeError):
    """Sanitized local-provider runtime failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Local model request failed: {code}")


class OllamaSettings(BaseSettings):
    """Immutable, loopback-only Ollama configuration."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=None,
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        validate_default=True,
    )

    base_url: str = Field(
        default="http://127.0.0.1:11434",
        validation_alias="OLLAMA_BASE_URL",
    )
    model: str = Field(
        default="qwen3:4b-instruct",
        validation_alias="OLLAMA_MODEL",
    )
    timeout_seconds: float = Field(
        default=120.0,
        ge=1.0,
        le=300.0,
        validation_alias="OLLAMA_TIMEOUT_SECONDS",
    )
    connect_timeout_seconds: float = Field(
        default=5.0,
        ge=0.25,
        le=30.0,
        validation_alias="OLLAMA_CONNECT_TIMEOUT_SECONDS",
    )
    num_ctx: int = Field(
        default=8192,
        ge=1024,
        le=32768,
        validation_alias="OLLAMA_NUM_CTX",
    )
    max_output_tokens: int = Field(
        default=1024,
        ge=1,
        le=4096,
        validation_alias="OLLAMA_MAX_OUTPUT_TOKENS",
    )
    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        validation_alias="OLLAMA_TEMPERATURE",
    )
    keep_alive: str = Field(
        default="5m",
        pattern=r"^(0|[1-9][0-9]{0,3}[smh])$",
        validation_alias="OLLAMA_KEEP_ALIVE",
    )
    max_response_chars: int = Field(
        default=65_536,
        ge=1_024,
        le=262_144,
        validation_alias="OLLAMA_MAX_RESPONSE_CHARS",
    )

    @field_validator("base_url")
    @classmethod
    def validate_loopback_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        try:
            port = parsed.port
        except ValueError:
            raise ValueError("invalid provider port") from None
        if (
            parsed.scheme != "http"
            or parsed.hostname not in LOOPBACK_HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
            or port is None
            or not 1 <= port <= 65535
        ):
            raise ValueError("OLLAMA_BASE_URL must be loopback HTTP with a port")
        return normalized

    @field_validator("model")
    @classmethod
    def validate_model_name(cls, value: str) -> str:
        normalized = value.strip()
        if not MODEL_NAME_PATTERN.fullmatch(normalized):
            raise ValueError("invalid Ollama model name")
        return normalized

    def safe_diagnostics(self) -> dict[str, Any]:
        return {
            "provider": "ollama",
            "loopback_only": True,
            "model": self.model,
            "num_ctx": self.num_ctx,
            "max_output_tokens": self.max_output_tokens,
            "structured_output_supported": True,
        }


def loadOllamaSettings(
    *,
    env_file: str | Path | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> OllamaSettings:
    """Load local-provider settings without exposing rejected values."""

    try:
        return OllamaSettings(_env_file=env_file, **dict(overrides or {}))
    except ValidationError:
        raise OllamaSettingsError("Invalid local model configuration") from None


class OllamaMessage(BaseModel):
    """One bounded chat message."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=32_768)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if not value.strip() or "\x00" in value:
            raise ValueError("message content is invalid")
        return value


class OllamaChatRequest(BaseModel):
    """Bounded provider-neutral input for local chat completion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    messages: tuple[OllamaMessage, ...] = Field(min_length=1, max_length=32)
    response_schema: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_request_bounds(self) -> OllamaChatRequest:
        if sum(len(message.content) for message in self.messages) > 65_536:
            raise ValueError("combined message content is too large")
        if self.response_schema is not None:
            if self.response_schema.get("type") != "object":
                raise ValueError("response schema must describe an object")
            try:
                encoded = json.dumps(
                    self.response_schema,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
            except (TypeError, ValueError):
                raise ValueError("response schema must be JSON-compatible") from None
            if len(encoded) > 32_768:
                raise ValueError("response schema is too large")
        return self


class OllamaChatResponse(BaseModel):
    """Minimal content and content-free performance metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str
    content: str
    prompt_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_duration_ns: int = Field(ge=0)
    structured: bool


class _OllamaMessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: str
    content: str


class _OllamaApiResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str
    message: _OllamaMessageResponse
    done: bool
    prompt_eval_count: int = Field(default=0, ge=0)
    eval_count: int = Field(default=0, ge=0)
    total_duration: int = Field(default=0, ge=0)


class OllamaModelGateway:
    """Lifecycle-managed local model gateway with no cloud fallback."""

    def __init__(
        self,
        settings: OllamaSettings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._client = client
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.settings.base_url,
                timeout=httpx.Timeout(
                    self.settings.timeout_seconds,
                    connect=self.settings.connect_timeout_seconds,
                ),
                trust_env=False,
                headers={"User-Agent": "jarvis-os-local-provider/1.0"},
            )
        self._started = True

    async def check_health(self) -> DependencyHealth:
        if not self._started or self._client is None:
            return DependencyHealth(ready=False, code="not_started")
        try:
            version_response = await self._client.get("/api/version")
            tags_response = await self._client.get("/api/tags")
            if (
                version_response.status_code != 200
                or tags_response.status_code != 200
            ):
                return DependencyHealth(ready=False, code="unavailable")
            version_payload = version_response.json()
            tags_payload = tags_response.json()
            if not isinstance(version_payload.get("version"), str):
                return DependencyHealth(ready=False, code="invalid_response")
            names = {
                model.get("name")
                for model in tags_payload.get("models", [])
                if isinstance(model, dict)
            }
            if self.settings.model not in names:
                return DependencyHealth(ready=False, code="model_unavailable")
            return DependencyHealth(ready=True, code="ready")
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            return DependencyHealth(ready=False, code="unavailable")

    async def close(self) -> None:
        client = self._client
        self._client = None
        self._started = False
        if client is not None:
            await client.aclose()

    async def chat(self, request: OllamaChatRequest) -> OllamaChatResponse:
        if not self._started or self._client is None:
            raise OllamaProviderError("ollama_not_started")

        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": [
                message.model_dump(mode="json")
                for message in request.messages
            ],
            "stream": False,
            "think": False,
            "keep_alive": self.settings.keep_alive,
            "options": {
                "temperature": self.settings.temperature,
                "num_ctx": self.settings.num_ctx,
                "num_predict": self.settings.max_output_tokens,
            },
        }
        if request.response_schema is not None:
            payload["format"] = request.response_schema

        try:
            response = await self._client.post("/api/chat", json=payload)
        except httpx.TimeoutException:
            raise OllamaProviderError("ollama_timeout") from None
        except httpx.HTTPError:
            raise OllamaProviderError("ollama_unavailable") from None

        if response.status_code == 404:
            raise OllamaProviderError("ollama_model_unavailable")
        if response.status_code != 200:
            raise OllamaProviderError("ollama_unavailable")

        try:
            result = _OllamaApiResponse.model_validate(response.json())
        except (ValidationError, ValueError):
            raise OllamaProviderError("ollama_response_invalid") from None
        if (
            not result.done
            or result.model != self.settings.model
            or result.message.role != "assistant"
            or not result.message.content.strip()
            or len(result.message.content) > self.settings.max_response_chars
        ):
            raise OllamaProviderError("ollama_response_invalid")

        structured = request.response_schema is not None
        if structured:
            try:
                parsed = json.loads(result.message.content)
            except json.JSONDecodeError:
                raise OllamaProviderError("ollama_response_invalid") from None
            if not isinstance(parsed, dict):
                raise OllamaProviderError("ollama_response_invalid")

        return OllamaChatResponse(
            model=result.model,
            content=result.message.content,
            prompt_tokens=result.prompt_eval_count,
            output_tokens=result.eval_count,
            total_duration_ns=result.total_duration,
            structured=structured,
        )


async def callLocalModel(
    gateway: OllamaModelGateway,
    request: OllamaChatRequest,
) -> OllamaChatResponse:
    """Canonical function-map entry point for the local model gateway."""

    return await gateway.chat(request)
