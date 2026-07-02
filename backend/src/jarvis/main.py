"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import FastAPI

from jarvis.config.settings import Settings
from jarvis.health import HealthReporter
from jarvis.health import router as health_router
from jarvis.runtime.lifecycle import (
    ApplicationRuntime,
    ResourceSpec,
    manageApplicationLifespan,
)
from jarvis.security.desktop_auth import DesktopSessionAuthenticator
from jarvis.tasks.api import router as task_router
from jarvis.tasks.service import (
    TaskCreationService,
    TaskEventQueryService,
    TaskControlService,
    TaskQueryService,
)
from jarvis.websocket.session import (
    WebSocketSessionService,
    router as websocket_router,
)


def create_application(
    settings: Settings,
    resource_specs: Sequence[ResourceSpec],
    *,
    worker_drain_timeout_seconds: float = 30.0,
    desktop_authenticator: DesktopSessionAuthenticator | None = None,
    task_creation_service: TaskCreationService | None = None,
    task_query_service: TaskQueryService | None = None,
    task_event_query_service: TaskEventQueryService | None = None,
    task_control_service: TaskControlService | None = None,
    websocket_session_service: WebSocketSessionService | None = None,
) -> FastAPI:
    """Create an application with an explicit, testable runtime."""

    runtime = ApplicationRuntime(
        settings=settings,
        resource_specs=resource_specs,
        worker_drain_timeout_seconds=worker_drain_timeout_seconds,
    )
    app = FastAPI(
        title="JARVIS OS API",
        lifespan=manageApplicationLifespan,
    )
    app.state.runtime = runtime
    app.state.health_reporter = HealthReporter(runtime)
    if desktop_authenticator is not None:
        app.state.desktop_authenticator = desktop_authenticator
    if task_creation_service is not None:
        app.state.task_creation_service = task_creation_service
    if task_query_service is not None:
        app.state.task_query_service = task_query_service
    if task_event_query_service is not None:
        app.state.task_event_query_service = task_event_query_service
    if task_control_service is not None:
        app.state.task_control_service = task_control_service
    if websocket_session_service is not None:
        app.state.websocket_session_service = websocket_session_service
    app.include_router(health_router)
    app.include_router(task_router)
    app.include_router(websocket_router)
    return app
