"""Unauthenticated but secret-safe process health endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from jarvis.health.service import HealthProbe, HealthReporter, reportHealth


router = APIRouter(prefix="/health", tags=["health"])


class LivenessResponse(BaseModel):
    """Minimal process-liveness response."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["live"]
    state: str


class DependencyStatusResponse(BaseModel):
    """Sanitized status for one fixed-name dependency."""

    model_config = ConfigDict(extra="forbid")

    ready: bool
    code: str


class ReadinessResponse(BaseModel):
    """Dependency readiness response without sensitive diagnostics."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "not_ready"]
    state: str
    accepting_work: bool
    dependencies: dict[str, DependencyStatusResponse]
    failure_code: str | None = None


def _get_reporter(request: Request) -> HealthReporter | None:
    reporter = getattr(request.app.state, "health_reporter", None)
    return reporter if isinstance(reporter, HealthReporter) else None


@router.get("/live", response_model=LivenessResponse)
async def report_liveness(request: Request) -> LivenessResponse:
    """Return 200 when the HTTP process can serve a bounded response."""

    reporter = _get_reporter(request)
    if reporter is None:
        return LivenessResponse(status="live", state="unavailable")

    report = await reportHealth(reporter, HealthProbe.LIVENESS)
    return LivenessResponse(status="live", state=report.state.value)


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def report_readiness(request: Request):
    """Return current dependency readiness, using 503 when degraded."""

    reporter = _get_reporter(request)
    if reporter is None:
        response = ReadinessResponse(
            status="not_ready",
            state="unavailable",
            accepting_work=False,
            dependencies={},
            failure_code="runtime_unavailable",
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=response.model_dump(mode="json"),
        )

    report = await reportHealth(reporter, HealthProbe.READINESS)
    response = ReadinessResponse(
        status="ready" if report.healthy else "not_ready",
        state=report.state.value,
        accepting_work=report.accepting_work,
        dependencies={
            name: DependencyStatusResponse(
                ready=dependency.ready,
                code=dependency.code,
            )
            for name, dependency in report.dependencies.items()
        },
        failure_code=report.failure_code,
    )
    return JSONResponse(
        status_code=(
            status.HTTP_200_OK
            if report.healthy
            else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content=response.model_dump(mode="json"),
    )
