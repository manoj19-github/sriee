"""Stable, secret-safe API and WebSocket errors for Global ID 110011."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from jarvis.tasks.repository import (
    ApprovalConsumedError,
    ApprovalDigestMismatchError,
    ApprovalExpiredError,
    IdempotencyConflictError,
)
from jarvis.tasks.service import (
    ApprovalNotFoundError,
    InvalidPaginationError,
    InvalidRequestIdentifierError,
    TaskNotFoundError,
)


SAFE_CORRELATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{15,127}$")
SAFE_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
MAX_VALIDATION_ISSUES = 20


class ErrorBody(BaseModel):
    """Public error fields shared by HTTP and WebSocket transports."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(pattern=SAFE_ERROR_CODE.pattern)
    message: str = Field(min_length=1, max_length=256)
    correlation_id: str = Field(pattern=SAFE_CORRELATION_ID.pattern)
    retryable: bool
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    """Stable HTTP error response envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    error: ErrorBody


@dataclass(frozen=True, slots=True)
class ErrorSpec:
    status_code: int
    message: str
    retryable: bool = False


@dataclass(frozen=True, slots=True)
class MappedDomainError:
    """Transport-neutral result of mapping one failure."""

    status_code: int
    body: ErrorBody

    def http_envelope(self) -> ErrorEnvelope:
        return ErrorEnvelope(error=self.body)


class WebSocketProtocolError(RuntimeError):
    """An allowlisted WebSocket protocol failure safe for the desktop client."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("websocket protocol error")


ERROR_SPECS: dict[str, ErrorSpec] = {
    "approval_consumed": ErrorSpec(409, "Approval has already been decided."),
    "approval_digest_mismatch": ErrorSpec(
        409,
        "Approval does not match the pending action.",
    ),
    "approval_expired": ErrorSpec(409, "Approval expired before the decision."),
    "approval_not_found": ErrorSpec(404, "Approval was not found."),
    "bad_request": ErrorSpec(400, "The request could not be accepted."),
    "contract_version_unsupported": ErrorSpec(
        426,
        "The requested contract version is not supported.",
    ),
    "desktop_authentication_unavailable": ErrorSpec(
        503,
        "Desktop authentication is temporarily unavailable.",
        True,
    ),
    "idempotency_key_conflict": ErrorSpec(
        409,
        "The idempotency key belongs to a different request.",
    ),
    "internal_error": ErrorSpec(
        500,
        "The request failed unexpectedly.",
    ),
    "invalid_desktop_session": ErrorSpec(
        401,
        "Desktop session authentication failed.",
    ),
    "invalid_event_pagination": ErrorSpec(
        422,
        "Event pagination parameters are invalid.",
    ),
    "invalid_json": ErrorSpec(400, "The WebSocket frame is not valid JSON."),
    "invalid_request_identifier": ErrorSpec(
        422,
        "A request identifier is invalid.",
    ),
    "invalid_subscription": ErrorSpec(
        422,
        "The task subscription is invalid.",
    ),
    "rate_limited": ErrorSpec(
        429,
        "The request rate limit was exceeded.",
        True,
    ),
    "request_rejected": ErrorSpec(400, "The request was rejected."),
    "request_validation_failed": ErrorSpec(
        422,
        "The request does not match the required contract.",
    ),
    "resource_not_found": ErrorSpec(404, "The requested resource was not found."),
    "service_unavailable": ErrorSpec(
        503,
        "The service is temporarily unavailable.",
        True,
    ),
    "state_conflict": ErrorSpec(409, "The request conflicts with current state."),
    "subscription_denied": ErrorSpec(
        404,
        "The task subscription is unavailable.",
    ),
    "subscription_limit": ErrorSpec(
        429,
        "The WebSocket subscription limit was reached.",
        True,
    ),
    "task_control_service_unavailable": ErrorSpec(
        503,
        "Task control is temporarily unavailable.",
        True,
    ),
    "task_event_query_service_unavailable": ErrorSpec(
        503,
        "Task event retrieval is temporarily unavailable.",
        True,
    ),
    "task_not_found": ErrorSpec(404, "Task was not found."),
    "task_query_service_unavailable": ErrorSpec(
        503,
        "Task retrieval is temporarily unavailable.",
        True,
    ),
    "task_service_unavailable": ErrorSpec(
        503,
        "Task creation is temporarily unavailable.",
        True,
    ),
    "unknown_frame": ErrorSpec(
        400,
        "The WebSocket frame type is not supported.",
    ),
}


DOMAIN_ERROR_CODES: tuple[tuple[type[BaseException], str], ...] = (
    (InvalidRequestIdentifierError, "invalid_request_identifier"),
    (IdempotencyConflictError, "idempotency_key_conflict"),
    (TaskNotFoundError, "task_not_found"),
    (InvalidPaginationError, "invalid_event_pagination"),
    (ApprovalNotFoundError, "approval_not_found"),
    (ApprovalExpiredError, "approval_expired"),
    (ApprovalConsumedError, "approval_consumed"),
    (ApprovalDigestMismatchError, "approval_digest_mismatch"),
)


def resolveCorrelationId(candidate: str | None = None) -> str:
    """Return a validated caller correlation ID or a fresh opaque identifier."""

    if candidate is not None:
        normalized = candidate.strip()
        if SAFE_CORRELATION_ID.fullmatch(normalized):
            return normalized
    return f"corr_{uuid4().hex}"


def _validation_details(error: RequestValidationError) -> dict[str, Any]:
    raw_issues = error.errors()
    issues: list[dict[str, Any]] = []
    for issue in raw_issues[:MAX_VALIDATION_ISSUES]:
        location = [
            part if isinstance(part, int) else str(part)[:64]
            for part in issue.get("loc", ())
        ]
        issue_type = str(issue.get("type", "validation_error"))
        if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,64}", issue_type):
            issue_type = "validation_error"
        issues.append({"location": location, "type": issue_type})
    return {
        "issues": issues,
        "truncated": len(raw_issues) > MAX_VALIDATION_ISSUES,
    }


def _http_fallback_code(status_code: int) -> str:
    return {
        400: "bad_request",
        404: "resource_not_found",
        409: "state_conflict",
        422: "request_validation_failed",
        429: "rate_limited",
        503: "service_unavailable",
    }.get(status_code, "request_rejected")


def _http_exception_code(error: HTTPException) -> str:
    detail = error.detail
    if isinstance(detail, dict):
        candidate = detail.get("code")
        if isinstance(candidate, str) and candidate in ERROR_SPECS:
            return candidate
    return _http_fallback_code(error.status_code)


def mapDomainErrors(
    error: BaseException,
    *,
    correlation_id: str | None = None,
) -> MappedDomainError:
    """Map a typed failure to an allowlisted, content-free public contract."""

    safe_correlation_id = resolveCorrelationId(correlation_id)
    details: dict[str, Any] = {}

    if isinstance(error, RequestValidationError):
        code = "request_validation_failed"
        details = _validation_details(error)
    elif isinstance(error, WebSocketProtocolError):
        code = error.code if error.code in ERROR_SPECS else "unknown_frame"
    elif isinstance(error, HTTPException):
        code = _http_exception_code(error)
    else:
        code = next(
            (
                mapped_code
                for exception_type, mapped_code in DOMAIN_ERROR_CODES
                if isinstance(error, exception_type)
            ),
            "internal_error",
        )

    spec = ERROR_SPECS[code]
    return MappedDomainError(
        status_code=spec.status_code,
        body=ErrorBody(
            code=code,
            message=spec.message,
            correlation_id=safe_correlation_id,
            retryable=spec.retryable,
            details=details,
        ),
    )


def webSocketErrorFrame(
    error: BaseException,
    *,
    correlation_id: str | None = None,
    protocol_version: str = "1.0",
) -> dict[str, Any]:
    """Build a stable WebSocket error frame from the shared mapping."""

    mapped = mapDomainErrors(error, correlation_id=correlation_id)
    return {
        "type": "error",
        "version": protocol_version,
        "payload": mapped.body.model_dump(mode="json"),
    }


def _request_correlation_id(request: Request) -> str:
    return resolveCorrelationId(request.headers.get("x-correlation-id"))


async def _domain_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    mapped = mapDomainErrors(
        error,
        correlation_id=_request_correlation_id(request),
    )
    headers = {"X-Correlation-Id": mapped.body.correlation_id}
    if (
        isinstance(error, HTTPException)
        and error.status_code == 401
        and error.headers is not None
        and error.headers.get("WWW-Authenticate") == "Bearer"
    ):
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse(
        status_code=mapped.status_code,
        content=mapped.http_envelope().model_dump(mode="json"),
        headers=headers,
    )


def installDomainErrorHandlers(app: FastAPI) -> None:
    """Install the shared mapping as the outer production API error boundary."""

    app.add_exception_handler(HTTPException, _domain_error_handler)
    app.add_exception_handler(RequestValidationError, _domain_error_handler)
    app.add_exception_handler(Exception, _domain_error_handler)
