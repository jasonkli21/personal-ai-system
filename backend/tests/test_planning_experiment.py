"""Narrowing contract exercised through canonical API composition and broker seams."""

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import ValidationError

from personal_ai.api.dependencies import get_application_context, get_context_assembler
from personal_ai.context.planner import ContextPlan, ContextPlanner, planning_digest
from personal_ai.context.planning_experiment import (
    ContextPlanProposal,
    create_planning_envelope,
    validate_planning_proposal,
)
from personal_ai.context.providers import ContextEntityReference, ContextPreparationError
from personal_ai.context.tokens import EstimatedTokenCounter
from personal_ai.entities import Message
from personal_ai.evaluation import planning
from tests.test_context_runtime_composition import APPLICATION_ID, SyntheticProvider, _app
from tests.test_federation import federation as federation_fixture
from tests.test_federation import prepare

broker_case = federation_fixture


def _experiment_app(*, body_mutator=None, authority_mutator=None):
    reference = ContextEntityReference(
        entity_type="record",
        entity_id="selected-record-1",
        application_id=APPLICATION_ID,
        workspace_id="workspace-1",
    )
    provider = SyntheticProvider(reference)
    app = _app(provider)

    @app.post("/planning-experiment")
    def experiment(
        body: dict,
        context=Depends(get_application_context),  # noqa: B008
        assembler=Depends(get_context_assembler),  # noqa: B008
    ):
        assembler.counter = EstimatedTokenCounter()
        baseline = assembler.plan_context(
            "Use the selected record.", context, candidate_entities=(reference,)
        )
        envelope = assembler.planning_envelope(
            baseline, context, deadline=datetime.now(UTC) + timedelta(seconds=1)
        )
        proposal = {"baseline_digest": envelope.request.baseline_digest, **body}
        if body_mutator:
            proposal = body_mutator(proposal)
        if authority_mutator:
            context = authority_mutator(context, provider)
        try:
            final = assembler.validate_context_proposal(envelope, proposal, context)
            before_fetch = provider.calls
            pending = Message(
                id=uuid4(),
                conversation_id=uuid4(),
                owner_id=context.scope.owner_id,
                application_id=context.scope.application_id,
                workspace_id=context.scope.workspace_id,
                role="user",
                content="Use the selected record.",
                status="completed",
                created_at=datetime.now(UTC),
            )
            result = assembler.assemble(
                (),
                pending,
                refresh=False,
                application_context=context,
                context_plan=final,
                emit_manifest=False,
            )
            from personal_ai.auth.scope import ApplicationScope
            from personal_ai.context.traces import ContextTraceManifest

            retained = ContextTraceManifest.from_build(
                result.manifest,
                request_id=context.scope.request_id,
                conversation_id=pending.conversation_id,
                user_message_id=pending.id,
                assistant_message_id=uuid4(),
                scope=ApplicationScope(
                    application_id=context.scope.application_id,
                    workspace_id=context.scope.workspace_id,
                ),
                context_plan=final,
            )
            retained = ContextTraceManifest.model_validate_json(retained.model_dump_json())
            return {
                "trace": final.planning_trace.model_dump(mode="json"),
                "retained_planning_trace": retained.planning_trace.model_dump(mode="json"),
                "request": envelope.request.model_dump(mode="json"),
                "sources": len(result.source_items),
                "before_fetch": before_fetch,
                "calls": provider.calls,
            }
        except ContextPreparationError as error:
            return {"denied": error.code, "calls": provider.calls}

    return app


def _choice(**updates):
    return {
        "choice_id": "choice-0",
        "fields": ["label"],
        "max_results": 1,
        "max_bytes": 1024,
        "max_tokens": 256,
        **updates,
    }


def test_canonical_planner_validation_retrieval_builder_and_privacy():
    response = TestClient(_experiment_app()).post(
        "/planning-experiment", json={"choices": [_choice()]}
    )
    result = response.json()
    assert result["calls"] == result["sources"] == 1
    assert result["before_fetch"] == 0
    trace = result["trace"]
    assert result["retained_planning_trace"] == trace
    assert trace["strategy"] == "validated_narrowing"
    assert trace["baseline_digest"] != trace["final_digest"]
    assert trace["proposal_digest"] and trace["proposal_choice_count"] == 1
    assert trace["baseline"][0]["max_bytes"] > trace["final"][0]["max_bytes"]
    assert trace["planner_calls"] == trace["planner_quota"] == 0
    serialized = json.dumps(result["request"]) + json.dumps(trace)
    for private in ("selected-record-1", "owner-1", "workspace-1", "Use the selected record"):
        assert private not in serialized


@pytest.mark.parametrize(
    "choice,reason",
    [
        (_choice(choice_id="choice-15"), "planning_unknown_or_duplicate_choice"),
        (_choice(fields=["private"]), "planning_field_outside_envelope"),
        (_choice(fields=["label", "label"]), "planning_field_outside_envelope"),
        (_choice(max_tokens=257), "planning_budget_outside_envelope"),
        (_choice(max_results=2), "planning_budget_outside_envelope"),
        (_choice(max_bytes=65536), "planning_budget_outside_envelope"),
        (_choice(entity_refs=[{"entity_id": "other"}]), "proposal_rejected"),
        (_choice(window_seconds=86400), "proposal_rejected"),
        (_choice(provider_id="finance.accounts"), "proposal_rejected"),
        (_choice(source_class="domain_history"), "proposal_rejected"),
        (_choice(selector={"type": "all"}), "proposal_rejected"),
    ],
)
def test_adversarial_proposals_return_current_control(choice, reason):
    result = (
        TestClient(_experiment_app())
        .post("/planning-experiment", json={"choices": [choice]})
        .json()
    )
    trace = result["trace"]
    assert trace["reasons"] == [reason]
    assert trace["baseline_digest"] == trace["final_digest"]
    assert result["calls"] == 1  # Only ordinary baseline retrieval, no planner fetch.


@pytest.mark.parametrize(
    "body",
    [
        {"choices": [_choice(), _choice()]},
        {"choices": [], "tools": ["search"]},
        {"choices": [], "schema_version": "unknown"},
        {"choices": [], "execution_mode": "BYOK"},
        {"choices": [], "recurse": True},
    ],
)
def test_no_tool_recursion_or_execution_mode_contract(body):
    result = TestClient(_experiment_app()).post("/planning-experiment", json=body).json()
    assert result["trace"]["strategy"] == "deterministic"
    assert result["trace"]["planner_calls"] == 0


@pytest.mark.parametrize(
    "identity", ["owner_id", "acting_user_id", "application_id", "workspace_id"]
)
def test_scope_changes_fail_closed_before_retrieval(identity):
    def mutate(context, provider):
        return context.model_copy(
            update={"scope": context.scope.model_copy(update={identity: "other"})}
        )

    result = (
        TestClient(_experiment_app(authority_mutator=mutate))
        .post("/planning-experiment", json={"choices": []})
        .json()
    )
    assert result == {"denied": "planning_scope_changed", "calls": 0}


def test_revoked_policy_cannot_fallback_to_historical_baseline():
    def mutate(context, provider):
        policy = context.definition.context_policy.model_copy(update={"provider_policies": ()})
        return context.model_copy(
            update={"definition": context.definition.model_copy(update={"context_policy": policy})}
        )

    result = (
        TestClient(_experiment_app(authority_mutator=mutate))
        .post("/planning-experiment", json={"choices": []})
        .json()
    )
    assert result["calls"] == 0 and result["denied"] == "context_policy_denied"


def test_provider_removed_cannot_fallback_to_unavailable_baseline():
    def mutate(context, provider):
        return context.model_copy(update={"context_provider_capabilities": ()})

    result = (
        TestClient(_experiment_app(authority_mutator=mutate))
        .post("/planning-experiment", json={"choices": []})
        .json()
    )
    assert result == {"denied": "planning_provider_unavailable", "calls": 0}


def test_empty_proposal_narrows_optional_baseline_without_retrieval():
    result = TestClient(_experiment_app()).post("/planning-experiment", json={"choices": []}).json()
    assert result["sources"] == result["calls"] == 0
    assert result["trace"]["final"] == []


def _federation_envelope(f):
    selection = f["selection"].model_copy(update={"max_tokens": 256})
    baseline = ContextPlan(
        planner_version=ContextPlanner.VERSION,
        scope_fingerprint=ContextPlan.fingerprint_scope(f["scope"]),
        application_id=f["scope"].application_id,
        workspace_id=f["scope"].workspace_id,
        selections=(selection,),
    )
    return create_planning_envelope(
        baseline,
        f["context"],
        f["coordinator"],
        configuration_digest=planning_digest("fixture"),
        deadline=datetime.now(UTC) + timedelta(seconds=1),
    )


@pytest.mark.parametrize("revocation", ["grant", "source_policy", "export", "expired"])
def test_federation_dependencies_revalidated_between_plan_and_validation(broker_case, revocation):
    f = broker_case
    envelope = _federation_envelope(f)
    assert f["adapter"].calls == 0
    if revocation == "grant":
        f["authority"].revoke(f["principal"], f["grant"].grant_id, expected_revision=1)
    elif revocation == "source_policy":
        f["source_policy"].current = False
    elif revocation == "export":
        f["adapter"].export_allowed = False
    else:
        f["repository"].records["owner", f["grant"].grant_id] = f["grant"].model_copy(
            update={"expires_at": datetime.now(UTC) - timedelta(seconds=1)}
        )
    with pytest.raises(ContextPreparationError):
        validate_planning_proposal(
            envelope,
            {"choices": [], "baseline_digest": envelope.request.baseline_digest},
            f["context"],
            f["coordinator"],
        )
    assert f["adapter"].calls == 0


def test_revocation_after_validated_plan_still_denies_retrieval(broker_case):
    f = broker_case
    envelope = _federation_envelope(f)
    final = validate_planning_proposal(
        envelope,
        {
            "baseline_digest": envelope.request.baseline_digest,
            "choices": [_choice(fields=["constraint"], max_results=10, max_bytes=16384)],
        },
        f["context"],
        f["coordinator"],
    )
    assert final.selections
    f["source_policy"].current = False
    with pytest.raises(ContextPreparationError):
        prepare({**f, "selection": final.selections[0]})
    assert f["adapter"].calls == 0


def test_timeout_and_malformed_output_are_traced_control(broker_case):
    f = broker_case
    envelope = _federation_envelope(f)
    for output, now, reason in (
        ({}, envelope.request.deadline, "planning_deadline_exceeded"),
        ({}, None, "proposal_rejected"),
    ):
        final = validate_planning_proposal(
            envelope, output, f["context"], f["coordinator"], now=now
        )
        assert final.planning_trace.reasons == (reason,)
        assert final.selections == envelope.baseline.selections
    with pytest.raises(ValidationError):
        ContextPlanProposal.model_validate(
            {"baseline_digest": "a" * 64, "choices": [], "credentials": "secret"}
        )


def test_frozen_baseline_and_no_promotion_without_measurements():
    result = planning.evaluate()
    assert result["decision"] == "non_promotion"
    assert result["model_answer_quality"] is None
    assert result["assisted_comparison"] is None
    assert result["promoted_coverage"] == []
    assert result["planner_calls"] == result["planner_quota"] == 0
    classes = {row["failure_class"] for row in result["rows"]}
    assert {"lexical_omission", "irrelevant_selection", "required_source_denial"} <= classes


def test_required_selections_cannot_be_removed_or_reduced(broker_case):
    f = broker_case
    selection = f["selection"].model_copy(update={"max_tokens": 256, "required": True})
    plan = ContextPlan(
        planner_version=ContextPlanner.VERSION,
        scope_fingerprint=ContextPlan.fingerprint_scope(f["scope"]),
        application_id=f["scope"].application_id,
        workspace_id=f["scope"].workspace_id,
        selections=(selection,),
    )
    envelope = create_planning_envelope(
        plan,
        f["context"],
        f["coordinator"],
        configuration_digest=planning_digest("fixture"),
        deadline=datetime.now(UTC) + timedelta(seconds=1),
    )
    for choices, reason in (
        ([], "planning_required_choice_omitted"),
        ([_choice(fields=["constraint"], max_results=10)], "planning_required_choice_narrowed"),
    ):
        final = validate_planning_proposal(
            envelope,
            {"baseline_digest": envelope.request.baseline_digest, "choices": choices},
            f["context"],
            f["coordinator"],
        )
        assert final.selections == plan.selections
        assert final.planning_trace.reasons == (reason,)


def test_promotion_thresholds_reject_missing_overhead_and_hard_regressions():
    from personal_ai.evaluation.planning_promotion import PlanningMeasurements, promotion_reasons

    control = PlanningMeasurements(
        families=100,
        omission_rate=0.3,
        irrelevant_rate=0.02,
        supported_answer_rate=0.7,
        total_tokens=1000,
        total_quota=1000,
        p95_latency_ms=1000,
        planner_p95_latency_ms=0,
        rollback_verified=True,
    )
    candidate = control.model_copy(
        update={
            "omission_rate": 0.15,
            "supported_answer_rate": 0.8,
            "planner_p95_latency_ms": 400,
            "total_tokens": 1050,
            "total_quota": 1050,
            "p95_latency_ms": 1100,
            "max_extra_calls": 1,
        }
    )
    assert promotion_reasons(control, candidate) == ()
    for update, reason in (
        ({"authority_violations": 1}, "hard_invariant_regression"),
        ({"non_strict_free_dispatches": 1}, "hard_invariant_regression"),
        ({"total_quota": 1101}, "excess_total_quota"),
        ({"supported_answer_rate": None}, "unmeasured_model_answer_quality"),
        ({"rollback_verified": False}, "rollback_unverified"),
        ({"families": 99}, "insufficient_heldout_families"),
    ):
        assert reason in promotion_reasons(control, candidate.model_copy(update=update))


def test_zero_inference_budget_cannot_be_changed_by_configuration_or_model():
    from personal_ai.context.planning_experiment import PlanningRequest

    result = TestClient(_experiment_app()).post("/planning-experiment", json={"choices": []}).json()
    for update in ({"planner_calls": 1}, {"planner_tokens": 1}, {"execution_mode": "BYOK"}):
        with pytest.raises(ValidationError):
            PlanningRequest.model_validate({**result["request"], **update})


def test_large_installed_catalog_is_not_a_planning_disclosure_catalog():
    from personal_ai.context.runtime import ContextRuntimeRegistry

    app = _experiment_app()
    runtime = app.state.context_runtime_registry
    providers = dict(runtime.provider_factories)
    for index in range(200):
        provider = SyntheticProvider(
            ContextEntityReference(
                entity_type="record", entity_id=f"private-{index}", application_id=APPLICATION_ID
            )
        )
        provider.spec = provider.spec.model_copy(update={"provider_id": f"other.provider_{index}"})
        providers[provider.spec.provider_id] = provider
    app.state.context_runtime_registry = ContextRuntimeRegistry(providers, runtime.planning_rules)
    result = TestClient(app).post("/planning-experiment", json={"choices": []}).json()
    assert len(result["request"]["choices"]) == 1
    assert "other.provider" not in json.dumps(result)
    assert result["calls"] == 0


def test_sensitivity_ceiling_is_checked_before_experiment_metadata(broker_case):
    f = broker_case
    envelope = _federation_envelope(f)
    with pytest.raises(ContextPreparationError, match="context_mode_sensitivity_denied"):
        create_planning_envelope(
            envelope.baseline,
            f["context"],
            f["coordinator"],
            configuration_digest=planning_digest("fixture"),
            deadline=envelope.request.deadline,
            maximum_sensitivity="public",
        )
    assert f["adapter"].calls == 0
