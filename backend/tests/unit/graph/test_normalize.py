from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from jarvis.graph import (
    RequestNormalizationError,
    RequestNormalizationSettings,
    normalizeRequest,
)


CONTENT = "  Continue Café\r\nDo NOT trim or rewrite this.  "
TASK_ID = "tsk_" + "a" * 32
THREAD_ID = "thr_" + "b" * 32


def request_state() -> dict[str, Any]:
    return {
        "contract_version": "1.2.0",
        "task_id": TASK_ID,
        "thread_id": THREAD_ID,
        "actor_id": "actor-001",
        "device_id": "device-001",
        "request": {
            "input": {
                "type": "text",
                "content": CONTENT,
            }
        },
        "status": "created",
    }


def test_normalizes_metadata_without_rewriting_user_content() -> None:
    state = request_state()
    original = deepcopy(state)

    delta = normalizeRequest(state)

    assert delta == {
        "contract_version": "1.2.0",
        "task_id": TASK_ID,
        "thread_id": THREAD_ID,
        "request": {
            "input": {
                "type": "text",
                "content": CONTENT,
            }
        },
        "status": "planning",
    }
    assert delta["request"]["input"]["content"] == CONTENT
    assert state == original


def test_transcript_input_is_preserved_as_transcript() -> None:
    state = request_state()
    state["request"]["input"]["type"] = "transcript"

    delta = normalizeRequest(state)

    assert delta["request"]["input"] == {
        "type": "transcript",
        "content": CONTENT,
    }


def test_missing_ids_are_assigned_once_and_stable_after_merge() -> None:
    state = request_state()
    state["task_id"] = ""
    state["thread_id"] = ""
    generated = "c" * 32

    first = normalizeRequest(state, id_factory=lambda: generated)
    merged = {**state, **first}

    def must_not_generate() -> str:
        raise AssertionError("existing IDs must be preserved")

    second = normalizeRequest(merged, id_factory=must_not_generate)

    assert first["task_id"] == "tsk_" + generated
    assert first["thread_id"] == "thr_" + generated
    assert second == first


def test_existing_ids_never_call_generator() -> None:
    def must_not_generate() -> str:
        raise AssertionError("generator must not be called")

    delta = normalizeRequest(request_state(), id_factory=must_not_generate)

    assert delta["task_id"] == TASK_ID
    assert delta["thread_id"] == THREAD_ID


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("actor_id", ""),
        ("actor_id", "actor with spaces"),
        ("device_id", None),
        ("task_id", "tsk_short"),
        ("thread_id", "thr_short"),
    ],
)
def test_rejects_invalid_identity_metadata(
    field: str,
    value: object,
) -> None:
    state = request_state()
    state[field] = value

    with pytest.raises(RequestNormalizationError) as captured:
        normalizeRequest(state)

    assert captured.value.code == "request_identity_invalid"


@pytest.mark.parametrize(
    "contract_version",
    [None, "", "developement", "2.0.0"],
)
def test_rejects_invalid_or_unsupported_contract(
    contract_version: object,
) -> None:
    state = request_state()
    state["contract_version"] = contract_version

    with pytest.raises(RequestNormalizationError) as captured:
        normalizeRequest(state)

    assert captured.value.code == "request_contract_unsupported"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"input": {"type": "text", "content": " "}},
        {"input": {"type": "text", "content": "unsafe\x00content"}},
        {"input": {"type": "unknown", "content": "hello"}},
        {"input": {"type": "text", "content": "hello"}, "extra": True},
        {"input": {"type": "text", "content": "x" * 16_001}},
    ],
)
def test_rejects_malformed_payload_without_echoing_content(
    payload: object,
) -> None:
    state = request_state()
    state["request"] = payload

    with pytest.raises(RequestNormalizationError) as captured:
        normalizeRequest(state)

    assert captured.value.code == "request_payload_invalid"
    assert "unsafe" not in str(captured.value)
    assert "hello" not in str(captured.value)


def test_rejects_serialized_request_over_configured_byte_limit() -> None:
    with pytest.raises(RequestNormalizationError) as captured:
        normalizeRequest(
            request_state(),
            settings=RequestNormalizationSettings(
                max_serialized_request_bytes=32
            ),
        )

    assert captured.value.code == "request_payload_too_large"


@pytest.mark.parametrize(
    "settings",
    [
        RequestNormalizationSettings(max_serialized_request_bytes=0),
        RequestNormalizationSettings(supported_contract_major=0),
    ],
)
def test_rejects_invalid_normalization_settings(
    settings: RequestNormalizationSettings,
) -> None:
    with pytest.raises(RequestNormalizationError) as captured:
        normalizeRequest(request_state(), settings=settings)

    assert captured.value.code == "normalization_settings_incompatible"


def test_rejects_invalid_workflow_status() -> None:
    state = request_state()
    state["status"] = "executing"

    with pytest.raises(RequestNormalizationError) as captured:
        normalizeRequest(state)

    assert captured.value.code == "request_status_invalid"


def test_rejects_invalid_generated_identifier_without_reflection() -> None:
    state = request_state()
    state["task_id"] = ""
    state["thread_id"] = ""

    with pytest.raises(RequestNormalizationError) as captured:
        normalizeRequest(
            state,
            id_factory=lambda: "not-a-secret-or-valid-identifier",
        )

    assert captured.value.code == "request_id_generation_failed"
    assert "not-a-secret" not in str(captured.value)
