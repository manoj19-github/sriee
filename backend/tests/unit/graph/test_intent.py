from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from typing import Any

import pytest

from jarvis.graph import (
    AmbiguityCode,
    ContextKind,
    ContextSummary,
    IntentClassificationError,
    IntentClassificationService,
    IntentClassifierSettings,
    IntentName,
    IntentTarget,
    classifyIntent,
)
from jarvis.providers.ollama import (
    OllamaChatResponse,
    OllamaProviderError,
)


ACTOR_ID = "actor-001"
DEVICE_ID = "device-001"
TASK_ID = "tsk_" + "a" * 32
REQUEST_CONTENT = "Continue the current project and fix its tests."
CONTEXT_REFS = (
    "pol_policy001",
    "cap_manifest01",
    "prj_project001",
    "mem_memory001",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def state() -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "actor_id": ACTOR_ID,
        "device_id": DEVICE_ID,
        "request": {
            "input": {
                "type": "text",
                "content": REQUEST_CONTENT,
            }
        },
        "context_refs": list(CONTEXT_REFS),
        "intent": None,
        "status": "planning",
    }


def summaries() -> tuple[ContextSummary, ...]:
    return (
        ContextSummary(
            reference_id=CONTEXT_REFS[0],
            kind=ContextKind.POLICY,
            summary="Current policy snapshot is available.",
        ),
        ContextSummary(
            reference_id=CONTEXT_REFS[1],
            kind=ContextKind.CAPABILITY,
            summary="Developer project capabilities are available.",
        ),
        ContextSummary(
            reference_id=CONTEXT_REFS[2],
            kind=ContextKind.PROJECT,
            summary="A current Python project is selected.",
        ),
        ContextSummary(
            reference_id=CONTEXT_REFS[3],
            kind=ContextKind.MEMORY,
            summary="The user was working on test failures.",
        ),
    )


def model_json(
    *,
    intent: str = "continue_project",
    confidence: float = 0.91,
    target: str = "project",
    context_refs: list[str] | None = None,
    ambiguities: list[str] | None = None,
) -> str:
    return json.dumps(
        {
            "intent": intent,
            "confidence": confidence,
            "target": target,
            "context_refs": (
                [CONTEXT_REFS[2]]
                if context_refs is None
                else context_refs
            ),
            "ambiguities": [] if ambiguities is None else ambiguities,
        }
    )


def response(content: str, *, structured: bool = True) -> OllamaChatResponse:
    return OllamaChatResponse(
        model="qwen3:4b-instruct",
        content=content,
        prompt_tokens=20,
        output_tokens=10,
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
        self.result = summaries() if result is None else result
        self.error = error
        self.delay = delay
        self.calls: list[tuple[tuple[str, ...], str, str, int]] = []

    async def resolve_summaries(
        self,
        reference_ids,
        *,
        actor_id: str,
        device_id: str,
        limit: int,
    ):
        self.calls.append((reference_ids, actor_id, device_id, limit))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.result


class FakeGateway:
    def __init__(
        self,
        results: list[object] | None = None,
    ) -> None:
        self.results = results or [response(model_json())]
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
    settings: IntentClassifierSettings | None = None,
) -> IntentClassificationService:
    return IntentClassificationService(
        gateway=gateway or FakeGateway(),
        resolver=resolver or FakeResolver(),
        settings=settings or IntentClassifierSettings(),
    )


@pytest.mark.anyio
async def test_classifies_high_confidence_consequential_intent() -> None:
    resolver = FakeResolver()
    gateway = FakeGateway()

    delta = await classifyIntent(
        state(),
        service=service(gateway=gateway, resolver=resolver),
    )

    assert delta == {
        "intent": {
            "name": "continue_project",
            "confidence": 0.91,
            "scope": {
                "target": "project",
                "context_refs": [CONTEXT_REFS[2]],
            },
            "ambiguities": [],
            "consequential": True,
            "needs_clarification": False,
        }
    }
    assert resolver.calls == [
        (CONTEXT_REFS, ACTOR_ID, DEVICE_ID, 16)
    ]
    assert len(gateway.requests) == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("intent", "target"),
    [
        (IntentName.INFORMATION_REQUEST, IntentTarget.GENERAL),
        (IntentName.CONVERSATION, IntentTarget.NONE),
    ],
)
async def test_low_confidence_nonconsequential_intent_does_not_force_clarification(
    intent: IntentName,
    target: IntentTarget,
) -> None:
    gateway = FakeGateway(
        [
            response(
                model_json(
                    intent=intent.value,
                    confidence=0.30,
                    target=target.value,
                    context_refs=[],
                )
            )
        ]
    )

    delta = await classifyIntent(state(), service=service(gateway=gateway))

    assert delta["intent"]["consequential"] is False
    assert delta["intent"]["needs_clarification"] is False
    assert delta["intent"]["ambiguities"] == []


@pytest.mark.anyio
async def test_low_confidence_consequential_intent_routes_to_clarification() -> None:
    gateway = FakeGateway(
        [response(model_json(confidence=0.69))]
    )

    delta = await classifyIntent(state(), service=service(gateway=gateway))

    assert delta["intent"]["ambiguities"] == ["low_confidence"]
    assert delta["intent"]["needs_clarification"] is True


@pytest.mark.anyio
async def test_unknown_intent_routes_to_clarification() -> None:
    gateway = FakeGateway(
        [
            response(
                model_json(
                    intent="unknown",
                    confidence=0.95,
                    target="none",
                    context_refs=[],
                )
            )
        ]
    )

    delta = await classifyIntent(state(), service=service(gateway=gateway))

    assert delta["intent"]["ambiguities"] == ["unsupported_request"]
    assert delta["intent"]["needs_clarification"] is True


@pytest.mark.anyio
async def test_project_intent_without_project_reference_routes_to_clarification() -> None:
    gateway = FakeGateway(
        [response(model_json(context_refs=[CONTEXT_REFS[1]]))]
    )

    delta = await classifyIntent(state(), service=service(gateway=gateway))

    assert delta["intent"]["ambiguities"] == ["missing_project"]


@pytest.mark.anyio
async def test_incompatible_consequential_target_routes_to_clarification() -> None:
    gateway = FakeGateway(
        [response(model_json(target="desktop"))]
    )

    delta = await classifyIntent(state(), service=service(gateway=gateway))

    assert delta["intent"]["ambiguities"] == ["ambiguous_target"]
    assert delta["intent"]["needs_clarification"] is True


@pytest.mark.anyio
async def test_project_target_requires_project_scope_for_any_intent() -> None:
    gateway = FakeGateway(
        [
            response(
                model_json(
                    intent="information_request",
                    target="project",
                    context_refs=[CONTEXT_REFS[1]],
                )
            )
        ]
    )

    delta = await classifyIntent(state(), service=service(gateway=gateway))

    assert delta["intent"]["ambiguities"] == ["missing_project"]


@pytest.mark.anyio
async def test_model_ambiguities_are_deduplicated_and_canonically_ordered() -> None:
    gateway = FakeGateway(
        [
            response(
                model_json(
                    confidence=0.50,
                    context_refs=[],
                    ambiguities=[
                        "unclear_action",
                        "ambiguous_target",
                        "unclear_action",
                    ],
                )
            )
        ]
    )

    delta = await classifyIntent(state(), service=service(gateway=gateway))

    assert delta["intent"]["ambiguities"] == [
        "missing_project",
        "ambiguous_target",
        "unclear_action",
        "low_confidence",
    ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "bad_content",
    [
        "not json",
        model_json(intent="invented"),
        model_json(context_refs=["prj_notauthorized"]),
        model_json(context_refs=[CONTEXT_REFS[2], CONTEXT_REFS[2]]),
    ],
)
async def test_invalid_model_output_gets_one_content_free_repair(
    bad_content: str,
) -> None:
    gateway = FakeGateway(
        [response(bad_content), response(model_json())]
    )

    delta = await classifyIntent(state(), service=service(gateway=gateway))

    assert delta["intent"]["name"] == "continue_project"
    assert len(gateway.requests) == 2
    repair_messages = gateway.requests[1].messages
    assert repair_messages[-1].role == "system"
    assert "prior response" in repair_messages[-1].content
    assert bad_content not in " ".join(
        message.content for message in repair_messages
    )


@pytest.mark.anyio
async def test_two_invalid_model_outputs_fail_closed() -> None:
    gateway = FakeGateway(
        [response("bad-one"), response("bad-two")]
    )

    with pytest.raises(IntentClassificationError) as caught:
        await classifyIntent(state(), service=service(gateway=gateway))

    assert caught.value.code == "intent_model_output_invalid"
    assert len(gateway.requests) == 2
    assert "bad-one" not in str(caught.value)
    assert "bad-two" not in str(caught.value)


@pytest.mark.anyio
async def test_unstructured_response_is_repaired() -> None:
    gateway = FakeGateway(
        [
            response(model_json(), structured=False),
            response(model_json()),
        ]
    )

    await classifyIntent(state(), service=service(gateway=gateway))

    assert len(gateway.requests) == 2


@pytest.mark.anyio
async def test_prompt_is_bounded_structured_and_labels_context_untrusted() -> None:
    gateway = FakeGateway()

    await classifyIntent(state(), service=service(gateway=gateway))

    request = gateway.requests[0]
    assert request.response_schema["type"] == "object"
    assert request.messages[0].role == "system"
    assert "Classify only" in request.messages[0].content
    payload = json.loads(request.messages[1].content)
    assert payload["request"]["input"]["content"] == REQUEST_CONTENT
    assert all(
        item["trust"] == "untrusted_data"
        for item in payload["context_summaries"]
    )


@pytest.mark.anyio
async def test_input_is_not_mutated_and_output_excludes_source_content() -> None:
    original = state()
    before = deepcopy(original)

    delta = await classifyIntent(original, service=service())

    assert original == before
    encoded = json.dumps(delta)
    assert REQUEST_CONTENT not in encoded
    assert all(summary.summary not in encoded for summary in summaries())


@pytest.mark.anyio
@pytest.mark.parametrize(
    "result",
    [
        "not-a-sequence",
        summaries()[:-1],
        summaries() + (summaries()[0],),
        (
            *summaries()[:-1],
            ContextSummary(
                reference_id="mem_unlisted01",
                kind=ContextKind.MEMORY,
                summary="Unlisted.",
            ),
        ),
        (
            ContextSummary(
                reference_id=CONTEXT_REFS[0],
                kind=ContextKind.PROJECT,
                summary="Wrong kind.",
            ),
            *summaries()[1:],
        ),
    ],
)
async def test_invalid_resolved_context_fails_closed(result: object) -> None:
    with pytest.raises(IntentClassificationError) as caught:
        await classifyIntent(
            state(),
            service=service(resolver=FakeResolver(result)),
        )

    assert caught.value.code == "intent_context_invalid"


@pytest.mark.anyio
async def test_context_summary_runtime_bound_is_enforced() -> None:
    bounded = list(summaries())
    bounded[0] = bounded[0].model_copy(update={"summary": "x" * 11})
    settings = IntentClassifierSettings(
        max_summary_chars=10,
        max_total_context_chars=100,
    )

    with pytest.raises(IntentClassificationError) as caught:
        await classifyIntent(
            state(),
            service=service(
                resolver=FakeResolver(tuple(bounded)),
                settings=settings,
            ),
        )

    assert caught.value.code == "intent_context_invalid"


@pytest.mark.anyio
async def test_context_resolver_timeout_is_sanitized() -> None:
    settings = IntentClassifierSettings(resolver_timeout_seconds=0.01)

    with pytest.raises(IntentClassificationError) as caught:
        await classifyIntent(
            state(),
            service=service(
                resolver=FakeResolver(delay=0.05),
                settings=settings,
            ),
        )

    assert caught.value.code == "intent_context_unavailable"


@pytest.mark.anyio
async def test_context_resolver_failure_is_sanitized() -> None:
    resolver = FakeResolver(error=RuntimeError("secret source details"))

    with pytest.raises(IntentClassificationError) as caught:
        await classifyIntent(state(), service=service(resolver=resolver))

    assert caught.value.code == "intent_context_unavailable"
    assert "secret source details" not in str(caught.value)


@pytest.mark.anyio
async def test_model_provider_failure_is_sanitized_without_retry() -> None:
    gateway = FakeGateway(
        [OllamaProviderError("private-provider-detail")]
    )

    with pytest.raises(IntentClassificationError) as caught:
        await classifyIntent(state(), service=service(gateway=gateway))

    assert caught.value.code == "intent_model_unavailable"
    assert "private-provider-detail" not in str(caught.value)
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
        await classifyIntent(
            state(),
            service=service(gateway=gateway, resolver=resolver),
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("status", "executing", "intent_state_invalid"),
        ("task_id", "bad", "intent_identity_invalid"),
        ("actor_id", "x", "intent_identity_invalid"),
        ("device_id", "x", "intent_identity_invalid"),
        ("request", {}, "intent_request_invalid"),
        ("context_refs", [], "intent_context_refs_invalid"),
        (
            "context_refs",
            [CONTEXT_REFS[0], CONTEXT_REFS[0]],
            "intent_context_refs_invalid",
        ),
        (
            "context_refs",
            [CONTEXT_REFS[0], "invalid"],
            "intent_context_refs_invalid",
        ),
        (
            "context_refs",
            [CONTEXT_REFS[0], CONTEXT_REFS[2]],
            "intent_context_refs_invalid",
        ),
        (
            "context_refs",
            [CONTEXT_REFS[1], CONTEXT_REFS[2]],
            "intent_context_refs_invalid",
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

    with pytest.raises(IntentClassificationError) as caught:
        await classifyIntent(invalid, service=service())

    assert caught.value.code == code


@pytest.mark.anyio
@pytest.mark.parametrize(
    "settings",
    [
        IntentClassifierSettings(confidence_threshold=0),
        IntentClassifierSettings(confidence_threshold=1.1),
        IntentClassifierSettings(max_context_refs=1),
        IntentClassifierSettings(max_context_refs=17),
        IntentClassifierSettings(max_summary_chars=0),
        IntentClassifierSettings(max_summary_chars=2_001),
        IntentClassifierSettings(
            max_summary_chars=100,
            max_total_context_chars=99,
        ),
        IntentClassifierSettings(max_total_context_chars=24_001),
        IntentClassifierSettings(resolver_timeout_seconds=0),
        IntentClassifierSettings(resolver_timeout_seconds=31),
    ],
)
async def test_incompatible_settings_are_rejected(
    settings: IntentClassifierSettings,
) -> None:
    with pytest.raises(IntentClassificationError) as caught:
        await classifyIntent(
            state(),
            service=service(settings=settings),
        )

    assert caught.value.code == "intent_settings_incompatible"
