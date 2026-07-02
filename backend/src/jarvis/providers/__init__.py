"""Local and optional model-provider gateways."""

from jarvis.providers.ollama import (
    OllamaChatRequest,
    OllamaChatResponse,
    OllamaMessage,
    OllamaModelGateway,
    OllamaProviderError,
    OllamaSettings,
    OllamaSettingsError,
    callLocalModel,
    loadOllamaSettings,
)

__all__ = [
    "OllamaChatRequest",
    "OllamaChatResponse",
    "OllamaMessage",
    "OllamaModelGateway",
    "OllamaProviderError",
    "OllamaSettings",
    "OllamaSettingsError",
    "callLocalModel",
    "loadOllamaSettings",
]
