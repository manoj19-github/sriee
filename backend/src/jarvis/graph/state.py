"""Canonical JSON-compatible JARVIS graph state and append reducers."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class JarvisState(TypedDict):
    """Versioned workflow state; nodes return partial updates to these fields."""

    contract_version: str
    task_id: str
    thread_id: str
    actor_id: str
    device_id: str
    request: dict[str, Any]
    context_refs: list[str]
    intent: dict[str, Any] | None
    plan: dict[str, Any] | None
    policy_decisions: list[dict[str, Any]]
    pending_approval: dict[str, Any] | None
    action_results: Annotated[list[dict[str, Any]], operator.add]
    observations: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[dict[str, Any]], operator.add]
    status: str
    revision_count: int
    final_response: dict[str, Any] | None
