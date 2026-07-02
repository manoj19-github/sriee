from __future__ import annotations

import asyncio
import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from packaging.version import Version

from jarvis.security.desktop_auth import (
    AuthenticatedPrincipal,
    ContractRange,
    authenticateDesktopSession,
)
from jarvis.tasks.api import router
from jarvis.tasks.models import (
    ApprovalRecord,
    ApprovalStatus,
    CreateTaskRequest,
    TaskInput,
    TaskInputType,
    TaskStatus,
)
from jarvis.tasks.repository import InMemoryTaskRepository
from jarvis.tasks.service import (
    InMemoryOutboxNotifier,
    TaskControlService,
    TaskCreationService,
)


NOW = datetime.now(UTC)
DIGEST = hashlib.sha256(b"approved action").hexdigest()
APPROVAL_ID = "apr_approval0001"
CORRELATION_ID = "corr-control-0001"


def principal(
    *,
    actor_id: str = "actor-001",
    device_id: str = "device-001",
) -> AuthenticatedPrincipal:
    contracts = ContractRange.parse("1.0.0", "1.5.0")
    return AuthenticatedPrincipal(
        actor_id=actor_id,
        device_id=device_id,
        session_id="session-001",
        token_id="token-001",
        contract_version=Version("1.2.0"),
        contract_range=contracts,
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )


def seed_task(repository: InMemoryTaskRepository) -> str:
    service = TaskCreationService(
        repository,
        InMemoryOutboxNotifier(),
        clock=lambda: NOW,
    )

    async def create() -> str:
        outcome = await service.create(
            request=CreateTaskRequest(
                input=TaskInput(type=TaskInputType.TEXT, content="Cancel me")
            ),
            principal=principal(),
            idempotency_key="idem-control-0001",
            correlation_id=CORRELATION_ID,
        )
        return outcome.task.task_id

    return asyncio.run(create())


def seed_approval(
    repository: InMemoryTaskRepository,
    task_id: str,
    *,
    expires_at: datetime = NOW + timedelta(minutes=5),
) -> None:
    asyncio.run(
        repository.put_pending_approval_for_test(
            ApprovalRecord(
                approval_id=APPROVAL_ID,
                task_id=task_id,
                actor_id="actor-001",
                device_id="device-001",
                action_id="act_action000001",
                action_digest=DIGEST,
                status=ApprovalStatus.PENDING,
                expires_at=expires_at,
            )
        )
    )


def application(
    repository: InMemoryTaskRepository,
    notifier: InMemoryOutboxNotifier,
    request_principal: AuthenticatedPrincipal | None,
    *,
    configure_service: bool = True,
) -> FastAPI:
    app = FastAPI()
    if configure_service:
        app.state.task_control_service = TaskControlService(
            repository,
            notifier,
            clock=lambda: NOW,
        )
    if request_principal is not None:
        app.dependency_overrides[authenticateDesktopSession] = (
            lambda: request_principal
        )
    app.include_router(router)
    return app


def test_cancellation_is_persisted_signalled_and_idempotent() -> None:
    repository = InMemoryTaskRepository()
    notifier = InMemoryOutboxNotifier()
    task_id = seed_task(repository)

    with TestClient(application(repository, notifier, principal())) as client:
        first = client.post(
            f"/api/v1/tasks/{task_id}/cancel",
            headers={"X-Correlation-Id": CORRELATION_ID},
        )
        replay = client.post(
            f"/api/v1/tasks/{task_id}/cancel",
            headers={"X-Correlation-Id": "corr-control-0002"},
        )

    tasks, events, outbox = asyncio.run(repository.snapshot())
    projection = asyncio.run(repository.get_projection(task_id))
    assert first.status_code == replay.status_code == 202
    assert first.json()["status"] == "cancellation_requested"
    assert first.json()["created"] is True
    assert first.json()["event_sequence"] == 2
    assert replay.json()["created"] is False
    assert len(tasks) == 1
    assert [event.event_type for event in events] == [
        "task.created",
        "task.cancellation_requested",
    ]
    assert len(outbox) == 2
    assert notifier.task_ids == [task_id]
    assert projection is not None
    assert projection.status is TaskStatus.CANCELLATION_REQUESTED


def test_terminal_task_remains_terminal_without_new_intent() -> None:
    repository = InMemoryTaskRepository()
    notifier = InMemoryOutboxNotifier()
    task_id = seed_task(repository)

    async def make_terminal() -> None:
        projection = await repository.get_projection(task_id)
        assert projection is not None
        await repository.replace_projection(
            replace(projection, status=TaskStatus.SUCCEEDED)
        )

    asyncio.run(make_terminal())
    with TestClient(application(repository, notifier, principal())) as client:
        response = client.post(
            f"/api/v1/tasks/{task_id}/cancel",
            headers={"X-Correlation-Id": CORRELATION_ID},
        )

    _, events, outbox = asyncio.run(repository.snapshot())
    assert response.status_code == 202
    assert response.json()["status"] == "succeeded"
    assert response.json()["cancellation_requested"] is False
    assert response.json()["event_sequence"] is None
    assert len(events) == len(outbox) == 1
    assert notifier.task_ids == []


def test_cancellation_notifier_failure_keeps_durable_intent() -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)

    with TestClient(
        application(
            repository,
            InMemoryOutboxNotifier(fail=True),
            principal(),
        )
    ) as client:
        response = client.post(
            f"/api/v1/tasks/{task_id}/cancel",
            headers={"X-Correlation-Id": CORRELATION_ID},
        )

    _, events, outbox = asyncio.run(repository.snapshot())
    assert response.status_code == 202
    assert events[-1].event_type == "task.cancellation_requested"
    assert outbox[-1].event_type == "graph.task.cancel.requested"


@pytest.mark.parametrize(
    "request_principal",
    [
        principal(actor_id="actor-002"),
        principal(device_id="device-002"),
    ],
)
def test_unauthorized_cancellation_is_not_found(
    request_principal: AuthenticatedPrincipal,
) -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)

    with TestClient(
        application(repository, InMemoryOutboxNotifier(), request_principal)
    ) as client:
        response = client.post(
            f"/api/v1/tasks/{task_id}/cancel",
            headers={"X-Correlation-Id": CORRELATION_ID},
        )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "task_not_found"


@pytest.mark.parametrize("decision", ["approve", "deny"])
def test_valid_approval_decision_is_consumed_and_forwarded(decision: str) -> None:
    repository = InMemoryTaskRepository()
    notifier = InMemoryOutboxNotifier()
    task_id = seed_task(repository)
    seed_approval(repository, task_id)

    with TestClient(application(repository, notifier, principal())) as client:
        response = client.post(
            f"/api/v1/approvals/{APPROVAL_ID}/decision",
            json={"decision": decision, "action_digest": DIGEST},
            headers={"X-Correlation-Id": CORRELATION_ID},
        )

    projection = asyncio.run(repository.get_projection(task_id))
    _, events, outbox = asyncio.run(repository.snapshot())
    assert response.status_code == 200
    assert response.json()["decision"] == decision
    assert response.json()["event_sequence"] == 2
    assert events[-1].event_type == "approval.decided"
    assert outbox[-1].event_type == "graph.approval.decided"
    assert notifier.task_ids == [task_id]
    assert projection is not None
    assert projection.pending_approval is None
    assert projection.status is (
        TaskStatus.EXECUTING if decision == "approve" else TaskStatus.DENIED
    )


def test_digest_mismatch_does_not_consume_approval() -> None:
    repository = InMemoryTaskRepository()
    notifier = InMemoryOutboxNotifier()
    task_id = seed_task(repository)
    seed_approval(repository, task_id)

    with TestClient(application(repository, notifier, principal())) as client:
        mismatch = client.post(
            f"/api/v1/approvals/{APPROVAL_ID}/decision",
            json={"decision": "approve", "action_digest": "0" * 64},
            headers={"X-Correlation-Id": CORRELATION_ID},
        )
        accepted = client.post(
            f"/api/v1/approvals/{APPROVAL_ID}/decision",
            json={"decision": "approve", "action_digest": DIGEST},
            headers={"X-Correlation-Id": CORRELATION_ID},
        )

    assert mismatch.status_code == 409
    assert mismatch.json()["detail"]["code"] == "approval_digest_mismatch"
    assert accepted.status_code == 200


def test_expired_and_consumed_approvals_are_rejected() -> None:
    expired_repository = InMemoryTaskRepository()
    expired_task = seed_task(expired_repository)
    seed_approval(
        expired_repository,
        expired_task,
        expires_at=NOW - timedelta(seconds=1),
    )
    with TestClient(
        application(
            expired_repository,
            InMemoryOutboxNotifier(),
            principal(),
        )
    ) as client:
        expired = client.post(
            f"/api/v1/approvals/{APPROVAL_ID}/decision",
            json={"decision": "approve", "action_digest": DIGEST},
            headers={"X-Correlation-Id": CORRELATION_ID},
        )
    assert expired.status_code == 409
    assert expired.json()["detail"]["code"] == "approval_expired"

    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)
    seed_approval(repository, task_id)
    with TestClient(
        application(repository, InMemoryOutboxNotifier(), principal())
    ) as client:
        first = client.post(
            f"/api/v1/approvals/{APPROVAL_ID}/decision",
            json={"decision": "deny", "action_digest": DIGEST},
            headers={"X-Correlation-Id": CORRELATION_ID},
        )
        consumed = client.post(
            f"/api/v1/approvals/{APPROVAL_ID}/decision",
            json={"decision": "deny", "action_digest": DIGEST},
            headers={"X-Correlation-Id": CORRELATION_ID},
        )
    assert first.status_code == 200
    assert consumed.status_code == 409
    assert consumed.json()["detail"]["code"] == "approval_consumed"


def test_unknown_or_unauthorized_approval_is_not_found() -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)
    seed_approval(repository, task_id)

    with TestClient(
        application(
            repository,
            InMemoryOutboxNotifier(),
            principal(actor_id="actor-002"),
        )
    ) as client:
        unauthorized = client.post(
            f"/api/v1/approvals/{APPROVAL_ID}/decision",
            json={"decision": "approve", "action_digest": DIGEST},
            headers={"X-Correlation-Id": CORRELATION_ID},
        )
        unknown = client.post(
            "/api/v1/approvals/apr_unknown00001/decision",
            json={"decision": "approve", "action_digest": DIGEST},
            headers={"X-Correlation-Id": CORRELATION_ID},
        )
    assert unauthorized.status_code == unknown.status_code == 404
    assert unauthorized.json()["detail"]["code"] == "approval_not_found"


@pytest.mark.parametrize(
    "body",
    [
        {"decision": "invalid", "action_digest": DIGEST},
        {"decision": "approve", "action_digest": "short"},
        {"decision": "approve", "action_digest": DIGEST, "extra": True},
    ],
)
def test_invalid_approval_body_returns_validation_error(
    body: dict[str, object],
) -> None:
    repository = InMemoryTaskRepository()
    task_id = seed_task(repository)
    seed_approval(repository, task_id)

    with TestClient(
        application(repository, InMemoryOutboxNotifier(), principal())
    ) as client:
        response = client.post(
            f"/api/v1/approvals/{APPROVAL_ID}/decision",
            json=body,
            headers={"X-Correlation-Id": CORRELATION_ID},
        )
    assert response.status_code == 422
