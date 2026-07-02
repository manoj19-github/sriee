from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field

from jarvis.errors import (
    WebSocketProtocolError,
    installDomainErrorHandlers,
    mapDomainErrors,
    webSocketErrorFrame,
)
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


CORRELATION_ID = "corr-error-test-0001"
SECRET_MARKER = "secret-value-must-not-escape"
INVALID_CORRELATION_ID = "unsafe correlation/identifier"


class ValidationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=1)


def application() -> FastAPI:
    app = FastAPI()
    installDomainErrorHandlers(app)

    @app.get("/unavailable")
    async def unavailable() -> None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "task_service_unavailable",
                "unsafe": SECRET_MARKER,
            },
        )

    @app.post("/validate")
    async def validate(payload: ValidationPayload) -> ValidationPayload:
        return payload

    @app.get("/unauthorized")
    async def unauthorized() -> None:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_desktop_session"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.get("/unexpected")
    async def unexpected() -> None:
        raise RuntimeError(SECRET_MARKER)

    return app


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (InvalidRequestIdentifierError(), 422, "invalid_request_identifier"),
        (IdempotencyConflictError(), 409, "idempotency_key_conflict"),
        (TaskNotFoundError(), 404, "task_not_found"),
        (InvalidPaginationError(), 422, "invalid_event_pagination"),
        (ApprovalNotFoundError(), 404, "approval_not_found"),
        (ApprovalExpiredError(), 409, "approval_expired"),
        (ApprovalConsumedError(), 409, "approval_consumed"),
        (ApprovalDigestMismatchError(), 409, "approval_digest_mismatch"),
    ],
)
def test_maps_typed_domain_errors_to_stable_codes(
    error: BaseException,
    status_code: int,
    code: str,
) -> None:
    mapped = mapDomainErrors(error, correlation_id=CORRELATION_ID)

    assert mapped.status_code == status_code
    assert mapped.body.code == code
    assert mapped.body.correlation_id == CORRELATION_ID
    assert mapped.body.retryable is False
    assert mapped.body.details == {}


def test_http_error_envelope_has_correlation_and_retryability() -> None:
    with TestClient(application()) as client:
        response = client.get(
            "/unavailable",
            headers={"X-Correlation-Id": CORRELATION_ID},
        )

    assert response.status_code == 503
    assert response.headers["X-Correlation-Id"] == CORRELATION_ID
    assert response.json() == {
        "error": {
            "code": "task_service_unavailable",
            "message": "Task creation is temporarily unavailable.",
            "correlation_id": CORRELATION_ID,
            "retryable": True,
            "details": {},
        }
    }
    assert SECRET_MARKER not in response.text


def test_authentication_challenge_is_preserved_without_unsafe_headers() -> None:
    with TestClient(application()) as client:
        response = client.get(
            "/unauthorized",
            headers={"X-Correlation-Id": CORRELATION_ID},
        )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "invalid_desktop_session"


def test_validation_error_omits_rejected_values_and_messages() -> None:
    with TestClient(application()) as client:
        response = client.post(
            "/validate",
            json={"count": SECRET_MARKER, "private": SECRET_MARKER},
            headers={"X-Correlation-Id": CORRELATION_ID},
        )

    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "request_validation_failed"
    assert body["correlation_id"] == CORRELATION_ID
    assert body["retryable"] is False
    assert body["details"]["truncated"] is False
    assert body["details"]["issues"] == [
        {"location": ["body", "count"], "type": "int_parsing"},
        {"location": ["body", "private"], "type": "extra_forbidden"},
    ]
    assert SECRET_MARKER not in response.text


def test_unexpected_exception_and_invalid_correlation_fail_safely() -> None:
    with TestClient(
        application(),
        raise_server_exceptions=False,
    ) as client:
        response = client.get(
            "/unexpected",
            headers={"X-Correlation-Id": INVALID_CORRELATION_ID},
        )

    body = response.json()["error"]
    assert response.status_code == 500
    assert body["code"] == "internal_error"
    assert body["retryable"] is False
    assert body["correlation_id"].startswith("corr_")
    assert body["correlation_id"] != INVALID_CORRELATION_ID
    assert response.headers["X-Correlation-Id"] == body["correlation_id"]
    assert SECRET_MARKER not in response.text
    assert INVALID_CORRELATION_ID not in response.text


def test_websocket_errors_use_the_same_public_contract() -> None:
    frame = webSocketErrorFrame(
        WebSocketProtocolError("subscription_limit"),
        correlation_id=CORRELATION_ID,
    )

    assert frame == {
        "type": "error",
        "version": "1.0",
        "payload": {
            "code": "subscription_limit",
            "message": "The WebSocket subscription limit was reached.",
            "correlation_id": CORRELATION_ID,
            "retryable": True,
            "details": {},
        },
    }


def test_unknown_websocket_error_code_is_not_reflected() -> None:
    frame = webSocketErrorFrame(
        WebSocketProtocolError(SECRET_MARKER),
        correlation_id=CORRELATION_ID,
    )

    assert frame["payload"]["code"] == "unknown_frame"
    assert SECRET_MARKER not in str(frame)
