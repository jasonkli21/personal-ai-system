"""Closed policy and redacted result for a single automatic continuation."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import Field

from .catalog import CATALOG_VERSION
from .proposed_request import Budget, Closed, ReasoningRequest

Effort = Literal["low", "medium", "high", "max"]
RequestedEffort = Literal["auto", "low", "medium", "high", "max"]
EFFORTS: tuple[Effort, ...] = ("low", "medium", "high", "max")
POLICY_VERSION = "reasoning-direct-policy-v1"
OBSERVATION_VERSION = "reasoning-observation-v2"

Narrowing = Literal["policy", "budget", "capability", "source", "quota", "unavailable"]
Stop = Literal[
    "sufficient", "budget_exhausted", "policy_denied", "unsupported", "provider_unavailable",
    "cancelled", "uncertain_effect", "internal_failure",
]


class Observation(Closed):
    schema_version: Literal["reasoning-observation-v2"] = OBSERVATION_VERSION
    policy_version: Literal["reasoning-direct-policy-v1"] = POLICY_VERSION
    catalog_version: Literal["reasoning-catalog-v1"] = CATALOG_VERSION
    strategy: Literal["direct"] = "direct"
    requested_effort: RequestedEffort
    effective_effort: Effort | None = None
    narrowing_reasons: tuple[Narrowing, ...] = Field(default=(), max_length=6)
    native_control: Literal["applied", "not_applied", "unsupported"] = "not_applied"
    capability_version: Literal["fake-native-effort-v1"] | None = None
    provider_acknowledged: bool | None = None
    native_reasoning_observed: Literal["unknown"] = "unknown"
    status: Literal["complete", "partial", "unavailable"]
    stop_reason: Stop
    replayed: bool = False
    model_attempts: int | None = Field(default=None, ge=0, le=1)
    model_reservations: int | None = Field(default=None, ge=0, le=1)
    model_settlements: int | None = Field(default=None, ge=0, le=1)
    count_attempts: int | None = Field(default=None, ge=0)
    count_reservations: int | None = Field(default=None, ge=0)
    count_settlements: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    usage_confidence: Literal["estimated", "observed", "unknown"] = "unknown"
    reserved_input_tokens: int | None = Field(default=None, ge=0)
    reserved_output_tokens: int | None = Field(default=None, ge=0)
    cost_class: Literal["synthetic_no_charge", "local_no_provider_charge", "unknown"] = "unknown"
    quota_state: Literal["admitted", "denied", "unknown"] = "unknown"
    elapsed_ms: int | None = Field(default=None, ge=0)


class ReasoningDenied(Exception):
    def __init__(self, observation: Observation):
        self.observation = observation
        super().__init__(observation.stop_reason)


def deny(
    request: ReasoningRequest, stop: Stop, reason: Narrowing, *, unsupported: bool = False,
) -> None:
    raise ReasoningDenied(Observation(
        requested_effort=request.effort, status="unavailable", stop_reason=stop,
        narrowing_reasons=(reason,), native_control="unsupported" if unsupported else "not_applied",
        model_attempts=0, model_reservations=0, model_settlements=0,
        count_attempts=0, count_reservations=0, count_settlements=0,
    ))


@dataclass(frozen=True, slots=True)
class Ceilings:
    operator: Effort
    application: Effort
    workspace: Effort
    user: Effort
    endpoint: Effort


@dataclass(frozen=True, slots=True)
class DirectPolicy:
    requested: RequestedEffort
    ceiling: Effort
    budget: Budget
    reasons: tuple[Narrowing, ...]


def has_generation_receipt(generation_metadata) -> bool:
    if generation_metadata is None:
        return False
    try:
        UUID(generation_metadata.invocation_id)
        if len(generation_metadata.attempt_ids) != 1:
            return False
        UUID(generation_metadata.attempt_ids[0])
        return True
    except (TypeError, ValueError, AttributeError):
        return False


def resolve_policy(
    request: ReasoningRequest,
    *,
    enabled: bool,
    ceilings: Ceilings,
    input_limit: int,
    output_limit: int,
    elapsed_limit: int,
    count_reservation: int,
) -> DirectPolicy:
    if not enabled:
        deny(request, "policy_denied", "policy")
    if request.strategy != "auto" or request.research != "off":
        deny(request, "unsupported", "policy", unsupported=True)

    requested: Effort = "low" if request.effort == "auto" else request.effort
    ceiling = min(
        (requested, ceilings.operator, ceilings.application, ceilings.workspace, ceilings.user,
         ceilings.endpoint),
        key=EFFORTS.index,
    )
    reasons: tuple[Narrowing, ...] = ("policy",) if ceiling != requested else ()
    budget = request.budget
    bounded = Budget(
        max_model_calls=min(1, budget.max_model_calls),
        max_concurrency=min(1, budget.max_concurrency),
        max_elapsed_seconds=min(budget.max_elapsed_seconds, elapsed_limit),
        max_input_tokens=min(budget.max_input_tokens, input_limit),
        max_output_tokens=min(budget.max_output_tokens, output_limit),
    )
    if not all((
        bounded.max_model_calls, bounded.max_concurrency, bounded.max_elapsed_seconds,
        bounded.max_input_tokens, bounded.max_output_tokens,
    )) or budget.max_input_tokens < count_reservation:
        deny(request, "budget_exhausted", "budget")
    if bounded != budget:
        reasons += ("budget",)
    return DirectPolicy(request.effort, ceiling, bounded, reasons)


class TurnObservation:
    """Request-local policy plus diagnostics; generation receipts establish attempts."""

    def __init__(self, policy: DirectPolicy, started: float, request_id: str):
        self.policy = policy
        self.started = started
        self.request_id = request_id
        self.effective: Effort = "low"
        self.capability = None
        self.native_applied = False
        self.events: dict[tuple, int] = {}

    def record(self, event, state, facts):
        operation = facts.get("operation")
        if operation not in {"streaming", "token_counting"}:
            return
        key = (operation, event, state)
        self.events[key] = self.events.get(key, 0) + 1

    def count(self, operation, event, state="ok"):
        return self.events.get((operation, event, state), 0)

    def result(
        self, *, complete=False, partial=False, stop: Stop | None = None, usage=None,
        generation_metadata=None,
    ):
        from time import monotonic

        receipt_known = has_generation_receipt(generation_metadata)
        attempted = len(generation_metadata.attempt_ids) if receipt_known else None
        complete = bool(
            complete and receipt_known and attempted == 1
            and generation_metadata.status == "success"
        )
        reasons = self.policy.reasons
        if self.effective != self.policy.ceiling or (not self.capability and self.policy.ceiling != "low"):
            reasons += ("capability",)
        if stop is None:
            if complete:
                stop = "sufficient"
            elif attempted is None:
                stop = "uncertain_effect"
            else:
                stop = "provider_unavailable"
        if not complete and attempted is None and stop == "sufficient":
            stop = "uncertain_effect"
        native_applied = self.native_applied and attempted == 1
        return Observation(
            requested_effort=self.policy.requested,
            effective_effort=self.effective if attempted == 1 else None,
            narrowing_reasons=reasons,
            native_control="applied" if native_applied else "not_applied",
            capability_version=self.capability if native_applied else None,
            status="complete" if complete else "partial" if partial else "unavailable",
            stop_reason=stop, model_attempts=attempted,
            model_reservations=None,
            model_settlements=None,
            count_attempts=None,
            count_reservations=None,
            count_settlements=None,
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
            usage_confidence=(
                "observed" if usage and usage.confidence == "reported" else
                "estimated" if usage and usage.confidence == "estimated" else "unknown"
            ),
            reserved_input_tokens=None,
            reserved_output_tokens=None,
            cost_class=(
                "synthetic_no_charge"
                if receipt_known and generation_metadata.identity.provider_id == "offline_fake"
                else "unknown"
            ),
            quota_state="unknown",
            elapsed_ms=int((monotonic() - self.started) * 1000),
        )
