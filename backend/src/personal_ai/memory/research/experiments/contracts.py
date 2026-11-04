"""Bounded, versioned portable research metadata. Hashes confer no authority."""

import json
from hashlib import sha256
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identity = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{0,99}$")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Arm = Literal[
    "no_memory",
    "full_history",
    "fixed",
    "verified_knowledge",
    "tool_lookup",
    "pending_diagnostic",
    "lexical",
    "topic_hierarchical",
    "adaptive",
    "semantic",
    "hybrid",
    "hybrid_reranked",
]
ARMS = tuple(Arm.__args__)
Family = Literal["transfer", "revision", "correction", "rights", "poison", "resources"]
Split = Literal["development", "validation_author_visible", "challenge_author_visible"]
Status = Literal[
    "setup",
    "complete",
    "unsupported",
    "denied",
    "incomplete",
    "timed_out",
    "cancelled",
    "error",
]


def canonical(value) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value) -> str:
    return sha256(canonical(value)).hexdigest()


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    @model_validator(mode="after")
    def bounded(self):
        if len(canonical(self)) > 65536:
            raise ValueError("research_record_capacity")
        return self


class SourceHash(Record):
    path: Annotated[str, Field(pattern=r"^[a-zA-Z0-9_./-]{1,240}$")]
    sha256: Digest

    @model_validator(mode="after")
    def relative(self):
        if self.path.startswith("/") or ".." in self.path.split("/"):
            raise ValueError("source_path_invalid")
        return self


class DatasetManifest(Record):
    version: Literal["memory-longitudinal-dataset-v1"] = "memory-longitudinal-dataset-v1"
    dataset_id: Identity
    provenance: Literal["public_synthetic"] = "public_synthetic"
    consent: Literal["synthetic_no_personal_data"] = "synthetic_no_personal_data"
    fixture_sha256: Digest
    source_sha256: Digest
    scorer_sha256: Digest
    source_snapshot: Identity
    observed_at: Literal["2026-10-29T12:00:00+00:00"] = "2026-10-29T12:00:00+00:00"
    eligibility_policy: Literal["current_scope_source_epoch_and_tombstone"] = (
        "current_scope_source_epoch_and_tombstone"
    )
    splits: tuple[Split, ...] = Field(min_length=3, max_length=3)
    families: tuple[Family, ...] = Field(min_length=6, max_length=6)
    scoring_seal: Digest
    contamination: Literal["all_splits_author_visible"] = "all_splits_author_visible"
    cases: int = Field(ge=48, le=96)


class TaskManifest(Record):
    """Policy-visible task identity, without rubric, family, split or fault labels."""

    version: Literal["memory-longitudinal-task-v1"] = "memory-longitudinal-task-v1"
    task_id: Identity
    subject: Identity
    workspace: Identity
    actor: Identity
    sessions: tuple[Identity, ...] = Field(min_length=2, max_length=4)
    temporal_order: tuple[int, ...] = Field(min_length=3, max_length=4)
    permission_timeline_sha256: Digest
    source_timeline_sha256: Digest
    tools: tuple[Literal["discover", "apply", "current"], ...] = ("current", "discover", "apply")
    effects: Literal["simulated_terminal_state_only"] = "simulated_terminal_state_only"
    scorer_reference: Digest

    @model_validator(mode="after")
    def order(self):
        if self.temporal_order != tuple(range(len(self.temporal_order))):
            raise ValueError("task_order_invalid")
        return self


class ModelManifest(Record):
    version: Literal["memory-research-model-v1"] = "memory-research-model-v1"
    mode: Literal["scripted_no_transport", "protocol_only"] = "scripted_no_transport"
    provider: Identity | None = None
    endpoint: (
        Annotated[str, Field(pattern=r"^http://(localhost|127\.0\.0\.1|\[::1\])(:[0-9]{1,5})?/?$")]
        | None
    ) = None
    model: Identity | None = None
    build: Identity | None = None
    weights_sha256: Digest | None = None
    tokenizer: Identity = "fixture_word_estimate"
    configuration_sha256: Digest
    temperature: float | None = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    seed: int = Field(ge=0, le=2**31 - 1)
    capability: Literal["deterministic_action_proxy", "not_observed"] = "deterministic_action_proxy"
    privacy: Literal["public_synthetic_only"] = "public_synthetic_only"
    cost_profile: Literal["no_transport", "not_observed"] = "no_transport"
    actual_model_tokens: None = None
    billed_cost: None = None

    @model_validator(mode="after")
    def model_space(self):
        if self.mode == "scripted_no_transport":
            if (
                any(
                    v is not None
                    for v in (
                        self.provider,
                        self.endpoint,
                        self.model,
                        self.build,
                        self.weights_sha256,
                        self.temperature,
                    )
                )
                or self.tokenizer != "fixture_word_estimate"
                or self.capability != "deterministic_action_proxy"
                or self.cost_profile != "no_transport"
            ):
                raise ValueError("scripted_model_space_invalid")
        elif (
            self.model is None
            or self.provider is None
            or self.capability != "not_observed"
            or self.cost_profile != "not_observed"
        ):
            raise ValueError("unobserved_model_protocol_required")
        return self


class MemoryPolicyManifest(Record):
    version: Literal["memory-research-policy-v1"] = "memory-research-policy-v1"
    policy_id: Identity
    arm: Arm
    capture: Literal["sealed_fixture_only"] = "sealed_fixture_only"
    knowledge: Literal["canonical_service_when_compatible"] = "canonical_service_when_compatible"
    episodes: Literal["disabled"] = "disabled"
    consolidation: Literal["pending_diagnostic_only"] = "pending_diagnostic_only"
    index: Literal["bounded_fixture_or_none"] = "bounded_fixture_or_none"
    selection: Identity
    context_allocation: Literal["canonical_builder"] = "canonical_builder"
    flags: tuple[Literal["offline_explicit_opt_in"], ...] = ("offline_explicit_opt_in",)
    parameter_sha256: Digest


class Budgets(Record):
    context_tokens: int = Field(default=4096, ge=64, le=4096)
    memory_tokens: int = Field(default=1024, ge=1, le=1024)
    output_tokens: Literal[0] = 0
    tool_calls: int = Field(default=2, ge=1, le=4)
    deadline_seconds: float = Field(default=2, gt=0, le=2, allow_inf_nan=False)
    corpus_bytes: int = Field(default=262144, ge=1, le=262144)
    artifact_bytes: int = Field(default=16_777_216, ge=1, le=16_777_216)


class Contrast(Record):
    baseline: Arm
    candidate: Arm

    @model_validator(mode="after")
    def distinct(self):
        if self.baseline == self.candidate:
            raise ValueError("contrast_identity")
        return self


class Protocol(Record):
    version: Literal["memory-longitudinal-protocol-v1"] = "memory-longitudinal-protocol-v1"
    hypothesis: Literal["current_memory_improves_new_terminal_actions"] = (
        "current_memory_improves_new_terminal_actions"
    )
    primary: Contrast
    secondary: tuple[Contrast, ...] = Field(max_length=5)
    estimand: Literal["paired_final_task_b_success_by_scenario"] = (
        "paired_final_task_b_success_by_scenario"
    )
    minimum_effect_pp: float = Field(default=5, ge=0, le=100, allow_inf_nan=False)
    maximum_family_regression_pp: float = Field(default=0, ge=0, le=100, allow_inf_nan=False)
    bootstrap_seed: int = Field(default=719, ge=0, le=2**31 - 1)
    bootstrap_samples: int = Field(default=1000, ge=100, le=5000)
    interval: Literal["scenario_cluster_percentile_95"] = "scenario_cluster_percentile_95"
    multiplicity: Literal["primary_only_secondary_descriptive_no_significance_claim"] = (
        "primary_only_secondary_descriptive_no_significance_claim"
    )
    exclusions: Literal["unsupported_or_incomplete_pairs_reported_never_imputed"] = (
        "unsupported_or_incomplete_pairs_reported_never_imputed"
    )
    repetition_seeds: tuple[int, ...] = Field(min_length=2, max_length=2)
    critical_threshold: Literal[0] = 0
    budgets: Budgets = Budgets()


class EnvironmentManifest(Record):
    python: Annotated[str, Field(max_length=32)]
    platform: Annotated[str, Field(max_length=200)]
    machine: Annotated[str, Field(max_length=40)]
    pydantic: Annotated[str, Field(max_length=32)]
    native: Literal["not_observed"] = "not_observed"
    model_transport: Literal["disabled"] = "disabled"


class RunManifest(Record):
    version: Literal["memory-longitudinal-run-v1"] = "memory-longitudinal-run-v1"
    revision: Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")]
    dirty: bool
    source_hashes: tuple[SourceHash, ...] = Field(min_length=1, max_length=128)
    dataset: DatasetManifest
    model: ModelManifest
    policies: tuple[MemoryPolicyManifest, ...] = Field(min_length=1, max_length=12)
    protocol: Protocol
    parser: Literal["strict_pydantic_bounded_json"] = "strict_pydantic_bounded_json"
    serializer: Literal["canonical_sorted_json_sha256"] = "canonical_sorted_json_sha256"
    environment: EnvironmentManifest
    evidence_tier: Literal["E1"] = "E1"
    attempt_identity: Literal["task_arm_repetition_step_original_intent"] = (
        "task_arm_repetition_step_original_intent"
    )
    preregistration: Literal["author_locked_before_measurement"] = (
        "author_locked_before_measurement"
    )

    @model_validator(mode="after")
    def unique(self):
        if self.model.mode != "scripted_no_transport":
            raise ValueError("model_dispatch_not_authorized")
        if len({p.path for p in self.source_hashes}) != len(self.source_hashes):
            raise ValueError("duplicate_source")
        if len({p.arm for p in self.policies}) != len(self.policies):
            raise ValueError("duplicate_policy")
        arms = {p.arm for p in self.policies}
        if any(
            c.baseline not in arms or c.candidate not in arms
            for c in (self.protocol.primary, *self.protocol.secondary)
        ):
            raise ValueError("unregistered_contrast")
        return self


class ResourceCounters(Record):
    fixture_token_estimate: int = Field(default=0, ge=0, le=4096)
    memory_token_estimate: int = Field(default=0, ge=0, le=1024)
    tool_calls: int = Field(default=0, ge=0, le=4)
    provider_calls: Literal[0] = 0
    actual_tokens: None = None
    billed_cost: None = None
    maintenance_calls: int = Field(default=0, ge=0, le=128)
    index_bytes: int = Field(default=0, ge=0, le=262144)
    retained_bytes: int = Field(default=0, ge=0, le=262144)
    elapsed_ms: float = Field(default=0, ge=0, allow_inf_nan=False)
    index_build_ms: float = Field(default=0, ge=0, allow_inf_nan=False)
    retrieval_ms: float = Field(default=0, ge=0, allow_inf_nan=False)
    packing_ms: float = Field(default=0, ge=0, allow_inf_nan=False)
    consumption_ms: float = Field(default=0, ge=0, allow_inf_nan=False)


class AttemptReceipt(Record):
    version: Literal["memory-longitudinal-attempt-v1"] = "memory-longitudinal-attempt-v1"
    run_sha256: Digest
    task_id: Identity
    arm: Arm
    repetition: int = Field(ge=0, le=1)
    seed: int = Field(ge=0, le=2**31 - 1)
    time_step: int = Field(ge=0, le=3)
    session: Identity
    original_intent: Digest
    retry_of: Digest | None = None
    status: Status
    reason: Identity
    source_epoch: int = Field(ge=1, le=1000000)
    permission_epoch: int = Field(ge=1, le=1000000)
    selected: tuple[Identity, ...] = Field(default=(), max_length=128)
    packed: tuple[Identity, ...] = Field(default=(), max_length=128)
    consumed: tuple[Identity, ...] = Field(default=(), max_length=128)
    terminal_state_sha256: Digest | None = None
    observed_action: Identity | None = None
    effect_count: int = Field(default=0, ge=0, le=4)
    abstained: bool = False
    rediscoveries: int = Field(default=0, ge=0, le=4)
    rejected_actions: int = Field(default=0, ge=0, le=4)
    resources: ResourceCounters = ResourceCounters()

    @property
    def receipt_id(self):
        return digest([self.run_sha256, self.task_id, self.arm, self.repetition, self.time_step])

    @model_validator(mode="after")
    def provenance(self):
        if not set(self.consumed) <= set(self.packed) <= set(self.selected):
            raise ValueError("attempt_provenance_invalid")
        if self.status not in ("complete", "setup") and (
            self.consumed or self.terminal_state_sha256 or self.observed_action
        ):
            raise ValueError("failed_attempt_disclosure")
        if self.observed_action is not None and self.terminal_state_sha256 is None:
            raise ValueError("unobserved_success")
        return self


class PairedMetric(Record):
    baseline: Arm
    candidate: Arm
    attempted_scenarios: int = Field(ge=0, le=96)
    eligible_pairs: int = Field(ge=0, le=96)
    excluded_pairs: int = Field(ge=0, le=96)
    wins: int = Field(ge=0, le=96)
    losses: int = Field(ge=0, le=96)
    ties: int = Field(ge=0, le=96)
    delta_pp: float | None = Field(default=None, ge=-100, le=100, allow_inf_nan=False)
    interval_pp: tuple[float, float] | None = None
    variance: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    family_delta_pp: tuple[tuple[Family, float], ...] = Field(default=(), max_length=6)

    @model_validator(mode="after")
    def denominator(self):
        if (
            self.wins + self.losses + self.ties != self.eligible_pairs
            or self.eligible_pairs + self.excluded_pairs != self.attempted_scenarios
        ):
            raise ValueError("pair_denominator")
        if self.interval_pp is not None and not (
            -100 <= self.interval_pp[0] <= self.interval_pp[1] <= 100
        ):
            raise ValueError("pair_interval")
        return self


class EvaluationReport(Record):
    version: Literal["memory-longitudinal-report-v1"] = "memory-longitudinal-report-v1"
    run_sha256: Digest
    receipts_sha256: Digest
    semantic_replay_sha256: Digest
    replay_match: bool
    source_verified: bool
    complete_grid: bool
    attempted_rows: int = Field(ge=0, le=9216)
    status_counts: tuple[tuple[Status, int], ...] = Field(max_length=8)
    comparisons: tuple[PairedMetric, ...] = Field(max_length=6)
    safety_failures: tuple[Identity, ...] = Field(default=(), max_length=128)
    safety_checks: tuple[tuple[Identity, Literal["pass", "fail", "unknown"]], ...] = Field(
        max_length=64
    )
    contamination: Literal["author_visible_no_independent_blind_claim"] = (
        "author_visible_no_independent_blind_claim"
    )
    native_resources: None = None
    actual_model_resources: None = None
    limitations: tuple[Identity, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def rows(self):
        if (
            sum(n for _, n in self.status_counts) != self.attempted_rows
            or any(n < 0 for _, n in self.status_counts)
            or len({s for s, _ in self.status_counts}) != len(self.status_counts)
        ):
            raise ValueError("status_denominator")
        return self


class ResearchDecision(Record):
    version: Literal["memory-research-decision-v1"] = "memory-research-decision-v1"
    status: Literal[
        "candidate",
        "blocked",
        "needs_independent_review",
        "rejected",
        "not_evaluable",
        "eligible_for_offline_canary",
    ]
    report_sha256: Digest
    evidence_key: Digest
    previous_decision: Digest | None = None
    prior_failure: Digest | None = None
    reviewer: Identity | None = None
    reasons: tuple[Identity, ...] = Field(min_length=1, max_length=64)
    effective_policy: Literal["unchanged"] = "unchanged"
    live_promotion: Literal[False] = False
