from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

import pytest

from jarvis.graph import (
    CapabilityDefinition,
    CapabilityManifest,
    CapabilityParameter,
    ContextKind,
    ParameterKind,
    PlanContextBundle,
    PlanContextSummary,
    PlanResource,
    PlanValidationError,
    PlanValidationService,
    PlanValidationSettings,
    validatePlan,
)


TASK_ID = "tsk_" + "d" * 32
ACTOR_ID = "actor-001"
DEVICE_ID = "device-001"
REFS = ("pol_policy001", "cap_manifest01", "prj_project001")
RESOURCE_ID = "res_project001"
ACTION_INSPECT = "act_" + "1" * 24
ACTION_UPDATE = "act_" + "2" * 24
CRITERION_INSPECT = "crt_" + "3" * 24
CRITERION_UPDATE = "crt_" + "4" * 24


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def plan() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "objective": "modify_project",
        "assumptions": ["current_context"],
        "actions": [
            {
                "action_id": ACTION_INSPECT,
                "capability_id": "project.inspect",
                "capability_version": "1.0.0",
                "arguments": [
                    {"name": "project", "value": RESOURCE_ID},
                ],
                "dependencies": [],
                "timeout_seconds": 20,
            },
            {
                "action_id": ACTION_UPDATE,
                "capability_id": "project.update",
                "capability_version": "1.2.0",
                "arguments": [
                    {"name": "project", "value": RESOURCE_ID},
                    {"name": "mode", "value": "safe_fix"},
                ],
                "dependencies": [ACTION_INSPECT],
                "timeout_seconds": 90,
            },
        ],
        "success_criteria": [
            {
                "criterion_id": CRITERION_INSPECT,
                "action_id": ACTION_INSPECT,
                "verification_code": "inspection_recorded",
            },
            {
                "criterion_id": CRITERION_UPDATE,
                "action_id": ACTION_UPDATE,
                "verification_code": "tests_passed",
            },
        ],
        "warnings": ["state_may_change"],
    }


def state() -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "actor_id": ACTOR_ID,
        "device_id": DEVICE_ID,
        "context_refs": list(REFS),
        "plan": plan(),
        "status": "planning",
    }


def manifest() -> CapabilityManifest:
    return CapabilityManifest(
        reference_id=REFS[1],
        version="1.0.0",
        actor_id=ACTOR_ID,
        device_id=DEVICE_ID,
        capabilities=(
            CapabilityDefinition(
                capability_id="project.inspect",
                version="1.0.0",
                description="Inspect a registered project.",
                parameters=(
                    CapabilityParameter(
                        name="project",
                        kind=ParameterKind.RESOURCE,
                        resource_types=("project",),
                    ),
                ),
                verification_codes=("inspection_recorded",),
                max_timeout_seconds=30,
                reversible=True,
            ),
            CapabilityDefinition(
                capability_id="project.update",
                version="1.2.0",
                description="Apply a registered project update.",
                parameters=(
                    CapabilityParameter(
                        name="project",
                        kind=ParameterKind.RESOURCE,
                        resource_types=("project",),
                    ),
                    CapabilityParameter(
                        name="mode",
                        kind=ParameterKind.ENUM,
                        allowed_values=("safe_fix", "format_only"),
                    ),
                ),
                verification_codes=("change_observed", "tests_passed"),
                max_timeout_seconds=120,
                reversible=True,
            ),
        ),
    )


def bundle(
    *,
    selected_manifest: CapabilityManifest | None = None,
) -> PlanContextBundle:
    return PlanContextBundle(
        summaries=(
            PlanContextSummary(
                reference_id=REFS[0],
                kind=ContextKind.POLICY,
                summary="Policy snapshot.",
            ),
            PlanContextSummary(
                reference_id=REFS[1],
                kind=ContextKind.CAPABILITY,
                summary="Capability manifest.",
            ),
            PlanContextSummary(
                reference_id=REFS[2],
                kind=ContextKind.PROJECT,
                summary="Project context.",
            ),
        ),
        manifest=selected_manifest or manifest(),
        resources=(
            PlanResource(
                resource_id=RESOURCE_ID,
                resource_type="project",
                label="Selected project",
            ),
        ),
    )


class FakeResolver:
    def __init__(
        self,
        result: object | None = None,
        *,
        error: BaseException | None = None,
        delay: float = 0,
    ) -> None:
        self.result = bundle() if result is None else result
        self.error = error
        self.delay = delay
        self.calls: list[tuple[tuple[str, ...], str, str]] = []

    async def resolve_plan_context(
        self,
        reference_ids,
        *,
        actor_id: str,
        device_id: str,
    ):
        self.calls.append((reference_ids, actor_id, device_id))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.result


def service(
    *,
    resolver: FakeResolver | None = None,
    settings: PlanValidationSettings | None = None,
) -> PlanValidationService:
    return PlanValidationService(
        resolver=resolver or FakeResolver(),
        settings=settings or PlanValidationSettings(),
    )


async def assert_rejected(
    selected_state: dict[str, Any],
    code: str,
    *,
    selected_service: PlanValidationService | None = None,
) -> None:
    with pytest.raises(PlanValidationError) as captured:
        await validatePlan(
            selected_state,
            service=selected_service or service(),
        )
    assert captured.value.code == code


@pytest.mark.anyio
async def test_validates_and_returns_canonical_checkpoint_safe_plan() -> None:
    resolver = FakeResolver()

    result = await validatePlan(state(), service=service(resolver=resolver))

    assert result == {"plan": plan()}
    assert resolver.calls == [(REFS, ACTOR_ID, DEVICE_ID)]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("status", "executing", "plan_validation_state_invalid"),
        ("plan", None, "plan_validation_state_invalid"),
        ("task_id", "unsafe", "plan_validation_identity_invalid"),
        ("context_refs", [REFS[0], REFS[2]], "plan_validation_context_refs_invalid"),
    ],
)
async def test_rejects_invalid_state(
    field: str,
    value: object,
    code: str,
) -> None:
    invalid = state()
    invalid[field] = value

    await assert_rejected(invalid, code)


@pytest.mark.anyio
async def test_rejects_invalid_or_unknown_plan_schema() -> None:
    invalid = state()
    invalid["plan"]["schema_version"] = "2.0"
    await assert_rejected(invalid, "plan_schema_invalid")

    malformed = state()
    malformed["plan"]["private"] = "must-not-enter"
    await assert_rejected(malformed, "plan_schema_invalid")


@pytest.mark.anyio
async def test_rejects_unknown_capability_and_version() -> None:
    unknown = state()
    unknown["plan"]["actions"][0]["capability_id"] = "project.unknown"
    await assert_rejected(unknown, "plan_capability_unknown")

    wrong_version = state()
    wrong_version["plan"]["actions"][0]["capability_version"] = "9.0.0"
    await assert_rejected(wrong_version, "plan_capability_invalid")


@pytest.mark.anyio
async def test_rejects_invalid_arguments_and_unknown_resources() -> None:
    invalid_argument = state()
    invalid_argument["plan"]["actions"][1]["arguments"][1]["value"] = "unsafe"
    await assert_rejected(invalid_argument, "plan_argument_invalid")

    unknown_resource = state()
    unknown_resource["plan"]["actions"][0]["arguments"][0]["value"] = (
        "res_unknown001"
    )
    await assert_rejected(unknown_resource, "plan_resource_unknown")


@pytest.mark.anyio
async def test_rejects_duplicate_action_id_and_semantics() -> None:
    duplicate_id = state()
    duplicate_id["plan"]["actions"][1]["action_id"] = ACTION_INSPECT
    await assert_rejected(duplicate_id, "plan_action_duplicate")

    duplicate_semantics = state()
    copied = deepcopy(duplicate_semantics["plan"]["actions"][0])
    copied["action_id"] = "act_" + "5" * 24
    duplicate_semantics["plan"]["actions"].append(copied)
    duplicate_semantics["plan"]["success_criteria"].append(
        {
            "criterion_id": "crt_" + "6" * 24,
            "action_id": copied["action_id"],
            "verification_code": "inspection_recorded",
        }
    )
    await assert_rejected(duplicate_semantics, "plan_action_duplicate")


@pytest.mark.anyio
async def test_rejects_unknown_dependency_self_reference_and_cycle() -> None:
    unknown = state()
    unknown["plan"]["actions"][1]["dependencies"] = ["act_" + "9" * 24]
    await assert_rejected(unknown, "plan_dependency_invalid")

    self_reference = state()
    self_reference["plan"]["actions"][0]["dependencies"] = [ACTION_INSPECT]
    await assert_rejected(self_reference, "plan_dependency_invalid")

    duplicate = state()
    duplicate["plan"]["actions"][1]["dependencies"] = [
        ACTION_INSPECT,
        ACTION_INSPECT,
    ]
    await assert_rejected(duplicate, "plan_dependency_invalid")

    cyclic = state()
    cyclic["plan"]["actions"][0]["dependencies"] = [ACTION_UPDATE]
    await assert_rejected(cyclic, "plan_dependency_cycle")


@pytest.mark.anyio
async def test_rejects_aggregate_and_critical_path_budget_overflow() -> None:
    await assert_rejected(
        state(),
        "plan_budget_exceeded",
        selected_service=service(
            settings=PlanValidationSettings(
                max_total_timeout_seconds=100,
                max_critical_path_seconds=100,
            )
        ),
    )
    await assert_rejected(
        state(),
        "plan_budget_exceeded",
        selected_service=service(
            settings=PlanValidationSettings(
                max_total_timeout_seconds=200,
                max_critical_path_seconds=100,
            )
        ),
    )


@pytest.mark.anyio
async def test_rejects_invalid_verification_definitions() -> None:
    unknown = state()
    unknown["plan"]["success_criteria"][1]["verification_code"] = "invented"
    await assert_rejected(unknown, "plan_verification_invalid")

    missing = state()
    missing["plan"]["success_criteria"].pop()
    await assert_rejected(missing, "plan_verification_invalid")

    duplicate = state()
    duplicate["plan"]["success_criteria"][1]["criterion_id"] = (
        CRITERION_INSPECT
    )
    await assert_rejected(duplicate, "plan_action_duplicate")

    duplicate_pair = state()
    duplicate_pair["plan"]["success_criteria"].append(
        {
            "criterion_id": "crt_" + "7" * 24,
            "action_id": ACTION_UPDATE,
            "verification_code": "tests_passed",
        }
    )
    await assert_rejected(
        duplicate_pair,
        "plan_verification_invalid",
    )


@pytest.mark.anyio
async def test_rejects_mismatched_context_and_resolver_failures() -> None:
    mismatched_manifest = manifest().model_copy(
        update={"actor_id": "actor-002"}
    )
    await assert_rejected(
        state(),
        "plan_validation_context_invalid",
        selected_service=service(
            resolver=FakeResolver(
                bundle(selected_manifest=mismatched_manifest)
            )
        ),
    )
    await assert_rejected(
        state(),
        "plan_validation_context_unavailable",
        selected_service=service(
            resolver=FakeResolver(error=RuntimeError("private"))
        ),
    )
    await assert_rejected(
        state(),
        "plan_validation_context_unavailable",
        selected_service=service(
            resolver=FakeResolver(delay=0.05),
            settings=PlanValidationSettings(
                resolver_timeout_seconds=0.001
            ),
        ),
    )


@pytest.mark.anyio
async def test_propagates_cancellation() -> None:
    with pytest.raises(asyncio.CancelledError):
        await validatePlan(
            state(),
            service=service(
                resolver=FakeResolver(error=asyncio.CancelledError())
            ),
        )


@pytest.mark.anyio
async def test_rejects_incompatible_validation_settings_before_resolution() -> None:
    resolver = FakeResolver()

    await assert_rejected(
        state(),
        "plan_validation_settings_incompatible",
        selected_service=service(
            resolver=resolver,
            settings=PlanValidationSettings(max_actions=9),
        ),
    )

    assert resolver.calls == []
