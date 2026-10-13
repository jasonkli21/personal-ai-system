"""Privacy-safe P21/P22 observation projection, leakage-safe splits and rollout gates.

This module does not dispatch, train on prompt text, invent missing labels, or
publish runtime policy. P19 and P22 remain authoritative for measured outcomes.
"""

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
    if gate is None or (
        case.endpoint != decision.selected
        or case.endpoint_configuration_sha256 != candidate.endpoint_configuration_sha256
        or case.policy_version != decision.request.policy_version
        or case.task_profile_id != decision.task.profile_id
        or case.task_profile_version != decision.task.profile_version
        or case.fixture_id != gate.fixture_id
        or case.evaluation_run_id != start.evaluation_run_id
        or case.measured_at < decision.created_at
        or case.metrics is None
        or case.status not in {"measured", "synthetic_baseline"}
        or start.source != ("live" if case.status == "measured" else "synthetic")
        or (
            case.evaluation_suite_id,
            case.evaluation_suite_version,
            case.scoring_policy_id,
            case.scoring_policy_version,
            case.output_tokens,
        )
        != (
            start.evaluation_suite_id,
            start.evaluation_suite_version,
            start.scoring_policy_id,
            start.scoring_policy_version,
            start.output_tokens,
        )
        or gate.endpoint_configuration_sha256 != candidate.endpoint_configuration_sha256
        or (start.task_profile_id, start.task_profile_version, start.policy_version)
        != (
            decision.task.profile_id,
            decision.task.profile_version,
            decision.request.policy_version,
        )
        or gate.prepared_input_sha256 != case.prepared_input_sha256
    ):
        raise ValueError("routing_label_identity_mismatch")
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
            [r.decision.model_dump(mode="json") for r in admitted]
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


def evaluate_strategy(dataset, strategy, *, thresholds=None):
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
    coverage = []
    for identity in dataset.manifest["coverage"]:
        subset = [m for m in measurements if m["coverage"] == identity]
        reasons = ["paired-pipeline-outcomes-unavailable"]
        if not dataset.manifest["complete"]:
            reasons.append("incomplete-dataset")
        for split in ("grouped_holdout", "temporal_holdout", "configuration_holdout"):
            if (
                len({m["group"] for m in subset if m["split"] == split and m["source"] == "live"})
                < thresholds.minimum_groups_per_holdout
            ):
                reasons.append(f"insufficient-{split}-live-coverage")
        if any(m["strategy_latency_us"] > thresholds.maximum_strategy_latency_us for m in subset):
            reasons.append("strategy-overhead-exceeded")
        coverage.append({"coverage_sha256": identity, "promoted": False, "reasons": reasons})
    return {
        "schema_version": "adaptive-routing-evaluation-v1",
        "dataset_sha256": dataset.sha256,
        "strategy": strategy.ref.model_dump(mode="json"),
        "thresholds": thresholds.model_dump(),
        "measurements": measurements,
        "coverage": coverage,
        "promoted_coverage": [],
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
