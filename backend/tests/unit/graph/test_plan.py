from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from jarvis.graph import (
    CapabilityDefinition,
    CapabilityManifest,
    CapabilityParameter,
    ContextKind,
    ModelPlanDraft,
    ParameterKind,
    PlanContextBundle,
    PlanContextSummary,
    PlanDraftError,
    PlanDraftService,
    PlanDraftSettings,
    PlanResource,
    createPlanDraft,
)
from jarvis.providers.ollama import OllamaChatResponse, OllamaProviderError


TASK_ID = "tsk_" + "c" * 32
ACTOR_ID = "actor-001"
DEVICE_ID = "device-001"
REFS = ("pol_policy001", "cap_manifest01", "prj_project001")
PROJECT_RESOURCE = "res_project001"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def state() -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "actor_id": ACTOR_ID,
        "device_id": DEVICE_ID,
        "context_refs": list(REFS),
        "intent": {
            "name": "modify_project",
            "confidence": 0.95,
            "scope": {
                "target": "project",
                "context_refs": [REFS[2]],
            },
            "ambiguities": [],
            "consequential": True,
            "needs_clarification": False,
        },
        "plan": None,
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
                description="Inspect the registered project without changing it.",
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
                description="Apply a registered project update mode.",
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
                    CapabilityParameter(
                        name="attempts",
                        kind=ParameterKind.INTEGER,
                        required=False,
                        minimum=1,
                        maximum=3,
                    ),
                ),
                verification_codes=("change_observed", "tests_passed"),
                max_timeout_seconds=120,
                reversible=True,
            ),
            CapabilityDefinition(
                capability_id="tests.run",
                version="2.0.0",
                description="Run a registered test suite for the project.",
                parameters=(
                    CapabilityParameter(
                        name="project",
                        kind=ParameterKind.RESOURCE,
                        resource_types=("project",),
                    ),
                    CapabilityParameter(
                        name="suite",
                        kind=ParameterKind.IDENTIFIER,
                    ),
                    CapabilityParameter(
                        name="fail_fast",
                        kind=ParameterKind.BOOLEAN,
                    ),
                ),
                verification_codes=("tests_passed",),
                max_timeout_seconds=300,
                reversible=True,
            ),
        ),
    )


def bundle() -> PlanContextBundle:
    return PlanContextBundle(
        summaries=(
            PlanContextSummary(
                reference_id=REFS[0],
                kind=ContextKind.POLICY,
                summary="The current policy reference is available.",
            ),
            PlanContextSummary(
                reference_id=REFS[1],
                kind=ContextKind.CAPABILITY,
                summary="The current capability manifest is available.",
            ),
            PlanContextSummary(
                reference_id=REFS[2],
                kind=ContextKind.PROJECT,
                summary="The selected project needs a safe fix and tests.",
            ),
        ),
        manifest=manifest(),
        resources=(
            PlanResource(
                resource_id=PROJECT_RESOURCE,
                resource_type="project",
                label="Selected project",
            ),
        ),
    )


def valid_payload() -> dict[str, Any]:
    return {
        "objective": "modify_project",
        "assumptions": ["current_context"],
        "actions": [
            {
                "step_id": "step_inspect",
                "capability_id": "project.inspect",
                "capability_version": "1.0.0",
                "arguments": [
                    {"name": "project", "value": PROJECT_RESOURCE}
                ],
                "depends_on": [],
                "timeout_seconds": 20,
            },
            {
                "step_id": "step_update",
                "capability_id": "project.update",
                "capability_version": "1.2.0",
                "arguments": [
                    {"name": "project", "value": PROJECT_RESOURCE},
                    {"name": "mode", "value": "safe_fix"},
                    {"name": "attempts", "value": 2},
                ],
                "depends_on": ["step_inspect"],
                "timeout_seconds": 90,
            },
        ],
        "success_criteria": [
            {
                "step_id": "step_inspect",
                "verification_code": "inspection_recorded",
            },
            {
                "step_id": "step_update",
                "verification_code": "change_observed",
            },
            {
                "step_id": "step_update",
                "verification_code": "tests_passed",
            },
        ],
        "warnings": ["state_may_change"],
    }


def response(
    payload: dict[str, Any] | str | None = None,
    *,
    structured: bool = True,
) -> OllamaChatResponse:
    content = (
        json.dumps(valid_payload())
        if payload is None
        else payload
        if isinstance(payload, str)
        else json.dumps(payload)
    )
    return OllamaChatResponse(
        model="qwen3:4b-instruct",
        content=content,
        prompt_tokens=100,
        output_tokens=50,
        total_duration_ns=100,
        structured=structured,
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


class FakeGateway:
    def __init__(self, results: list[object] | None = None) -> None:
        self.results = results or [response()]
        self.requests = []

    async def chat(self, request):
        self.requests.append(request)
        result = self.results[len(self.requests) - 1]
        if isinstance(result, BaseException):
            raise result
        return result


def service(
    *,
    gateway: FakeGateway | None = None,
    resolver: FakeResolver | None = None,
    settings: PlanDraftSettings | None = None,
) -> PlanDraftService:
    return PlanDraftService(
        gateway=gateway or FakeGateway(),
        resolver=resolver or FakeResolver(),
        settings=settings or PlanDraftSettings(),
    )


@pytest.mark.anyio
async def test_creates_typed_dependency_aware_plan_with_stable_ids() -> None:
    gateway = FakeGateway()
    resolver = FakeResolver()

    first = await createPlanDraft(
        state(),
        service=service(gateway=gateway, resolver=resolver),
    )
    second = await createPlanDraft(state(), service=service())

    assert first == second
    plan = first["plan"]
    assert plan["schema_version"] == "1.0"
    assert plan["objective"] == "modify_project"
    assert len(plan["actions"]) == 2
    assert plan["actions"][0]["action_id"].startswith("act_")
    assert plan["actions"][1]["dependencies"] == [
        plan["actions"][0]["action_id"]
    ]
    assert all(
        criterion["criterion_id"].startswith("crt_")
        for criterion in plan["success_criteria"]
    )
    assert resolver.calls == [(REFS, ACTOR_ID, DEVICE_ID)]
    assert len(gateway.requests) == 1


@pytest.mark.anyio
async def test_stable_ids_do_not_depend_on_model_step_labels() -> None:
    renamed = valid_payload()
    renamed["actions"][0]["step_id"] = "step_one"
    renamed["actions"][1]["step_id"] = "step_two"
    renamed["actions"][1]["depends_on"] = ["step_one"]
    renamed["success_criteria"][0]["step_id"] = "step_one"
    renamed["success_criteria"][1]["step_id"] = "step_two"
    renamed["success_criteria"][2]["step_id"] = "step_two"

    original = await createPlanDraft(state(), service=service())
    alternate = await createPlanDraft(
        state(),
        service=service(gateway=FakeGateway([response(renamed)])),
    )

    assert [
        item["action_id"] for item in original["plan"]["actions"]
    ] == [
        item["action_id"] for item in alternate["plan"]["actions"]
    ]
    assert [
        item["criterion_id"]
        for item in original["plan"]["success_criteria"]
    ] == [
        item["criterion_id"]
        for item in alternate["plan"]["success_criteria"]
    ]


@pytest.mark.anyio
async def test_projection_contains_no_context_or_manifest_prose() -> None:
    original = state()
    before = deepcopy(original)

    delta = await createPlanDraft(original, service=service())

    encoded = json.dumps(delta)
    assert original == before
    assert all(item.summary not in encoded for item in bundle().summaries)
    assert all(
        capability.description not in encoded
        for capability in manifest().capabilities
    )
    assert bundle().resources[0].label not in encoded


@pytest.mark.anyio
async def test_prompt_is_structured_and_marks_all_descriptions_untrusted() -> None:
    gateway = FakeGateway()

    await createPlanDraft(state(), service=service(gateway=gateway))

    request = gateway.requests[0]
    assert request.response_schema["type"] == "object"
    assert "Never return raw paths" in request.messages[0].content
    payload = json.loads(request.messages[1].content)
    assert payload["capability_manifest"]["availability_is_permission"] is False
    assert all(
        item["trust"] == "untrusted_data"
        for item in payload["context_summaries"]
    )
    assert all(
        item["trust"] == "untrusted_data"
        for item in payload["resources"]
    )


def mutated_payload(mutator) -> dict[str, Any]:
    payload = valid_payload()
    mutator(payload)
    return payload


def raw_path_identifier_payload() -> dict[str, Any]:
    payload = valid_payload()
    payload["actions"] = [
        {
            "step_id": "step_tests",
            "capability_id": "tests.run",
            "capability_version": "2.0.0",
            "arguments": [
                {"name": "project", "value": PROJECT_RESOURCE},
                {"name": "suite", "value": "C:/private/test.py"},
                {"name": "fail_fast", "value": True},
            ],
            "depends_on": [],
            "timeout_seconds": 100,
        }
    ]
    payload["success_criteria"] = [
        {
            "step_id": "step_tests",
            "verification_code": "tests_passed",
        }
    ]
    return payload


INVALID_PLAN_CASES = [
    "not-json",
    mutated_payload(lambda p: p.update(objective="desktop_control")),
    mutated_payload(
        lambda p: p["actions"][0].update(capability_id="project.unknown")
    ),
    mutated_payload(
        lambda p: p["actions"][0].update(capability_version="9.0.0")
    ),
    mutated_payload(
        lambda p: p["actions"][0]["arguments"].append(
            {"name": "command", "value": "rm"}
        )
    ),
    mutated_payload(
        lambda p: p["actions"][0].update(arguments=[])
    ),
    mutated_payload(
        lambda p: p["actions"][0]["arguments"][0].update(
            value="res_unlisted01"
        )
    ),
    mutated_payload(
        lambda p: p["actions"][1]["arguments"][1].update(
            value="raw shell command with spaces"
        )
    ),
    raw_path_identifier_payload(),
    mutated_payload(
        lambda p: p["actions"][1]["arguments"][2].update(value=4)
    ),
    mutated_payload(
        lambda p: p["actions"][1].update(depends_on=["step_future"])
    ),
    mutated_payload(
        lambda p: p["actions"][1].update(
            depends_on=["step_inspect", "step_inspect"]
        )
    ),
    mutated_payload(
        lambda p: p["actions"][1].update(step_id="step_inspect")
    ),
    mutated_payload(
        lambda p: p["actions"][1].update(timeout_seconds=121)
    ),
    mutated_payload(
        lambda p: p["success_criteria"][0].update(
            verification_code="invented_check"
        )
    ),
    mutated_payload(lambda p: p.update(success_criteria=p["success_criteria"][1:])),
    mutated_payload(
        lambda p: p["success_criteria"].append(
            deepcopy(p["success_criteria"][0])
        )
    ),
    mutated_payload(
        lambda p: p.update(
            assumptions=["current_context", "current_context"]
        )
    ),
]


@pytest.mark.anyio
@pytest.mark.parametrize("invalid", INVALID_PLAN_CASES)
async def test_invalid_model_plan_gets_one_content_free_repair(
    invalid: dict[str, Any] | str,
) -> None:
    gateway = FakeGateway([response(invalid), response()])

    result = await createPlanDraft(
        state(),
        service=service(gateway=gateway),
    )

    assert result["plan"]["objective"] == "modify_project"
    assert len(gateway.requests) == 2
    repair_text = " ".join(
        message.content for message in gateway.requests[1].messages
    )
    rejected = invalid if isinstance(invalid, str) else json.dumps(invalid)
    assert rejected not in repair_text
    assert "prior response" in gateway.requests[1].messages[-1].content


@pytest.mark.anyio
async def test_duplicate_semantic_action_is_repaired() -> None:
    invalid = valid_payload()
    duplicate = deepcopy(invalid["actions"][0])
    duplicate["step_id"] = "step_inspect_again"
    invalid["actions"].insert(1, duplicate)
    invalid["actions"][2]["depends_on"] = ["step_inspect_again"]
    invalid["success_criteria"].insert(
        1,
        {
            "step_id": "step_inspect_again",
            "verification_code": "inspection_recorded",
        },
    )
    gateway = FakeGateway([response(invalid), response()])

    await createPlanDraft(state(), service=service(gateway=gateway))

    assert len(gateway.requests) == 2


@pytest.mark.anyio
async def test_unstructured_output_is_repaired_once() -> None:
    gateway = FakeGateway(
        [response(structured=False), response()]
    )

    await createPlanDraft(state(), service=service(gateway=gateway))

    assert len(gateway.requests) == 2


@pytest.mark.anyio
async def test_two_invalid_outputs_fail_closed() -> None:
    gateway = FakeGateway([response("bad-one"), response("bad-two")])

    with pytest.raises(PlanDraftError) as caught:
        await createPlanDraft(state(), service=service(gateway=gateway))

    assert caught.value.code == "plan_model_output_invalid"
    assert "bad-one" not in str(caught.value)
    assert "bad-two" not in str(caught.value)
    assert len(gateway.requests) == 2


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("status", "executing", "plan_state_invalid"),
        ("plan", {}, "plan_state_invalid"),
        ("task_id", "bad", "plan_identity_invalid"),
        ("actor_id", "x", "plan_identity_invalid"),
        ("device_id", "x", "plan_identity_invalid"),
        ("context_refs", [], "plan_context_refs_invalid"),
        (
            "context_refs",
            [REFS[0], REFS[0]],
            "plan_context_refs_invalid",
        ),
        (
            "context_refs",
            [REFS[0], REFS[2]],
            "plan_context_refs_invalid",
        ),
        (
            "intent",
            {},
            "plan_intent_invalid",
        ),
    ],
)
async def test_invalid_state_is_rejected(
    field: str,
    value: object,
    code: str,
) -> None:
    invalid = state()
    invalid[field] = value

    with pytest.raises(PlanDraftError) as caught:
        await createPlanDraft(invalid, service=service())

    assert caught.value.code == code


@pytest.mark.anyio
async def test_clarification_required_intent_cannot_be_planned() -> None:
    invalid = state()
    invalid["intent"]["ambiguities"] = ["low_confidence"]
    invalid["intent"]["needs_clarification"] = True

    with pytest.raises(PlanDraftError) as caught:
        await createPlanDraft(invalid, service=service())

    assert caught.value.code == "plan_clarification_required"


@pytest.mark.anyio
async def test_intent_scope_must_remain_authorized() -> None:
    invalid = state()
    invalid["intent"]["scope"]["context_refs"] = ["prj_unlisted01"]

    with pytest.raises(PlanDraftError) as caught:
        await createPlanDraft(invalid, service=service())

    assert caught.value.code == "plan_intent_invalid"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "invalid_bundle",
    [
        "not-a-bundle",
        bundle().model_copy(update={"summaries": bundle().summaries[:-1]}),
        bundle().model_copy(
            update={
                "manifest": manifest().model_copy(
                    update={"reference_id": "cap_different01"}
                )
            }
        ),
        bundle().model_copy(
            update={
                "manifest": manifest().model_copy(
                    update={"actor_id": "actor-other"}
                )
            }
        ),
        bundle().model_copy(
            update={
                "manifest": manifest().model_copy(
                    update={"device_id": "device-other"}
                )
            }
        ),
    ],
)
async def test_invalid_resolved_context_fails_closed(
    invalid_bundle: object,
) -> None:
    with pytest.raises(PlanDraftError) as caught:
        await createPlanDraft(
            state(),
            service=service(resolver=FakeResolver(invalid_bundle)),
        )

    assert caught.value.code == "plan_context_invalid"


@pytest.mark.anyio
async def test_runtime_context_summary_bound_is_enforced() -> None:
    summaries = list(bundle().summaries)
    summaries[0] = summaries[0].model_copy(update={"summary": "x" * 11})
    invalid_bundle = bundle().model_copy(update={"summaries": tuple(summaries)})
    settings = PlanDraftSettings(
        max_summary_chars=10,
        max_total_context_chars=100,
    )

    with pytest.raises(PlanDraftError) as caught:
        await createPlanDraft(
            state(),
            service=service(
                resolver=FakeResolver(invalid_bundle),
                settings=settings,
            ),
        )

    assert caught.value.code == "plan_context_invalid"


@pytest.mark.anyio
async def test_resolver_timeout_and_failure_are_sanitized() -> None:
    with pytest.raises(PlanDraftError) as timeout:
        await createPlanDraft(
            state(),
            service=service(
                resolver=FakeResolver(delay=0.05),
                settings=PlanDraftSettings(
                    resolver_timeout_seconds=0.01
                ),
            ),
        )
    assert timeout.value.code == "plan_context_unavailable"

    with pytest.raises(PlanDraftError) as failure:
        await createPlanDraft(
            state(),
            service=service(
                resolver=FakeResolver(
                    error=RuntimeError("private resolver detail")
                )
            ),
        )
    assert failure.value.code == "plan_context_unavailable"
    assert "private resolver detail" not in str(failure.value)


@pytest.mark.anyio
async def test_provider_failure_is_sanitized_without_retry() -> None:
    gateway = FakeGateway(
        [OllamaProviderError("private provider detail")]
    )

    with pytest.raises(PlanDraftError) as caught:
        await createPlanDraft(state(), service=service(gateway=gateway))

    assert caught.value.code == "plan_model_unavailable"
    assert "private provider detail" not in str(caught.value)
    assert len(gateway.requests) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("source", ["resolver", "gateway"])
async def test_cancellation_propagates(source: str) -> None:
    resolver = FakeResolver(
        error=asyncio.CancelledError()
        if source == "resolver"
        else None
    )
    gateway = FakeGateway(
        [asyncio.CancelledError()]
        if source == "gateway"
        else None
    )

    with pytest.raises(asyncio.CancelledError):
        await createPlanDraft(
            state(),
            service=service(gateway=gateway, resolver=resolver),
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "settings",
    [
        PlanDraftSettings(max_actions=0),
        PlanDraftSettings(max_actions=9),
        PlanDraftSettings(max_actions=8, max_success_criteria=7),
        PlanDraftSettings(max_success_criteria=17),
        PlanDraftSettings(max_total_arguments=0),
        PlanDraftSettings(max_total_arguments=97),
        PlanDraftSettings(max_summary_chars=0),
        PlanDraftSettings(max_summary_chars=2_001),
        PlanDraftSettings(
            max_summary_chars=100,
            max_total_context_chars=99,
        ),
        PlanDraftSettings(max_total_context_chars=16_001),
        PlanDraftSettings(resolver_timeout_seconds=0),
        PlanDraftSettings(resolver_timeout_seconds=31),
    ],
)
async def test_invalid_settings_fail_before_dependencies(
    settings: PlanDraftSettings,
) -> None:
    with pytest.raises(PlanDraftError) as caught:
        await createPlanDraft(state(), service=service(settings=settings))

    assert caught.value.code == "plan_settings_incompatible"


@pytest.mark.parametrize(
    "factory",
    [
        lambda: CapabilityParameter(
            name="mode",
            kind=ParameterKind.ENUM,
        ),
        lambda: CapabilityParameter(
            name="mode",
            kind=ParameterKind.ENUM,
            allowed_values=("has spaces",),
        ),
        lambda: CapabilityParameter(
            name="resource",
            kind=ParameterKind.RESOURCE,
        ),
        lambda: CapabilityParameter(
            name="flag",
            kind=ParameterKind.BOOLEAN,
            allowed_values=("yes",),
        ),
        lambda: CapabilityParameter(
            name="count",
            kind=ParameterKind.INTEGER,
            minimum=2,
            maximum=1,
        ),
        lambda: CapabilityParameter(
            name="count",
            kind=ParameterKind.NUMBER,
            minimum=float("nan"),
        ),
    ],
)
def test_invalid_capability_parameter_contract_is_rejected(factory) -> None:
    with pytest.raises(ValidationError):
        factory()


def test_model_schema_forbids_free_form_plan_fields() -> None:
    fields = ModelPlanDraft.model_fields

    assert set(fields) == {
        "objective",
        "assumptions",
        "actions",
        "success_criteria",
        "warnings",
    }
    schema_text = json.dumps(ModelPlanDraft.model_json_schema())
    assert "rationale" not in schema_text
    assert "command" not in schema_text
    assert "risk" not in schema_text
