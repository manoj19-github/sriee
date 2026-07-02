"""Pure request normalization for Global ID 120001."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from packaging.version import InvalidVersion, Version
from pydantic import ValidationError

from jarvis.tasks.models import CreateTaskRequest


TASK_ID_PATTERN = re.compile(r"^tsk_[0-9a-f]{32}$")
THREAD_ID_PATTERN = re.compile(r"^thr_[0-9a-f]{32}$")
PRINCIPAL_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$"
)


class RequestNormalizationError(ValueError):
    """A content-free normalization failure safe for graph diagnostics."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"JARVIS request normalization failed: {code}")


@dataclass(frozen=True, slots=True)
class RequestNormalizationSettings:
    """Non-secret bounds for the normalization node."""

    max_serialized_request_bytes: int = 64 * 1024
    supported_contract_major: int = 1


def _generated_task_id(id_factory: Callable[[], str]) -> str:
    candidate = f"tsk_{id_factory()}"
    if not TASK_ID_PATTERN.fullmatch(candidate):
        raise RequestNormalizationError("request_id_generation_failed")
    return candidate


def _normalize_task_id(
    value: object,
    id_factory: Callable[[], str],
) -> str:
    if value is None or value == "":
        return _generated_task_id(id_factory)
    if not isinstance(value, str) or not TASK_ID_PATTERN.fullmatch(value):
        raise RequestNormalizationError("request_identity_invalid")
    return value


def _normalize_thread_id(value: object, task_id: str) -> str:
    if value is None or value == "":
        return f"thr_{task_id.removeprefix('tsk_')}"
    if not isinstance(value, str) or not THREAD_ID_PATTERN.fullmatch(value):
        raise RequestNormalizationError("request_identity_invalid")
    return value


def _validate_principal(value: object) -> None:
    if not isinstance(value, str) or not PRINCIPAL_ID_PATTERN.fullmatch(value):
        raise RequestNormalizationError("request_identity_invalid")


def _validate_contract(value: object, supported_major: int) -> str:
    if not isinstance(value, str):
        raise RequestNormalizationError("request_contract_unsupported")
    try:
        version = Version(value)
    except InvalidVersion:
        raise RequestNormalizationError(
            "request_contract_unsupported"
        ) from None
    if version.major != supported_major:
        raise RequestNormalizationError("request_contract_unsupported")
    return str(version)


def normalizeRequest(
    state: Mapping[str, Any],
    *,
    settings: RequestNormalizationSettings | None = None,
    id_factory: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Validate one request and return a minimal normalized graph-state delta."""

    selected_settings = settings or RequestNormalizationSettings()
    if (
        selected_settings.max_serialized_request_bytes < 1
        or selected_settings.supported_contract_major < 1
    ):
        raise RequestNormalizationError(
            "normalization_settings_incompatible"
        )

    status = state.get("status")
    if status not in {"created", "planning"}:
        raise RequestNormalizationError("request_status_invalid")

    _validate_principal(state.get("actor_id"))
    _validate_principal(state.get("device_id"))
    contract_version = _validate_contract(
        state.get("contract_version"),
        selected_settings.supported_contract_major,
    )

    raw_request = state.get("request")
    if not isinstance(raw_request, Mapping):
        raise RequestNormalizationError("request_payload_invalid")
    try:
        request = CreateTaskRequest.model_validate(dict(raw_request))
    except ValidationError:
        raise RequestNormalizationError("request_payload_invalid") from None

    normalized_request = request.model_dump(mode="json")
    serialized = json.dumps(
        normalized_request,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(serialized) > selected_settings.max_serialized_request_bytes:
        raise RequestNormalizationError("request_payload_too_large")

    generator = id_factory or (lambda: uuid4().hex)
    task_id = _normalize_task_id(state.get("task_id"), generator)
    thread_id = _normalize_thread_id(state.get("thread_id"), task_id)

    return {
        "contract_version": contract_version,
        "task_id": task_id,
        "thread_id": thread_id,
        "request": normalized_request,
        "status": "planning",
    }
