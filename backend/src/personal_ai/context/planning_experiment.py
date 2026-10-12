"""Non-promoted, narrowing-only experiment contract over canonical context plans.

No inference client, tools, search, database or source fetch exists here. Exact
selection identities stay in a request-local server envelope. Historical envelopes
are never permission: validation repeats shared current authority checks and normal
provider/builder revalidation still applies after validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from personal_ai.applications.contracts import ApplicationContextRequest, ContextSensitivity
from personal_ai.context.authorization import (
    authorize_context_selection,
    authorize_context_selections,
)
from personal_ai.context.planner import (
    ContextPlan,
    PlanningSelectionSummary,
    PlanningTrace,
    planning_digest,
)
from personal_ai.context.providers import (
    ContextOperation,
    ContextPreparationError,
    ContextProviderCoordinator,
)
from personal_ai.contracts.context_categories import ContextSourceClass

PlanningField = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{0,79}$", max_length=80)]


class PlanningChoice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    choice_id: str = Field(pattern=r"^choice-[0-9]{1,2}$")
    provider_id: str = Field(max_length=81)
    source_class: ContextSourceClass
    operation: ContextOperation
    sensitivity: ContextSensitivity
    selector: Literal["server_bound"] = "server_bound"
    categories: tuple[str, ...] = Field(default=(), max_length=64)
    fields: tuple[PlanningField, ...] = Field(max_length=32)
    entity_types: tuple[str, ...] = Field(max_length=16)
    entity_count: int = Field(ge=0, le=16)
    window_seconds: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    max_results: int = Field(ge=1, le=50)
    max_bytes: int = Field(ge=1, le=65_536)
    max_tokens: int = Field(ge=1, le=128_000)
    required: bool
    source_version: str = Field(max_length=100)
    dependency_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class PlanningRequest(BaseModel):
    """Minimized metadata; opaque choices bind exact scopes/entities/windows/grants."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["planning-request-v1"] = "planning-request-v1"
    strategy_version: Literal["narrowing-experiment-v1"] = "narrowing-experiment-v1"
    scope_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    application_id: str = Field(max_length=42)
    workspace_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    task: Literal["context_selection"] = "context_selection"
    requirements: tuple[Literal["preserve_required", "narrow_only"], ...] = (
        "preserve_required",
        "narrow_only",
    )
    baseline_version: str = Field(max_length=100)
    baseline_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    configuration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_version: str = Field(max_length=100)
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    maximum_sensitivity: ContextSensitivity
    choices: tuple[PlanningChoice, ...] = Field(max_length=16)
    token_budget: int = Field(ge=0)
    item_budget: int = Field(ge=0)
    byte_budget: int = Field(ge=0)
    deadline: datetime
    planner_calls: Literal[0] = 0
    planner_tokens: Literal[0] = 0
    execution_mode: Literal["STRICT_FREE"] = "STRICT_FREE"

    @field_validator("deadline")
    @classmethod
    def deadline_is_aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("planning_deadline_timezone_required")
        return value.astimezone(UTC)


class ProposedChoice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    choice_id: str = Field(pattern=r"^choice-[0-9]{1,2}$")
    fields: tuple[PlanningField, ...] = Field(max_length=32)
    max_results: int = Field(ge=1, le=50)
    max_bytes: int = Field(ge=1, le=65_536)
    max_tokens: int = Field(ge=1, le=128_000)


class ContextPlanProposal(BaseModel):
    """Non-authoritative output; unknown selectors/windows/providers are extra keys."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["context-plan-proposal-v1"] = "context-plan-proposal-v1"
    baseline_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    choices: tuple[ProposedChoice, ...] = Field(max_length=16)
    reason: Literal["retain", "reduce_overfetch"] = "retain"


@dataclass(frozen=True)
class PlanningEnvelope:
    """Server-held request-local binding, never accepted from an API or a model."""

    request: PlanningRequest
    baseline: ContextPlan
    context: ApplicationContextRequest
    spec_digests: tuple[str, ...]


def _current_selections(plan, context, coordinator, maximum_sensitivity):
    if (
        plan.scope_fingerprint != ContextPlan.fingerprint_scope(context.scope)
        or plan.application_id != context.scope.application_id
        or plan.workspace_id != context.scope.workspace_id
    ):
        raise ContextPreparationError("planning_scope_changed")
    authorize_context_selections(context, plan.selections, maximum_sensitivity=maximum_sensitivity)
    specs = []
    for selection in plan.selections:
        capability = coordinator.planning_capability(context, selection.provider_id)
        if capability.status != "available":
            raise ContextPreparationError("planning_provider_unavailable")
        spec = capability.spec
        operation = spec.operation(selection.operation)
        if operation is None:
            raise ContextPreparationError("planning_operation_changed")
        coordinator.validate_operation_bounds(selection, spec, operation)
        specs.append(spec)
    coordinator.authorize_boundaries(plan.selections, context.scope)
    return tuple(specs)


def create_planning_envelope(
    baseline: ContextPlan,
    context: ApplicationContextRequest,
    coordinator: ContextProviderCoordinator,
    *,
    configuration_digest: str,
    deadline: datetime,
    maximum_sensitivity: ContextSensitivity | None = None,
) -> PlanningEnvelope:
    if deadline.tzinfo is None or deadline.utcoffset() is None:
        raise ValueError("planning_deadline_timezone_required")
    ceiling = maximum_sensitivity or context.definition.context_policy.maximum_model_sensitivity
    specs = _current_selections(baseline, context, coordinator, ceiling)
    choices = tuple(
        PlanningChoice(
            choice_id=f"choice-{index}",
            provider_id=selection.provider_id,
            source_class=spec.source_class,
            operation=selection.operation,
            sensitivity=authorize_context_selection(
                context, selection, maximum_sensitivity=ceiling
            ),
            categories=tuple(
                sorted(
                    {
                        decision.category
                        for decision in baseline.decisions
                        if decision.provider_id == selection.provider_id
                        and decision.operation == selection.operation
                    }
                )
            ),
            fields=selection.fields,
            entity_types=tuple(sorted({ref.entity_type for ref in selection.entity_refs})),
            entity_count=len(selection.entity_refs),
            window_seconds=(
                (selection.window_end - selection.window_start).total_seconds()
                if selection.window_start
                else None
            ),
            max_results=selection.max_results,
            max_bytes=selection.max_bytes,
            max_tokens=selection.max_tokens or 1,
            required=selection.required,
            source_version=spec.source_version,
            dependency_digest=planning_digest(selection),
        )
        for index, (selection, spec) in enumerate(zip(baseline.selections, specs, strict=True))
    )
    # Unbounded legacy allocations cannot be represented by this experiment.
    if any(selection.max_tokens is None for selection in baseline.selections):
        raise ContextPreparationError("planning_unbounded_selection")
    request = PlanningRequest(
        scope_fingerprint=baseline.scope_fingerprint,
        application_id=baseline.application_id,
        workspace_digest=planning_digest(baseline.workspace_id) if baseline.workspace_id else None,
        baseline_version=baseline.planner_version,
        baseline_digest=planning_digest(baseline),
        configuration_digest=configuration_digest,
        policy_version=context.definition.context_policy.version,
        policy_digest=planning_digest(context.definition.context_policy),
        maximum_sensitivity=ceiling,
        choices=choices,
        token_budget=sum(choice.max_tokens for choice in choices),
        item_budget=sum(choice.max_results for choice in choices),
        byte_budget=sum(choice.max_bytes for choice in choices),
        deadline=deadline.astimezone(UTC),
    )
    return PlanningEnvelope(
        request, baseline, context, tuple(planning_digest(spec) for spec in specs)
    )


def validate_planning_proposal(
    envelope: PlanningEnvelope,
    proposal: object,
    context: ApplicationContextRequest,
    coordinator: ContextProviderCoordinator,
    *,
    now: datetime | None = None,
) -> ContextPlan:
    """Return a narrowed final plan or currently authorized control; never widen.

    If the baseline itself is revoked, denial propagates instead of returning
    historical permission. No external send/retry or source retrieval occurs.
    """
    request, baseline = envelope.request, envelope.baseline
    specs = _current_selections(baseline, context, coordinator, request.maximum_sensitivity)
    # Re-check the entire server-owned policy, not only a coarse version label.
    if planning_digest(context.definition.context_policy) != request.policy_digest:
        raise ContextPreparationError("planning_policy_changed")
    if tuple(planning_digest(spec) for spec in specs) != envelope.spec_digests:
        raise ContextPreparationError("planning_provider_configuration_changed")
    reason = "proposal_rejected"
    parsed = None
    try:
        current_time = now or datetime.now(UTC)
        if current_time.tzinfo is None or current_time.utcoffset() is None:
            raise ValueError("planning_clock_timezone_required")
        if current_time >= request.deadline:
            reason = "planning_deadline_exceeded"
            raise ValueError(reason)
        parsed = ContextPlanProposal.model_validate(proposal)
        if parsed.baseline_digest != request.baseline_digest:
            reason = "planning_baseline_mismatch"
            raise ValueError(reason)
        allowed = {
            choice.choice_id: (choice, selection)
            for choice, selection in zip(request.choices, baseline.selections, strict=True)
        }
        ids = [choice.choice_id for choice in parsed.choices]
        if len(ids) != len(set(ids)) or set(ids) - allowed.keys():
            reason = "planning_unknown_or_duplicate_choice"
            raise ValueError(reason)
        if any(choice.required and choice.choice_id not in ids for choice in request.choices):
            reason = "planning_required_choice_omitted"
            raise ValueError(reason)
        selections = []
        for choice in parsed.choices:
            cap, selection = allowed[choice.choice_id]
            if len(set(choice.fields)) != len(choice.fields) or set(choice.fields) - set(
                cap.fields
            ):
                reason = "planning_field_outside_envelope"
                raise ValueError(reason)
            if (
                choice.max_tokens > cap.max_tokens
                or choice.max_bytes > cap.max_bytes
                or choice.max_results > cap.max_results
            ):
                reason = "planning_budget_outside_envelope"
                raise ValueError(reason)
            if selection.required and (
                choice.fields != selection.fields
                or choice.max_tokens != cap.max_tokens
                or choice.max_bytes != cap.max_bytes
                or choice.max_results != cap.max_results
            ):
                reason = "planning_required_choice_narrowed"
                raise ValueError(reason)
            selections.append(
                selection.model_copy(
                    update={
                        "fields": choice.fields,
                        "max_tokens": choice.max_tokens,
                        "max_results": choice.max_results,
                        "max_bytes": choice.max_bytes,
                    }
                )
            )
        budgets = {}
        for selection in selections:
            spec = coordinator.planning_capability(context, selection.provider_id).spec
            budgets[spec.source_class] = budgets.get(spec.source_class, 0) + selection.max_tokens
        selected = {
            (selection.provider_id, selection.operation): selection for selection in selections
        }
        decisions = tuple(
            decision.model_copy(
                update={
                    "disposition": "selected"
                    if (decision.provider_id, decision.operation) in selected
                    else "omitted",
                    "fields": tuple(
                        field
                        for field in decision.fields
                        if field in selected[(decision.provider_id, decision.operation)].fields
                    )
                    if (decision.provider_id, decision.operation) in selected
                    else (),
                    "reason": "validated_narrowing",
                }
            )
            if decision.disposition == "selected"
            else decision
            for decision in baseline.decisions
        )
        final = ContextPlan.model_validate(
            {
                **baseline.model_dump(),
                "selections": tuple(selections),
                "source_token_budgets": tuple(sorted(budgets.items())),
                "decisions": decisions,
            }
        )
        _current_selections(final, context, coordinator, request.maximum_sensitivity)
        return _traced(baseline, final, request, parsed, "proposal_validated")
    except (ValidationError, ValueError, ContextPreparationError):
        _current_selections(baseline, context, coordinator, request.maximum_sensitivity)
        return _traced(baseline, baseline, request, parsed, reason)


def _traced(baseline, final, request, proposal, reason):
    return final.model_copy(
        update={
            "planning_trace": PlanningTrace(
                strategy="validated_narrowing"
                if reason == "proposal_validated"
                else "deterministic",
                configuration_digest=request.configuration_digest,
                baseline_digest=planning_digest(baseline),
                final_digest=planning_digest(final),
                proposal_digest=planning_digest(proposal) if proposal else None,
                baseline=tuple(
                    PlanningSelectionSummary.from_selection(s) for s in baseline.selections
                ),
                final=tuple(PlanningSelectionSummary.from_selection(s) for s in final.selections),
                proposal_choice_count=len(proposal.choices) if proposal else None,
                reasons=(reason,),
            )
        }
    )
