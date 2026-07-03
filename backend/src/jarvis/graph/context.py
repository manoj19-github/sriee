"""Authorized, reference-only context loading for Global ID 120002."""

from __future__ import annotations

import asyncio
import hmac
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from jarvis.graph.normalize import (
    PRINCIPAL_ID_PATTERN,
    TASK_ID_PATTERN,
)
from jarvis.tasks.models import CreateTaskRequest


REFERENCE_ID_PATTERN = re.compile(
    r"^(prj|cap|pol|mem)_[A-Za-z0-9_-]{8,128}$"
)
REFERENCE_VERSION_PATTERN = re.compile(r"^[1-9][0-9]*\.[0-9]+\.[0-9]+$")


class ContextKind(StrEnum):
    PROJECT = "project"
    CAPABILITY = "capability"
    POLICY = "policy"
    MEMORY = "memory"


class ContextClassification(StrEnum):
    INTERNAL = "internal"
    PERSONAL = "personal"
    SENSITIVE = "sensitive"


KIND_PREFIX = {
    ContextKind.PROJECT: "prj_",
    ContextKind.CAPABILITY: "cap_",
    ContextKind.POLICY: "pol_",
    ContextKind.MEMORY: "mem_",
}


class ContextLoadError(RuntimeError):
    """A content-free context failure safe for graph diagnostics."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"JARVIS context loading failed: {code}")


class ContextReference(BaseModel):
    """Opaque authorized reference; no source content can be represented."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reference_id: str = Field(pattern=REFERENCE_ID_PATTERN.pattern)
    kind: ContextKind
    actor_id: str = Field(
        min_length=3,
        max_length=128,
        pattern=PRINCIPAL_ID_PATTERN.pattern,
    )
    device_id: str | None = Field(
        default=None,
        min_length=3,
        max_length=128,
        pattern=PRINCIPAL_ID_PATTERN.pattern,
    )
    classification: ContextClassification
    version: str = Field(pattern=REFERENCE_VERSION_PATTERN.pattern)

    @model_validator(mode="after")
    def validate_kind_prefix(self) -> ContextReference:
        if not self.reference_id.startswith(KIND_PREFIX[self.kind]):
            raise ValueError("context reference prefix does not match kind")
        return self


class ContextQuery(BaseModel):
    """Ephemeral source query; request content is excluded from repr."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    actor_id: str
    device_id: str
    input_type: str
    content: str | None = Field(default=None, repr=False)
    purpose: str = "task_planning"


class ContextReferenceSource(Protocol):
    async def load_references(
        self,
        query: ContextQuery,
        *,
        limit: int,
    ) -> Sequence[ContextReference]:
        """Return only references authorized for the supplied query."""


@dataclass(frozen=True, slots=True)
class ContextSources:
    project: ContextReferenceSource
    capability: ContextReferenceSource
    policy: ContextReferenceSource
    memory: ContextReferenceSource


@dataclass(frozen=True, slots=True)
class ContextLoadSettings:
    project_limit: int = 4
    capability_limit: int = 1
    policy_limit: int = 1
    memory_limit: int = 8
    total_limit: int = 16
    source_timeout_seconds: float = 2.0


SOURCE_KINDS = {
    "project": ContextKind.PROJECT,
    "capability": ContextKind.CAPABILITY,
    "policy": ContextKind.POLICY,
    "memory": ContextKind.MEMORY,
}
SOURCE_ORDER = ("policy", "capability", "project", "memory")
REQUIRED_SOURCES = frozenset({"policy", "capability"})


def _validate_settings(settings: ContextLoadSettings) -> None:
    limits = (
        settings.project_limit,
        settings.capability_limit,
        settings.policy_limit,
        settings.memory_limit,
        settings.total_limit,
    )
    if (
        any(limit < 1 or limit > 100 for limit in limits)
        or settings.capability_limit != 1
        or settings.policy_limit != 1
        or settings.total_limit < 2
        or settings.source_timeout_seconds <= 0
        or settings.source_timeout_seconds > 30
    ):
        raise ContextLoadError("context_settings_incompatible")


def _build_query(state: Mapping[str, Any]) -> ContextQuery:
    if state.get("status") != "planning":
        raise ContextLoadError("context_state_invalid")
    task_id = state.get("task_id")
    actor_id = state.get("actor_id")
    device_id = state.get("device_id")
    if (
        not isinstance(task_id, str)
        or not TASK_ID_PATTERN.fullmatch(task_id)
        or not isinstance(actor_id, str)
        or not PRINCIPAL_ID_PATTERN.fullmatch(actor_id)
        or not isinstance(device_id, str)
        or not PRINCIPAL_ID_PATTERN.fullmatch(device_id)
    ):
        raise ContextLoadError("context_identity_invalid")

    raw_request = state.get("request")
    if not isinstance(raw_request, Mapping):
        raise ContextLoadError("context_request_invalid")
    try:
        request = CreateTaskRequest.model_validate(dict(raw_request))
    except ValidationError:
        raise ContextLoadError("context_request_invalid") from None

    return ContextQuery(
        task_id=task_id,
        actor_id=actor_id,
        device_id=device_id,
        input_type=request.input.type.value,
        content=request.input.content,
    )


async def _load_source(
    source: ContextReferenceSource,
    query: ContextQuery,
    *,
    limit: int,
    timeout: float,
) -> Sequence[ContextReference]:
    return await asyncio.wait_for(
        source.load_references(query, limit=limit),
        timeout=timeout,
    )


def _query_for_source(
    query: ContextQuery,
    source_name: str,
) -> ContextQuery:
    if source_name in {"project", "memory"}:
        return query
    return query.model_copy(update={"content": None})


def _validate_references(
    source_name: str,
    records: object,
    *,
    query: ContextQuery,
    limit: int,
) -> tuple[ContextReference, ...]:
    if not isinstance(records, Sequence) or isinstance(
        records,
        (str, bytes, bytearray),
    ):
        raise ContextLoadError("context_reference_invalid")
    if len(records) > limit:
        raise ContextLoadError("context_limit_exceeded")
    if source_name in REQUIRED_SOURCES and len(records) != 1:
        raise ContextLoadError("required_context_missing")

    expected_kind = SOURCE_KINDS[source_name]
    validated: list[ContextReference] = []
    for record in records:
        if not isinstance(record, ContextReference):
            raise ContextLoadError("context_reference_invalid")
        if record.kind is not expected_kind:
            raise ContextLoadError("context_reference_invalid")
        if not hmac.compare_digest(record.actor_id, query.actor_id):
            raise ContextLoadError("context_authorization_failed")
        if (
            record.device_id is not None
            and not hmac.compare_digest(record.device_id, query.device_id)
        ):
            raise ContextLoadError("context_authorization_failed")
        if source_name in REQUIRED_SOURCES and record.device_id is None:
            raise ContextLoadError("context_authorization_failed")
        validated.append(record)
    return tuple(validated)


async def loadBoundedContext(
    state: Mapping[str, Any],
    *,
    sources: ContextSources,
    settings: ContextLoadSettings | None = None,
) -> dict[str, Any]:
    """Load authorized opaque references under fixed limits and deadlines."""

    selected_settings = settings or ContextLoadSettings()
    _validate_settings(selected_settings)
    query = _build_query(state)
    limits = {
        "project": selected_settings.project_limit,
        "capability": selected_settings.capability_limit,
        "policy": selected_settings.policy_limit,
        "memory": selected_settings.memory_limit,
    }

    tasks = [
        _load_source(
            getattr(sources, source_name),
            _query_for_source(query, source_name),
            limit=limits[source_name],
            timeout=selected_settings.source_timeout_seconds,
        )
        for source_name in SOURCE_ORDER
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    references: list[ContextReference] = []
    safe_errors: list[dict[str, Any]] = []
    for source_name, result in zip(SOURCE_ORDER, results, strict=True):
        if isinstance(result, asyncio.CancelledError):
            raise result
        if isinstance(result, BaseException):
            if source_name in REQUIRED_SOURCES:
                raise ContextLoadError(
                    f"{source_name}_context_unavailable"
                ) from None
            safe_errors.append(
                {
                    "code": f"{source_name}_context_unavailable",
                    "source": source_name,
                    "retryable": True,
                }
            )
            continue
        references.extend(
            _validate_references(
                source_name,
                result,
                query=query,
                limit=limits[source_name],
            )
        )

    if len(references) > selected_settings.total_limit:
        raise ContextLoadError("context_limit_exceeded")
    reference_ids = [record.reference_id for record in references]
    if len(reference_ids) != len(set(reference_ids)):
        raise ContextLoadError("context_reference_duplicate")

    delta: dict[str, Any] = {"context_refs": reference_ids}
    if safe_errors:
        delta["errors"] = safe_errors
    return delta
