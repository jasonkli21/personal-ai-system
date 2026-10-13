"""Privacy-safe P21/P22 observation projection, leakage-safe splits and rollout gates.

This module does not dispatch, train on prompt text, invent missing labels, or
publish runtime policy. P19 and P22 remain authoritative for measured outcomes.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from personal_ai.routing.decision_models import EndpointRef, StrategyView, _aware, _FrozenModel
from personal_ai.routing.features import FEATURE_SCHEMA, coverage_identity, digest, extract_features
from personal_ai.routing.strategy import (
    QuotaAwareDeterministicStrategy,
    replay_deterministic_decision,
)


class SplitPolicy(_FrozenModel):
    version: Literal["group-temporal-config-v1"] = "group-temporal-config-v1"
    temporal_cutoff: datetime
    configuration_holdout: tuple[str, ...] = Field(default=(), max_length=128)
    heldout_modulus: int = Field(default=5, ge=2, le=10)
    # Trusted experiment specification, frozen in the dataset manifest. Missing
    # family classification merges the whole suite rather than guessing families.
    fixture_families: tuple[tuple[str, int, str, str], ...] = Field(default=(), max_length=10000)


class OutcomeLabel(_FrozenModel):
    endpoint: EndpointRef
    source: Literal["synthetic", "live"]
    source_version: str
    evaluation_identity_sha256: str
    known_at: datetime
    quality: float = Field(ge=0, le=1)
    hard_boundaries_passed: bool
    # Single executed-case metrics; NOT root/cascade pipeline totals.
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    quota_units: tuple[tuple[str, int], ...] = Field(default=(), max_length=16)


class DatasetRow(_FrozenModel):
    observation_sha256: str
    group_sha256: str
    coverage_sha256: str
    observed_at: datetime
    split: Literal["train", "grouped_holdout", "temporal_holdout", "configuration_holdout"]
    view: StrategyView
    selected: EndpointRef
    labels: tuple[OutcomeLabel | None, ...] = Field(max_length=32)
    shadow_agreement: bool | None = None
    shadow_latency_us: int = Field(default=0, ge=0)
    shadow_cpu_us: int = Field(default=0, ge=0)
    pipeline_metrics: dict | None = None

    @model_validator(mode="after")
    def canonical_labels_and_features(self):
        if (
            self.view.feature_context is None
            or self.selected not in {c.endpoint for c in self.view.candidates}
            or len(self.labels) != len(self.view.candidates)
            or any(
                label is not None
                and (label.endpoint != candidate.endpoint or label.endpoint != self.selected)
                for candidate, label in zip(self.view.candidates, self.labels)
            )
        ):
            raise ValueError("routing_dataset_label_or_feature_invalid")
        _aware(self.observed_at)
        for label in self.labels:
            if label:
                _aware(label.known_at)
        return self

    @field_validator("pipeline_metrics")
    @classmethod
    def bounded_metrics(cls, value):
        from personal_ai.usage.observations import PipelineMetrics

        return PipelineMetrics.model_validate(value).model_dump() if value is not None else None


@dataclass(frozen=True)
class ObservationDataset:
    rows: tuple[DatasetRow, ...]
    manifest: dict

    @property
    def sha256(self):
        return digest(
            {"manifest": self.manifest, "rows": [r.model_dump(mode="json") for r in self.rows]}
        )


def normalized_configuration_facts(decision, *, split_policy):
    """Return reusable routing configuration without operational instance data."""
    return normalized_configuration_facts_for_view(
        decision.strategy_view(), split_policy=split_policy
    )


def normalized_configuration_facts_for_view(view, *, split_policy):
    """Build the same configuration identity from an already-safe projected view."""
    context = view.feature_context
    return {
        "feature_schema": context.schema_version,
        "application_id": context.application_id,
        "task_id": context.task_id,
        "task_profile_id": context.task_profile_id,
        "task_profile_version": context.task_profile_version,
        "task_configuration_sha256": context.task_configuration_sha256,
        "requirements_sha256": context.requirements_sha256,
        "policy_sha256": context.policy_sha256,
        "baseline_strategy": QuotaAwareDeterministicStrategy.ref.model_dump(mode="json"),
        "baseline_implementation_sha256": QuotaAwareDeterministicStrategy().implementation_sha256,
        "candidate_composition": sorted(
            [
                (
                    candidate.endpoint.model_dump(mode="json"),
                    candidate.endpoint_configuration_sha256,
                    candidate.quality_identity_sha256,
                    candidate.configured_priority,
                )
                for candidate in view.candidates
            ],
            key=lambda item: json.dumps(item[0], sort_keys=True, separators=(",", ":")),
        ),
        "split_policy": split_policy.model_dump(mode="json"),
    }


def _join_selected_label(record, run_states):
    """Canonical joins only. Selected outcome never labels an unexecuted candidate."""
    decision = record.decision
    if decision.request.run_id is None:
        return None
    state = run_states.get(decision.request.run_id)
    if state is None:
        return None
    start, completion, cases = state
    if (
        completion is None
        or start.owner_id != decision.owner_id
        or (start.application_id, start.workspace_id)
        != (decision.application_id, decision.workspace_id)
    ):
        return None
    matches = [case for case in cases if case.routing_decision_id == decision.routing_decision_id]
    if len(matches) > 1:
        raise ValueError("routing_label_ambiguous")
    if not matches:
        return None
    case = matches[0]
    candidate = next(c for c in decision.candidates if c.endpoint == decision.selected)
    gate = next(
        (
            g
            for g in start.gate_bindings
            if g.request_id == decision.request.request_id and g.endpoint == decision.selected
        ),
        None,
    )
    mismatches = []
    if gate is None:
        mismatches.append("evaluation_gate_missing")
    else:
        if gate.fixture_id != case.fixture_id:
            mismatches.append("fixture")
        if gate.endpoint_configuration_sha256 != candidate.endpoint_configuration_sha256:
            mismatches.append("gate_endpoint_configuration")
        if gate.prepared_input_sha256 != case.prepared_input_sha256:
            mismatches.append("prepared_input")
    if case.endpoint != decision.selected:
        mismatches.append("endpoint")
    if case.endpoint_configuration_sha256 != candidate.endpoint_configuration_sha256:
        mismatches.append("case_endpoint_configuration")
    if case.policy_version != decision.request.policy_version:
        mismatches.append("policy")
    if case.task_profile_id != decision.task.profile_id or case.task_profile_version != decision.task.profile_version:
        mismatches.append("task_profile")
    if case.evaluation_run_id != start.evaluation_run_id:
        mismatches.append("run")
    if case.measured_at < decision.created_at:
        mismatches.append("measurement_precedes_decision")
    if case.metrics is None:
        mismatches.append("metrics_missing")
    if case.status not in {"measured", "synthetic_baseline"}:
        mismatches.append("case_status")
    if start.source != ("live" if case.status == "measured" else "synthetic"):
        mismatches.append("source")
    if (
        case.evaluation_suite_id,
        case.evaluation_suite_version,
        case.scoring_policy_id,
        case.scoring_policy_version,
        case.output_tokens,
    ) != (
        start.evaluation_suite_id,
        start.evaluation_suite_version,
        start.scoring_policy_id,
        start.scoring_policy_version,
        start.output_tokens,
    ):
        mismatches.append("suite_scoring_output")
    if (start.task_profile_id, start.task_profile_version, start.policy_version) != (
        decision.task.profile_id,
        decision.task.profile_version,
        decision.request.policy_version,
    ):
        mismatches.append("run_task_policy")
    if mismatches:
        raise ValueError("routing_label_identity_mismatch:" + ",".join(mismatches))
    # Live quality requires the producing terminal receipt, not caller-supplied IDs.
    if not (
        any(e.attempt_id == case.attempt_id and e.kind == "closed" for e in record.events)
        and any(
            e.permit
            and e.permit.attempt_id == case.attempt_id
            and e.permit.invocation_id == case.invocation_id
            for e in record.events
        )
    ):
        raise ValueError("routing_label_dispatch_missing")
    metrics = case.metrics
    return OutcomeLabel(
        endpoint=case.endpoint,
        source=start.source,
        source_version=f"{case.evaluation_suite_id}:{case.evaluation_suite_version}/{case.scoring_policy_id}:{case.scoring_policy_version}",
        evaluation_identity_sha256=digest(case),
        known_at=case.measured_at,
        quality=metrics.overall_score,
        hard_boundaries_passed=metrics.hard_boundaries_passed,
        input_tokens=metrics.input_tokens,
        output_tokens=metrics.output_tokens,
        latency_ms=metrics.latency_ms,
        quota_units=metrics.quota_units,
    )


def build_dataset(
    records, *, run_states, split_policy: SplitPolicy, complete: bool, pipeline_by_decision=None
):
    """Project a bounded explicit snapshot. Unknown conversation grouping is excluded.

    The initial dataset admits canonical evaluation-run families only. All cases
    in a run stay together; identical fixture case identities across runs also
    stay together. Ordinary traffic needs a canonical session join before it can
    be admitted, rather than pretending per-request IDs prevent session leakage.
    """
    _aware(split_policy.temporal_cutoff)
    from personal_ai.evaluation.provider_matrix_contracts import (
        EvaluationCaseSummary,
        EvaluationRunStart,
        EvaluationRunSummary,
    )

    run_states = {
        key: (
            EvaluationRunStart.model_validate(start.model_dump()),
            EvaluationRunSummary.model_validate(completion.model_dump()) if completion else None,
            tuple(EvaluationCaseSummary.model_validate(c.model_dump()) for c in cases),
        )
        for key, (start, completion, cases) in run_states.items()
    }
    if len(records) > 10000:
        raise ValueError("routing_dataset_bound_exceeded")
    unique = {}
    for record in records:
        from personal_ai.routing.decision_models import RoutingRecord

        record = RoutingRecord.model_validate(record.model_dump())
        key = record.decision.routing_decision_id
        if key in unique and unique[key] != record:
            raise ValueError("routing_observation_duplicate_conflict")
        unique[key] = record
    admitted, excluded = [], {}
    for record in sorted(
        unique.values(), key=lambda r: (r.decision.created_at, str(r.decision.routing_decision_id))
    ):
        d = record.decision
        reason = None
        if d.schema_version != 6:
            reason = "historical-feature-identity-unavailable"
        elif d.selected is None:
            reason = "no-route"
        elif d.request.run_id not in run_states:
            reason = "canonical-session-grouping-unavailable"
        elif not any(
            g.request_id == d.request.request_id
            for g in run_states[d.request.run_id][0].gate_bindings
        ):
            reason = "canonical-evaluation-request-unavailable"
        if reason:
            excluded[reason] = excluded.get(reason, 0) + 1
            continue
        replay_deterministic_decision(d, QuotaAwareDeterministicStrategy(), now=d.created_at)
        admitted.append(record)
    # Connected components preserve overlapping request/root/run/paired identities.
    parents = list(range(len(admitted)))
    families = {
        (suite, version, fixture): family
        for suite, version, fixture, family in split_policy.fixture_families
    }
    if len(families) != len(split_policy.fixture_families):
        raise ValueError("routing_fixture_family_duplicate")

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    keys = {}
    for i, record in enumerate(admitted):
        d = record.decision
        scoped = (d.owner_id, d.application_id, d.workspace_id)
        relations = [
            digest((scoped, "root", str(d.root_decision_id))),
            digest((scoped, "request", d.request.request_id)),
            digest((scoped, "run", d.request.run_id)),
        ]
        start = run_states[d.request.run_id][0]
        if (start.owner_id, start.application_id, start.workspace_id) != scoped:
            raise ValueError("routing_dataset_scope_mismatch")
        # Whole run union plus every paired fixture family, not just this route.
        relations.extend(
            digest(
                (
                    "fixture-family",
                    start.evaluation_suite_id,
                    families.get(
                        (start.evaluation_suite_id, start.evaluation_suite_version, g.fixture_id),
                        "unclassified-suite-family",
                    ),
                )
            )
            for g in start.gate_bindings
        )
        for relation in relations:
            if relation in keys:
                parents[find(i)] = find(keys[relation])
            keys[relation] = i
    groups = {}
    for i, record in enumerate(admitted):
        groups.setdefault(find(i), []).append(record)
    rows = []
    for group in groups.values():
        group_id = digest(sorted(str(r.decision.routing_decision_id) for r in group))
        configs = {
            c.endpoint_configuration_sha256
            for r in group
            for c in r.decision.candidates
            if c.eligible
        }
        split = (
            "configuration_holdout"
            if configs & set(split_policy.configuration_holdout)
            else "temporal_holdout"
            if max(r.decision.created_at for r in group) >= split_policy.temporal_cutoff
            else "grouped_holdout"
            if int(group_id[:8], 16) % split_policy.heldout_modulus == 0
            else "train"
        )
        for record in group:
            d = record.decision
            label = _join_selected_label(record, run_states)
            view = d.strategy_view()
            # Paired cases are grouped, but never assigned as labels to this
            # row's unexecuted alternatives. Pair comparison needs its own exact
            # input/config join; P22 target-only decisions cannot establish it.
            labels = tuple(label if c.endpoint == d.selected else None for c in view.candidates)
            rows.append(
                DatasetRow(
                    observation_sha256=digest(record),
                    group_sha256=group_id,
                    coverage_sha256=coverage_identity(view),
                    observed_at=d.created_at,
                    split=split,
                    view=view,
                    selected=d.selected,
                    labels=labels,
                    shadow_agreement=d.shadow.agreement if d.shadow else None,
                    shadow_latency_us=d.shadow.latency_us if d.shadow else 0,
                    shadow_cpu_us=d.shadow.cpu_us if d.shadow else 0,
                    pipeline_metrics=(pipeline_by_decision or {}).get(d.routing_decision_id),
                )
            )
    rows.sort(key=lambda row: row.observation_sha256)
    missing = sum(label is None for row in rows for label in row.labels)
    split_stats = {}
    for split in ("train", "grouped_holdout", "temporal_holdout", "configuration_holdout"):
        subset = [r for r in rows if r.split == split]
        split_stats[split] = {
            "rows": len(subset),
            "groups": len({r.group_sha256 for r in subset}),
            "missing_labels": sum(x is None for r in subset for x in r.labels),
        }
    manifest = {
        "schema_version": "routing-dataset-v1",
        "feature_schema": FEATURE_SCHEMA,
        "complete": complete,
        "observation_count": len(unique),
        "deduplicated": len(records) - len(unique),
        "included": len(rows),
        "excluded": excluded,
        "missing_labels": missing,
        "time_range": [
            min((r.observed_at.isoformat() for r in rows), default=None),
            max((r.observed_at.isoformat() for r in rows), default=None),
        ],
        "split_policy": split_policy.model_dump(mode="json"),
        "splits": split_stats,
        "group_policy": "scoped-request-root-run-and-exact-paired-case-connected-components",
        "label_policy": "p22-selected-executed-route-only-v1",
        "label_versions": sorted({x.source_version for r in rows for x in r.labels if x}),
        "coverage": sorted({r.coverage_sha256 for r in rows}),
        "application_task_profiles": sorted(
            {
                (
                    r.view.feature_context.application_id,
                    r.view.feature_context.task_id,
                    r.view.feature_context.task_profile_id,
                    r.view.feature_context.task_profile_version,
                )
                for r in rows
            }
        ),
        "strategy_policy_profile_config_facts_sha256": digest(
            sorted(
                {
                    json.dumps(
                        normalized_configuration_facts(r.decision, split_policy=split_policy),
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    for r in admitted
                }
            )
        ),
        "source_observation_corpus_sha256": digest(
            sorted(digest(record) for record in admitted)
        ),
        "excluded_fields": [
            "prompts",
            "context",
            "source-payloads",
            "credentials",
            "domain-records",
            "owner-workspace-request-identifiers",
        ],
        "historical_aggregates": "disabled; optional projection uses known_at < decision_time",
    }
    return ObservationDataset(tuple(rows), manifest)


def historical_quality(rows, *, before, coverage_sha256, endpoint):
    """Only prior outcomes already observed by decision time, in exact coverage."""
    _aware(before)
    supported = [
        label.quality
        for row in rows
        if row.coverage_sha256 == coverage_sha256 and row.observed_at < before
        for label in row.labels
        if label and label.endpoint == endpoint and label.known_at < before
    ]
    return sum(supported) / len(supported) if supported else None


class PromotionThresholds(_FrozenModel):
    version: Literal["routing-promotion-v1"] = "routing-promotion-v1"
    minimum_groups_per_holdout: int = Field(default=30, ge=30)
    minimum_quality_delta: float = Field(default=0, ge=0, le=1)
    minimum_resource_saving: float = Field(default=0.05, ge=0.05, le=1)
    maximum_pipeline_latency_increase_us: int = Field(default=0, ge=0)
    maximum_strategy_latency_us: int = Field(default=5000, ge=1, le=5000)
    maximum_abstention_rate: float = Field(default=0.25, ge=0, le=0.25)


class PromotionComparison(_FrozenModel):
    """Exact-coverage live comparison supplied only by a supported paired join."""

    coverage_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    group_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    split: Literal["grouped_holdout", "temporal_holdout", "configuration_holdout"]
    evidence_identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source: Literal["live"] = "live"
    quality_delta: float | None = Field(default=None, ge=-1, le=1)
    resource_saving: float | None = Field(default=None, ge=-1, le=1)
    pipeline_latency_increase_us: int | None = None
    pipeline_complete: bool = False
    calibration_supported: bool = False


def evaluate_strategy(dataset, strategy, *, thresholds=None, promotion_evidence=()):
    """Route agreement and supported answer quality remain separate measurements.

    Historical selected-route success is insufficient for comparing alternatives.
    No artifact is promoted by this report or by synthetic/shadow route agreement.
    """
    from personal_ai.routing.adaptive import ShadowRoutingStrategy

    thresholds = thresholds or PromotionThresholds()
    experiment = ShadowRoutingStrategy(strategy)
    measurements = []
    for row in dataset.rows:
        baseline = experiment.select(row.view)
        observation = experiment.observe(row.view, baseline)
        label = next(
            (x for x in row.labels if x and x.endpoint == observation.ranking[0].endpoint), None
        )
        measurements.append(
            {
                "coverage": row.coverage_sha256,
                "split": row.split,
                "group": row.group_sha256,
                "agreement": observation.agreement,
                "abstention": observation.abstention_reason,
                "strategy_latency_us": observation.latency_us,
                "strategy_cpu_us": observation.cpu_us,
                "supported_selected_quality": label.quality if label else None,
                "source": label.source if label else None,
                "single_case_latency_plus_strategy_us": label.latency_ms * 1000
                + observation.latency_us
                if label and label.latency_ms is not None
                else None,
                "pipeline_totals": row.pipeline_metrics,
                "provider_and_strategy_latency_us": (
                    row.pipeline_metrics["provider_latency_ms"] * 1000 + observation.latency_us
                    if row.pipeline_metrics
                    and row.pipeline_metrics["provider_latency_ms"] is not None
                    else None
                ),
            }
        )
    comparison_rows = tuple(
        PromotionComparison.model_validate(item.model_dump() if hasattr(item, "model_dump") else item)
        for item in promotion_evidence
    )
    rows_by_group = {
        (row.coverage_sha256, row.group_sha256): row.split for row in dataset.rows
    }
    if any(
        item.coverage_sha256 not in dataset.manifest["coverage"]
        or rows_by_group.get((item.coverage_sha256, item.group_sha256)) != item.split
        for item in comparison_rows
    ):
        raise ValueError("routing_promotion_evidence_identity_mismatch")
    if len(
        {
            (item.coverage_sha256, item.group_sha256)
            for item in comparison_rows
        }
    ) != len(comparison_rows):
        raise ValueError("routing_promotion_evidence_duplicate_group")

    coverage = []
    independent_live_groups = {}
    pipeline_complete_groups = 0
    supported_quality_comparisons = 0
    for identity in dataset.manifest["coverage"]:
        subset = [m for m in measurements if m["coverage"] == identity]
        comparisons = [item for item in comparison_rows if item.coverage_sha256 == identity]
        full_pipeline = [
            item for item in comparisons
            if item.pipeline_complete
            and item.quality_delta is not None
            and item.resource_saving is not None
            and item.pipeline_latency_increase_us is not None
        ]
        independent_live_groups[identity] = {
            split: len({item.group_sha256 for item in full_pipeline if item.split == split})
            for split in ("grouped_holdout", "temporal_holdout", "configuration_holdout")
        }
        pipeline_complete_groups += len({item.group_sha256 for item in full_pipeline})
        supported_quality_comparisons += sum(item.quality_delta is not None for item in comparisons)

        def gate(status, observed=None, threshold=None, reason=None):
            return {
                "status": status,
                "observed": observed,
                "threshold": threshold,
                "reason": reason,
            }

        enough_groups = all(
            independent_live_groups[identity][split] >= thresholds.minimum_groups_per_holdout
            for split in independent_live_groups[identity]
        )
        gates = {}
        if not dataset.manifest["complete"]:
            gates["dataset_completeness"] = gate("fail", False, True, "incomplete-dataset")
        else:
            gates["dataset_completeness"] = gate("pass", True, True)

        def metric_gate(
            values,
            threshold,
            *,
            compare,
            enough_groups=enough_groups,
            full_pipeline=full_pipeline,
        ):
            supported = [value for value in values if value is not None]
            if not enough_groups or len(supported) != len(full_pipeline) or not full_pipeline:
                return gate("unverified", None, threshold, "insufficient-live-pipeline-evidence")
            observed = sum(supported) / len(supported)
            return gate("pass" if compare(observed, threshold) else "fail", observed, threshold)

        gates["quality"] = metric_gate(
            [item.quality_delta for item in full_pipeline],
            thresholds.minimum_quality_delta,
            compare=lambda observed, threshold: observed >= threshold,
        )
        gates["resource_saving"] = metric_gate(
            [item.resource_saving for item in full_pipeline],
            thresholds.minimum_resource_saving,
            compare=lambda observed, threshold: observed >= threshold,
        )
        latency_values = [item.pipeline_latency_increase_us for item in full_pipeline]
        if not enough_groups or not full_pipeline or any(value is None for value in latency_values):
            gates["pipeline_latency"] = gate(
                "unverified", None, thresholds.maximum_pipeline_latency_increase_us,
                "incomplete-end-to-end-latency-evidence",
            )
        else:
            worst_latency = max(latency_values)
            gates["pipeline_latency"] = gate(
                "pass" if worst_latency <= thresholds.maximum_pipeline_latency_increase_us else "fail",
                worst_latency,
                thresholds.maximum_pipeline_latency_increase_us,
            )

        overhead = [m["strategy_latency_us"] for m in subset]
        if not overhead:
            gates["strategy_overhead"] = gate("unverified", None, thresholds.maximum_strategy_latency_us)
        else:
            worst_overhead = max(overhead)
            gates["strategy_overhead"] = gate(
                "pass" if worst_overhead <= thresholds.maximum_strategy_latency_us else "fail",
                worst_overhead,
                thresholds.maximum_strategy_latency_us,
            )
        abstentions = sum(m["abstention"] is not None for m in subset)
        abstention_rate = abstentions / len(subset) if subset else None
        gates["abstention"] = (
            gate(
                "pass" if abstention_rate <= thresholds.maximum_abstention_rate else "fail",
                abstention_rate,
                thresholds.maximum_abstention_rate,
            )
            if abstention_rate is not None
            else gate("unverified", None, thresholds.maximum_abstention_rate)
        )
        calibrated_groups = {
            item.group_sha256 for item in full_pipeline if item.calibration_supported
        }
        gates["calibration"] = (
            gate("pass", len(calibrated_groups), thresholds.minimum_groups_per_holdout)
            if enough_groups and len(calibrated_groups) >= thresholds.minimum_groups_per_holdout
            else gate("unverified", len(calibrated_groups), thresholds.minimum_groups_per_holdout,
                      "calibration-evidence-unavailable")
        )
        incompatible = {
            "feature-schema-incompatible",
            "artifact-stale",
            "baseline-incompatible",
            "strategy-implementation-incompatible",
            "endpoint-configuration-unavailable",
            "out-of-coverage",
        }
        compatibility_failures = [m["abstention"] for m in subset if m["abstention"] in incompatible]
        gates["configuration_freshness"] = (
            gate("fail", sorted(set(compatibility_failures)), "no incompatibility")
            if compatibility_failures
            else gate("pass" if subset else "unverified", 0 if subset else None, 0)
        )
        gates["independent_live_groups"] = (
            gate("pass", independent_live_groups[identity], thresholds.minimum_groups_per_holdout)
            if enough_groups
            else gate(
                "unverified",
                independent_live_groups[identity],
                thresholds.minimum_groups_per_holdout,
                "insufficient-independent-live-groups",
            )
        )
        promoted = all(result["status"] == "pass" for result in gates.values())
        reasons = [
            f"{name}:{result['status']}"
            for name, result in gates.items()
            if result["status"] != "pass"
        ]
        coverage.append(
            {"coverage_sha256": identity, "promoted": promoted, "gates": gates, "reasons": reasons}
        )
    promoted_coverage = [item["coverage_sha256"] for item in coverage if item["promoted"]]
    abstention_reason_counts = {}
    for measurement in measurements:
        reason = measurement["abstention"]
        if reason is not None:
            abstention_reason_counts[reason] = abstention_reason_counts.get(reason, 0) + 1
    return {
        "schema_version": "adaptive-routing-evaluation-v1",
        "dataset_sha256": dataset.sha256,
        "strategy": strategy.ref.model_dump(mode="json"),
        "thresholds": thresholds.model_dump(),
        "measurements": measurements,
        "coverage": coverage,
        "promoted_coverage": promoted_coverage,
        "non_abstaining_proposals": sum(m["abstention"] is None for m in measurements),
        "supported_alternate_quality_comparisons": supported_quality_comparisons,
        "independent_live_groups": independent_live_groups,
        "pipeline_complete_groups": pipeline_complete_groups,
        "abstention_reason_counts": abstention_reason_counts,
        "quality_comparison_status": (
            "supported"
            if any(item["gates"]["quality"]["status"] in {"pass", "fail"} for item in coverage)
            else "unverified"
        ),
        "strategy2": "deferred: insufficient supported paired labels; compare Strategy 1 first",
        "strategy3": "deferred: reward attribution, safe traffic and exploration evidence absent",
        "rollback": QuotaAwareDeterministicStrategy.ref.model_dump(mode="json"),
        "feature_rows_sha256": digest([extract_features(r.view) for r in dataset.rows]),
    }


def collect_dataset(
    factory, *, owner_id, scope, start, end, split_policy, accounting, max_records=1000
):
    """Read canonical retained P21/P22 facts. Bounds/expiry remain explicit.

    An exhausted row budget yields an incomplete manifest. This is a retained
    snapshot, not a claim that expired/deleted observations never existed.
    """
    if not 1 <= max_records <= 10000:
        raise ValueError("routing_dataset_bound_invalid")
    records, cursor, complete = [], None, False
    repository = factory.routing_decision_repository()
    while len(records) < max_records:
        page, cursor, complete = repository.observation_page(
            owner_id=owner_id,
            scope=scope,
            start=start,
            end=end,
            after=cursor,
            limit=min(100, max_records - len(records)),
        )
        records.extend(page)
        if complete:
            break
    evaluations = factory.provider_matrix_evaluation_repository()
    states = {}
    for run_id in sorted({r.decision.request.run_id for r in records if r.decision.request.run_id}):
        from uuid import UUID

        try:
            states[run_id] = evaluations.get_run_state(UUID(run_id), owner_id=owner_id, scope=scope)
        except LookupError:
            continue  # Deleted/expired/unavailable label remains missing/excluded.
    resources = {
        r.decision.routing_decision_id: accounting.request_observation(
            owner_id=owner_id,
            scope=scope,
            request_id=r.decision.request.request_id,
            run_id=r.decision.request.run_id,
        )
        for r in records
    }
    dataset = build_dataset(
        records,
        run_states=states,
        split_policy=split_policy,
        complete=complete,
        pipeline_by_decision=resources,
    )
    dataset.manifest["requested_time_range"] = [start.isoformat(), end.isoformat()]
    dataset.manifest["retention_semantics"] = (
        "retained-authorized-snapshot; deleted/expired observations absent"
    )
    return dataset


def load_snapshot(path):
    """Synthetic-only fixture replay; personal datasets need authorized store reads."""
    import json

    raw = path.read_bytes()
    if len(raw) > 2_000_000:
        raise ValueError("routing_snapshot_bound_exceeded")
    document = json.loads(raw)
    if document["schema_version"] != "adaptive-routing-synthetic-snapshot-v1":
        raise ValueError("routing_snapshot_schema_unsupported")
    if len(document["rows"]) > 10000:
        raise ValueError("routing_snapshot_bound_exceeded")
    rows = tuple(DatasetRow.model_validate(row) for row in document["rows"])
    if any(label.source != "synthetic" for row in rows for label in row.labels if label):
        raise ValueError("routing_snapshot_must_be_synthetic")
    dataset = ObservationDataset(rows, document["manifest"])
    if dataset.sha256 != document["dataset_sha256"]:
        raise ValueError("routing_snapshot_identity_mismatch")
    from personal_ai.routing.adaptive import AdaptiveArtifact

    artifact = AdaptiveArtifact.model_validate(document["artifact"])
    if artifact.dataset_sha256 != dataset.sha256:
        raise ValueError("routing_snapshot_artifact_mismatch")
    return dataset, artifact


def main():
    import json
    from pathlib import Path

    from personal_ai.routing.adaptive import BoundedCapacityStrategy

    path = Path(__file__).parent / "fixtures/routing/adaptive-observations-v1.json"
    dataset, artifact = load_snapshot(path)
    from personal_ai.evaluation.quota_scarcity import run_quota_scarcity_evaluation

    frozen = json.loads((path.parent / "adaptive-baseline-v1.json").read_text())
    if run_quota_scarcity_evaluation().model_dump(mode="json") != frozen["quota_baseline"]:
        raise ValueError("adaptive_frozen_baseline_changed")
    report = evaluate_strategy(dataset, BoundedCapacityStrategy(artifact))
    print(json.dumps({"manifest": dataset.manifest, "report": report}, indent=2))


def paired_outcomes(records, run_states):
    """Separate P22 paired measurements with exact input/rubric/run identity.

    These are observations from executed cases, not labels assigned to an
    unexecuted choice in another request. Different serializer/preparation hashes
    remain separate. They do not establish runtime candidate-policy benefit.
    """
    groups = {}
    for record in records:
        label = _join_selected_label(record, run_states)
        if label is None:
            continue
        d = record.decision
        start, completion, cases = run_states[d.request.run_id]
        case = next(c for c in cases if c.routing_decision_id == d.routing_decision_id)
        identity = digest(
            {
                "run": d.request.run_id,
                "fixture": case.fixture_id,
                "fixture_manifest": completion.fixture_manifest_sha256,
                "suite": (start.evaluation_suite_id, start.evaluation_suite_version),
                "scorer": (start.scoring_policy_id, start.scoring_policy_version),
                "task": start.task_configuration_sha256,
                "policy": start.policy_version,
                "input": case.prepared_input_sha256,
                "output_bound": case.output_tokens,
                "source": start.source,
            }
        )
        groups.setdefault(identity, []).append(label)
    return tuple(
        {
            "paired_identity_sha256": key,
            "outcomes": tuple(label.model_dump(mode="json") for label in labels),
            "promotion_eligible": False,
        }
        for key, labels in sorted(groups.items())
        if len(labels) > 1 and len({label.endpoint for label in labels}) == len(labels)
    )


if __name__ == "__main__":
    main()
