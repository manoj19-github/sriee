"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import FastAPI

from jarvis.config.settings import Settings
from jarvis.runtime.lifecycle import (
    ApplicationRuntime,
    ResourceSpec,
    manageApplicationLifespan,
)
from jarvis.security.desktop_auth import DesktopSessionAuthenticator


def create_application(
    settings: Settings,
    resource_specs: Sequence[ResourceSpec],
    *,
    worker_drain_timeout_seconds: float = 30.0,
    desktop_authenticator: DesktopSessionAuthenticator | None = None,
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
    if desktop_authenticator is not None:
        app.state.desktop_authenticator = desktop_authenticator
    return app
