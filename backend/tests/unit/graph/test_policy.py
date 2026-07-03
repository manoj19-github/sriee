from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from jarvis.graph import (
    PlanPolicyError,
    PlanPolicyService,
    PlanPolicySettings,
    PolicyActionRule,
    PolicyAggregateRule,
    PolicyDecisionKind,
    PolicySnapshot,
    RiskTier,
    SecurityAssessment,
    SecurityRecommendation,
    evaluatePlanPolicy,
    routeAfterPolicy,
)


TASK_ID = "tsk_" + "e" * 32
ACTOR_ID = "actor-001"
DEVICE_ID = "device-001"
POLICY_REF = "pol_policy001"
CAPABILITY_REF = "cap_manifest01"
PROJECT_REF = "prj_project001"
RESOURCE_ID = "res_project001"
ACTION_INSPECT = "act_" + "1" * 24
ACTION_UPDATE = "act_" + "2" * 24


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
                "criterion_id": "crt_" + "3" * 24,
                "action_id": ACTION_INSPECT,
                "verification_code": "inspection_recorded",
            },
            {
                "criterion_id": "crt_" + "4" * 24,
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
        "context_refs": [POLICY_REF, CAPABILITY_REF, PROJECT_REF],
        "plan": plan(),
        "policy_decisions": [],
        "status": "planning",
    }


def inspect_rule(
    *,
    decision: PolicyDecisionKind = PolicyDecisionKind.ALLOW,
    risk_tier: RiskTier = RiskTier.R0,
) -> PolicyActionRule:
    return PolicyActionRule(
        rule_id="prl_inspect01",
        capability_id="project.inspect",
        capability_version="1.0.0",
        decision=decision,
        risk_tier=risk_tier,
        reason_code="read_only_inspection",
    )


def update_rule(
    *,
    decision: PolicyDecisionKind = PolicyDecisionKind.ASK,
    risk_tier: RiskTier = RiskTier.R2,
    grant_reference_id: str | None = None,
) -> PolicyActionRule:
    return PolicyActionRule(
        rule_id="prl_update001",
        capability_id="project.update",
        capability_version="1.2.0",
        decision=decision,
        risk_tier=risk_tier,
        reason_code="scoped_project_mutation",
        grant_reference_id=grant_reference_id,
    )


def snapshot(
    *,
    action_rules: tuple[PolicyActionRule, ...] | None = None,
    aggregate_rules: tuple[PolicyAggregateRule, ...] = (),
    actor_id: str = ACTOR_ID,
    device_id: str = DEVICE_ID,
) -> PolicySnapshot:
    return PolicySnapshot(
        reference_id=POLICY_REF,
        version="1.0.0",
        actor_id=actor_id,
        device_id=device_id,
        action_rules=(
            action_rules
            if action_rules is not None
            else (inspect_rule(), update_rule())
        ),
        aggregate_rules=aggregate_rules,
    )


class FakeResolver:
    def __init__(
        self,
        result: object | None = None,
        *,
        error: BaseException | None = None,
        delay: float = 0,
    ) -> None:
        self.result = snapshot() if result is None else result
        self.error = error
        self.delay = delay
        self.calls: list[tuple[str, str, str]] = []

    async def resolve_policy_snapshot(
        self,
        reference_id: str,
        *,
        actor_id: str,
        device_id: str,
    ):
        self.calls.append((reference_id, actor_id, device_id))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.result


class FakeAdvisor:
    def __init__(
        self,
        result: object | None = None,
        *,
        error: BaseException | None = None,
        delay: float = 0,
    ) -> None:
        self.result = result or SecurityAssessment()
        self.error = error
        self.delay = delay
        self.calls = []

    async def analyze_plan(self, selected_plan, baseline):
        self.calls.append((selected_plan, baseline))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.result


def service(
    *,
    resolver: FakeResolver | None = None,
    advisor: FakeAdvisor | None = None,
    settings: PlanPolicySettings | None = None,
) -> PlanPolicyService:
    return PlanPolicyService(
        resolver=resolver or FakeResolver(),
        security_advisor=advisor,
        settings=settings or PlanPolicySettings(),
    )


async def assert_rejected(
    selected_state: dict[str, Any],
    code: str,
    *,
    selected_service: PlanPolicyService | None = None,
) -> None:
    with pytest.raises(PlanPolicyError) as captured:
        await evaluatePlanPolicy(
            selected_state,
            service=selected_service or service(),
        )
    assert captured.value.code == code


@pytest.mark.anyio
async def test_evaluates_every_action_and_routes_to_approval() -> None:
    resolver = FakeResolver()

    first = await evaluatePlanPolicy(
        state(),
        service=service(resolver=resolver),
    )
    second = await evaluatePlanPolicy(state(), service=service())

    assert first == second
    assert first["status"] == "awaiting_approval"
    assert [item["action_id"] for item in first["policy_decisions"]] == [
        ACTION_INSPECT,
        ACTION_UPDATE,
    ]
    assert [item["decision"] for item in first["policy_decisions"]] == [
        "allow",
        "ask",
    ]
    assert first["policy_decisions"][0]["requires_fresh_approval"] is False
    assert first["policy_decisions"][1]["requires_fresh_approval"] is True
    assert all(
        item["decision_id"].startswith("pdc_")
        for item in first["policy_decisions"]
    )
    assert resolver.calls == [(POLICY_REF, ACTOR_ID, DEVICE_ID)]
    assert RESOURCE_ID not in str(first)
    assert routeAfterPolicy({**state(), **first}) == "pause_for_approval"


@pytest.mark.anyio
async def test_all_allow_routes_to_execution_and_scoped_r2_grant_survives() -> None:
    selected_snapshot = snapshot(
        action_rules=(
            inspect_rule(),
            update_rule(
                decision=PolicyDecisionKind.ALLOW,
                grant_reference_id="grt_project001",
            ),
        )
    )

    result = await evaluatePlanPolicy(
        state(),
        service=service(resolver=FakeResolver(selected_snapshot)),
    )

    assert result["status"] == "executing"
    update = result["policy_decisions"][1]
    assert update["decision"] == "allow"
    assert update["grant_reference_id"] == "grt_project001"


@pytest.mark.anyio
async def test_explicit_deny_routes_entire_plan_to_denied() -> None:
    selected_snapshot = snapshot(
        action_rules=(
            inspect_rule(),
            update_rule(
                decision=PolicyDecisionKind.DENY,
                risk_tier=RiskTier.R4,
            ),
        )
    )

    result = await evaluatePlanPolicy(
        state(),
        service=service(resolver=FakeResolver(selected_snapshot)),
    )

    assert result["status"] == "denied"
    assert result["policy_decisions"][1]["decision"] == "deny"


@pytest.mark.anyio
async def test_unknown_capability_fails_closed_with_default_deny() -> None:
    selected_state = state()
    selected_state["plan"]["actions"][1]["capability_id"] = (
        "project.unregistered"
    )

    result = await evaluatePlanPolicy(
        selected_state,
        service=service(),
    )

    unknown = result["policy_decisions"][1]
    assert result["status"] == "denied"
    assert unknown["decision"] == "deny"
    assert unknown["risk_tier"] == "r4"
    assert unknown["reason_codes"] == ["policy_default_deny"]


@pytest.mark.anyio
async def test_aggregate_rule_elevates_all_matching_actions() -> None:
    anti_split = PolicyAggregateRule(
        rule_id="prl_combined01",
        capability_ids=("project.inspect", "project.update"),
        minimum_matches=2,
        decision=PolicyDecisionKind.ASK,
        risk_tier=RiskTier.R3,
        reason_code="combined_project_effect",
    )
    selected_snapshot = snapshot(
        action_rules=(inspect_rule(), update_rule()),
        aggregate_rules=(anti_split,),
    )

    result = await evaluatePlanPolicy(
        state(),
        service=service(resolver=FakeResolver(selected_snapshot)),
    )

    assert result["status"] == "awaiting_approval"
    assert all(
        item["decision"] == "ask"
        and item["risk_tier"] == "r3"
        and "combined_project_effect" in item["reason_codes"]
        for item in result["policy_decisions"]
    )


@pytest.mark.anyio
async def test_repeated_capability_cannot_split_aggregate_threshold() -> None:
    selected_state = state()
    second_inspection = deepcopy(
        selected_state["plan"]["actions"][0]
    )
    second_inspection["action_id"] = "act_" + "5" * 24
    second_inspection["arguments"][0]["value"] = "res_project002"
    selected_state["plan"]["actions"].append(second_inspection)
    selected_state["plan"]["success_criteria"].append(
        {
            "criterion_id": "crt_" + "6" * 24,
            "action_id": second_inspection["action_id"],
            "verification_code": "inspection_recorded",
        }
    )
    anti_split = PolicyAggregateRule(
        rule_id="prl_repeated01",
        capability_ids=("project.inspect",),
        minimum_matches=2,
        decision=PolicyDecisionKind.ASK,
        risk_tier=RiskTier.R2,
        reason_code="repeated_read_scope",
    )

    result = await evaluatePlanPolicy(
        selected_state,
        service=service(
            resolver=FakeResolver(
                snapshot(aggregate_rules=(anti_split,))
            )
        ),
    )

    inspect_decisions = [
        item
        for item in result["policy_decisions"]
        if item["action_id"] in {ACTION_INSPECT, second_inspection["action_id"]}
    ]
    assert len(inspect_decisions) == 2
    assert all(item["decision"] == "ask" for item in inspect_decisions)


@pytest.mark.anyio
async def test_security_advisor_can_only_tighten_policy() -> None:
    selected_snapshot = snapshot(
        action_rules=(
            inspect_rule(),
            update_rule(
                decision=PolicyDecisionKind.ALLOW,
                grant_reference_id="grt_project001",
            ),
        )
    )
    advisor = FakeAdvisor(
        SecurityAssessment(
            recommendations=(
                SecurityRecommendation(
                    action_id=ACTION_UPDATE,
                    decision=PolicyDecisionKind.DENY,
                    risk_tier=RiskTier.R4,
                    reason_code="security_external_effect",
                ),
            )
        )
    )

    result = await evaluatePlanPolicy(
        state(),
        service=service(
            resolver=FakeResolver(selected_snapshot),
            advisor=advisor,
        ),
    )

    assert result["status"] == "denied"
    update = result["policy_decisions"][1]
    assert update["decision"] == "deny"
    assert update["grant_reference_id"] is None
    assert "security_external_effect" in update["reason_codes"]
    assert len(advisor.calls) == 1


@pytest.mark.anyio
async def test_weaker_security_recommendation_is_ignored() -> None:
    advisor = FakeAdvisor(
        SecurityAssessment(
            recommendations=(
                SecurityRecommendation(
                    action_id=ACTION_UPDATE,
                    decision=PolicyDecisionKind.ALLOW,
                    risk_tier=RiskTier.R0,
                    reason_code="model_suggested_allow",
                ),
            )
        )
    )

    result = await evaluatePlanPolicy(
        state(),
        service=service(advisor=advisor),
    )

    update = result["policy_decisions"][1]
    assert update["decision"] == "ask"
    assert update["risk_tier"] == "r2"
    assert "model_suggested_allow" not in update["reason_codes"]


@pytest.mark.anyio
async def test_security_risk_cannot_create_ungranted_r2_allow() -> None:
    advisor = FakeAdvisor(
        SecurityAssessment(
            recommendations=(
                SecurityRecommendation(
                    action_id=ACTION_INSPECT,
                    decision=PolicyDecisionKind.ALLOW,
                    risk_tier=RiskTier.R2,
                    reason_code="security_scoped_effect",
                ),
            )
        )
    )

    result = await evaluatePlanPolicy(
        state(),
        service=service(advisor=advisor),
    )

    inspection = result["policy_decisions"][0]
    assert inspection["risk_tier"] == "r2"
    assert inspection["decision"] == "ask"
    assert inspection["requires_fresh_approval"] is True


@pytest.mark.anyio
async def test_global_security_risk_applies_to_every_action() -> None:
    advisor = FakeAdvisor(
        SecurityAssessment(
            recommendations=(
                SecurityRecommendation(
                    action_id=None,
                    decision=PolicyDecisionKind.ASK,
                    risk_tier=RiskTier.R3,
                    reason_code="security_plan_scope",
                ),
            )
        )
    )

    result = await evaluatePlanPolicy(
        state(),
        service=service(advisor=advisor),
    )

    assert result["status"] == "awaiting_approval"
    assert all(
        item["decision"] == "ask"
        and "security_plan_scope" in item["reason_codes"]
        for item in result["policy_decisions"]
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("status", "executing", "plan_policy_state_invalid"),
        ("plan", None, "plan_policy_state_invalid"),
        (
            "policy_decisions",
            [{"decision": "allow"}],
            "plan_policy_state_invalid",
        ),
        ("task_id", "unsafe", "plan_policy_identity_invalid"),
        (
            "context_refs",
            [CAPABILITY_REF, PROJECT_REF],
            "plan_policy_context_invalid",
        ),
    ],
)
async def test_rejects_invalid_graph_state(
    field: str,
    value: object,
    code: str,
) -> None:
    invalid = state()
    invalid[field] = value

    await assert_rejected(invalid, code)


@pytest.mark.anyio
async def test_rejects_malformed_plan() -> None:
    invalid = state()
    invalid["plan"]["schema_version"] = "2.0"

    await assert_rejected(invalid, "plan_policy_plan_invalid")


@pytest.mark.anyio
async def test_rejects_mismatched_or_malformed_snapshot() -> None:
    await assert_rejected(
        state(),
        "policy_snapshot_invalid",
        selected_service=service(
            resolver=FakeResolver(snapshot(actor_id="actor-002"))
        ),
    )
    await assert_rejected(
        state(),
        "policy_snapshot_invalid",
        selected_service=service(resolver=FakeResolver(object())),
    )


@pytest.mark.anyio
async def test_snapshot_failure_and_timeout_are_sanitized() -> None:
    await assert_rejected(
        state(),
        "policy_snapshot_unavailable",
        selected_service=service(
            resolver=FakeResolver(error=RuntimeError("private"))
        ),
    )
    await assert_rejected(
        state(),
        "policy_snapshot_unavailable",
        selected_service=service(
            resolver=FakeResolver(delay=0.05),
            settings=PlanPolicySettings(
                resolver_timeout_seconds=0.001
            ),
        ),
    )


@pytest.mark.anyio
async def test_invalid_security_assessment_fails_closed() -> None:
    unknown_action = SecurityAssessment(
        recommendations=(
            SecurityRecommendation(
                action_id="act_" + "9" * 24,
                decision=PolicyDecisionKind.DENY,
                risk_tier=RiskTier.R4,
                reason_code="security_unknown_action",
            ),
        )
    )
    await assert_rejected(
        state(),
        "policy_security_assessment_invalid",
        selected_service=service(advisor=FakeAdvisor(unknown_action)),
    )
    await assert_rejected(
        state(),
        "policy_security_assessment_invalid",
        selected_service=service(advisor=FakeAdvisor(object())),
    )


@pytest.mark.anyio
async def test_security_advisor_failure_and_timeout_fail_closed() -> None:
    await assert_rejected(
        state(),
        "policy_security_analysis_unavailable",
        selected_service=service(
            advisor=FakeAdvisor(error=RuntimeError("private"))
        ),
    )
    await assert_rejected(
        state(),
        "policy_security_analysis_unavailable",
        selected_service=service(
            advisor=FakeAdvisor(delay=0.05),
            settings=PlanPolicySettings(
                advisor_timeout_seconds=0.001
            ),
        ),
    )


@pytest.mark.anyio
async def test_cancellation_propagates_from_resolver_and_advisor() -> None:
    with pytest.raises(asyncio.CancelledError):
        await evaluatePlanPolicy(
            state(),
            service=service(
                resolver=FakeResolver(error=asyncio.CancelledError())
            ),
        )
    with pytest.raises(asyncio.CancelledError):
        await evaluatePlanPolicy(
            state(),
            service=service(
                advisor=FakeAdvisor(error=asyncio.CancelledError())
            ),
        )


@pytest.mark.anyio
async def test_rejects_incompatible_settings_before_resolution() -> None:
    resolver = FakeResolver()

    await assert_rejected(
        state(),
        "plan_policy_settings_incompatible",
        selected_service=service(
            resolver=resolver,
            settings=PlanPolicySettings(
                resolver_timeout_seconds=0,
            ),
        ),
    )

    assert resolver.calls == []


def test_policy_models_enforce_safety_floors_and_deny_by_default() -> None:
    with pytest.raises(ValidationError):
        update_rule(
            decision=PolicyDecisionKind.ALLOW,
            risk_tier=RiskTier.R3,
        )
    with pytest.raises(ValidationError):
        update_rule(
            decision=PolicyDecisionKind.ALLOW,
            risk_tier=RiskTier.R2,
        )
    with pytest.raises(ValidationError):
        PolicySnapshot(
            reference_id=POLICY_REF,
            version="1.0.0",
            actor_id=ACTOR_ID,
            device_id=DEVICE_ID,
            default_decision=PolicyDecisionKind.ALLOW,
            default_risk_tier=RiskTier.R0,
        )
    with pytest.raises(ValidationError):
        snapshot(action_rules=(inspect_rule(), inspect_rule()))
    with pytest.raises(ValidationError):
        PolicyAggregateRule(
            rule_id="prl_unsafe001",
            capability_ids=("project.update",),
            minimum_matches=2,
            decision=PolicyDecisionKind.ALLOW,
            risk_tier=RiskTier.R2,
            reason_code="unsafe_combination",
        )
