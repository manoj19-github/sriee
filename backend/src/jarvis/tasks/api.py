"""FastAPI task creation endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from jarvis.security.desktop_auth import (
    AuthenticatedPrincipal,
    authenticateDesktopSession,
)
from jarvis.tasks.models import CreateTaskRequest, CreateTaskResponse
from jarvis.tasks.repository import IdempotencyConflictError
from jarvis.tasks.service import (
    InvalidRequestIdentifierError,
    TaskCreationService,
)


router = APIRouter(prefix="/api/v1", tags=["tasks"])


def get_task_creation_service(request: Request) -> TaskCreationService:
    service = getattr(request.app.state, "task_creation_service", None)
    if not isinstance(service, TaskCreationService):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "task_service_unavailable"},
        )
    return service


@router.post(
    "/tasks",
    response_model=CreateTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def createTask(
    payload: CreateTaskRequest,
    principal: Annotated[
        AuthenticatedPrincipal,
        Depends(authenticateDesktopSession),
    ],
    service: Annotated[
        TaskCreationService,
        Depends(get_task_creation_service),
    ],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    x_correlation_id: Annotated[str, Header(alias="X-Correlation-Id")],
) -> CreateTaskResponse:
    """Validate, atomically persist, and schedule one authenticated task."""

    try:
        outcome = await service.create(
            request=payload,
            principal=principal,
            idempotency_key=idempotency_key,
            correlation_id=x_correlation_id,
        )
    except InvalidRequestIdentifierError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_request_identifier"},
        ) from None
    except IdempotencyConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "idempotency_key_conflict"},
        ) from None

    return CreateTaskResponse(
        task_id=outcome.task.task_id,
        status=outcome.task.status,
        created=outcome.created,
        event_sequence=outcome.event.sequence,
        accepted_at=outcome.task.created_at,
    )
