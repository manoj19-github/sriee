"""FastAPI task creation endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)

from jarvis.security.desktop_auth import (
    AuthenticatedPrincipal,
    authenticateDesktopSession,
)
from jarvis.tasks.models import (
    ArtifactReferenceResponse,
    CreateTaskRequest,
    CreateTaskResponse,
    PendingApprovalResponse,
    PlanSnapshotResponse,
    TaskResultResponse,
    TaskEventPageResponse,
    TaskEventResponse,
    TaskSnapshotResponse,
)
from jarvis.tasks.repository import IdempotencyConflictError
from jarvis.tasks.service import (
    InvalidRequestIdentifierError,
    InvalidPaginationError,
    TaskCreationService,
    TaskEventQueryService,
    TaskNotFoundError,
    TaskQueryService,
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


def get_task_query_service(request: Request) -> TaskQueryService:
    service = getattr(request.app.state, "task_query_service", None)
    if not isinstance(service, TaskQueryService):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "task_query_service_unavailable"},
        )
    return service


def get_task_event_query_service(request: Request) -> TaskEventQueryService:
    service = getattr(request.app.state, "task_event_query_service", None)
    if not isinstance(service, TaskEventQueryService):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "task_event_query_service_unavailable"},
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


@router.get(
    "/tasks/{task_id}",
    response_model=TaskSnapshotResponse,
)
async def getTask(
    task_id: str,
    principal: Annotated[
        AuthenticatedPrincipal,
        Depends(authenticateDesktopSession),
    ],
    service: Annotated[
        TaskQueryService,
        Depends(get_task_query_service),
    ],
) -> TaskSnapshotResponse:
    """Return a minimal authorized projection without personal artifact data."""

    try:
        projection = await service.get(task_id=task_id, principal=principal)
    except TaskNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "task_not_found"},
        ) from None

    plan = (
        PlanSnapshotResponse(
            revision=projection.plan.revision,
            status=projection.plan.status,
        )
        if projection.plan is not None
        else None
    )
    pending_approval = (
        PendingApprovalResponse(
            approval_id=projection.pending_approval.approval_id,
            action_id=projection.pending_approval.action_id,
            risk_tier=projection.pending_approval.risk_tier,
            expires_at=projection.pending_approval.expires_at,
        )
        if projection.pending_approval is not None
        else None
    )
    result = (
        TaskResultResponse(
            outcome=projection.result.outcome,
            summary=projection.result.summary,
            artifact_references=tuple(
                ArtifactReferenceResponse(reference_id=reference_id)
                for reference_id in projection.result.artifact_reference_ids
            ),
        )
        if projection.result is not None
        else None
    )
    return TaskSnapshotResponse(
        task_id=projection.task_id,
        status=projection.status,
        plan=plan,
        pending_approval=pending_approval,
        result=result,
        created_at=projection.created_at,
        updated_at=projection.updated_at,
    )


@router.get(
    "/tasks/{task_id}/events",
    response_model=TaskEventPageResponse,
)
async def listTaskEvents(
    task_id: str,
    principal: Annotated[
        AuthenticatedPrincipal,
        Depends(authenticateDesktopSession),
    ],
    service: Annotated[
        TaskEventQueryService,
        Depends(get_task_event_query_service),
    ],
    after_sequence: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> TaskEventPageResponse:
    """Return an exclusive-cursor page for durable event replay."""

    try:
        page = await service.list(
            task_id=task_id,
            principal=principal,
            after_sequence=after_sequence,
            limit=limit,
        )
    except TaskNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "task_not_found"},
        ) from None
    except InvalidPaginationError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_event_pagination"},
        ) from None

    return TaskEventPageResponse(
        task_id=page.task_id,
        events=tuple(
            TaskEventResponse(
                event_id=event.event_id,
                task_id=event.task_id,
                sequence=event.sequence,
                type=event.event_type,
                schema_version=event.schema_version,
                occurred_at=event.occurred_at,
                correlation_id=event.correlation_id,
                data=dict(event.data),
            )
            for event in page.events
        ),
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )
