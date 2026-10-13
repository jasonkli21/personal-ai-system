"""Frozen macro-planning benchmark; model outcomes remain explicitly unmeasured.

Uses configured deployment rules, shared assembler/provider/builder and built-in
profile/memory adapters. Domain payloads/counts are synthetic, never live proof.
No training, model inference or private artifact retention is performed.
"""

from __future__ import annotations

import importlib.metadata
import json
import platform
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from statistics import fmean

import pydantic

from personal_ai.context.deployment import configured_context_runtime
from personal_ai.context.planner import ContextPlanner, PlanningTrace
from personal_ai.context.providers import ContextPreparationError
from personal_ai.evaluation.context_planner import FIXTURE_PATH, _run_fixture
from personal_ai.evaluation.output import emit
from personal_ai.evaluation.planning_fixtures import federation_planning_rows
from personal_ai.evaluation.planning_promotion import (
    PlanningCoverageKey,
    PlanningMeasurements,
    promotion_reasons,
)
from personal_ai.evaluation.planning_quality import (
    PlanningAnswerQualityEvidence,
)
from personal_ai.settings import Settings

CORPUS_PATH = Path(__file__).parent / "fixtures/context/planning-heldout-v2.json"
FREEZE_PATH = Path(__file__).parent / "fixtures/context/planning-baseline-v7.json"
PLANNING_EVALUATOR_VERSION = "planning-evaluator-v6"
PLANNING_MEASUREMENT_VERSION = "planning-measurements-v2"
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SOURCE_IDENTITY_PATHS = (
    "backend/src/personal_ai/applications/contracts.py",
    "backend/src/personal_ai/applications/registry.py",
    "backend/src/personal_ai/auth/scope.py",
    "backend/src/personal_ai/context/assembler.py",
    "backend/src/personal_ai/context/adapters.py",
    "backend/src/personal_ai/context/authorization.py",
    "backend/src/personal_ai/context/builder.py",
    "backend/src/personal_ai/context/deployment.py",
    "backend/src/personal_ai/context/planner.py",
    "backend/src/personal_ai/context/planning_experiment.py",
    "backend/src/personal_ai/context/providers.py",
    "backend/src/personal_ai/context/runtime.py",
    "backend/src/personal_ai/context/traces.py",
    "backend/src/personal_ai/contracts/context_references.py",
    "backend/src/personal_ai/federation/broker.py",
    "backend/src/personal_ai/federation/contracts.py",
    "backend/src/personal_ai/federation/deployment.py",
    "backend/src/personal_ai/federation/service.py",
    "backend/src/personal_ai/evaluation/context_planner.py",
    "backend/src/personal_ai/evaluation/planning_fixtures.py",
    "backend/src/personal_ai/evaluation/planning_promotion.py",
    "backend/src/personal_ai/evaluation/planning_quality.py",
    "backend/src/personal_ai/evaluation/planning.py",
    "backend/src/personal_ai/evaluation/provider_matrix.py",
    "backend/src/personal_ai/evaluation/provider_matrix_contracts.py",
    "backend/src/personal_ai/settings.py",
    "backend/pyproject.toml",
    "backend/uv.lock",
    "backend/src/personal_ai/evaluation/fixtures/context/context-plan-fixtures.json",
    "backend/src/personal_ai/evaluation/fixtures/context/planning-heldout-v2.json",
)
SOURCE_IDENTITY_PATHS = tuple(
    sorted(
        set(SOURCE_IDENTITY_PATHS)
        | {
            str(path.relative_to(REPOSITORY_ROOT))
            for path in (REPOSITORY_ROOT / "backend/src/personal_ai").rglob("*")
            if path.is_file()
            and not path.name.startswith("planning-baseline-")
            and "__pycache__" not in path.parts
            and path.suffix != ".pyc"
            and path.name != ".DS_Store"
        }
        | {"backend/pyproject.toml", "backend/uv.lock"}
    )
)


def baseline_planner():
    # Valid startup composition, synthetic endpoint names, no credential or sends.
    options = {
        "_env_file": None,
        "ai_provider": "fake",
        "ai_model": "synthetic",
        "auth_mode": "google_oidc",
        "auth_required": True,
        "auth_audience": "synthetic",
        "auth_allowed_emails": ("synthetic@gmail.com",),
        "travel_context_enabled": True,
        "shopping_context_enabled": True,
        "finance_context_enabled": True,
        "federation_choice_hmac_key": "synthetic-key-" * 3,
    }
    for name in ("travel", "shopping", "finance"):
        options.update(
            {
                f"{name}_context_base_url": "https://synthetic.invalid",
                f"{name}_context_service_audience": "https://synthetic.invalid",
                f"{name}_context_service_account": "synthetic@example.invalid",
            }
        )
    runtime = configured_context_runtime(Settings(**options))
    return ContextPlanner(runtime.planning_rules)


def freeze_identity():
    distributions = _runtime_distributions()
    return {
        "baseline_lock_version": "planning-baseline-lock-v7",
        "baseline_version": ContextPlanner.VERSION,
        "configuration_digest": baseline_planner().configuration_digest,
        "evaluator_version": PLANNING_EVALUATOR_VERSION,
        "source_identity_digest": _source_identity_digest(),
        "corpus_digest": sha256(CORPUS_PATH.read_bytes()).hexdigest(),
        "fixture_dependency_digest": sha256(FIXTURE_PATH.read_bytes()).hexdigest(),
        "counter_identity": "phase13-envelope-byte-estimate-v1",
        "python_runtime": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_abi": sys.implementation.cache_tag,
        "platform_runtime": platform.platform(),
        "runtime_distribution_count": len(distributions),
        "runtime_dependency_digest": sha256(
            json.dumps(distributions, separators=(",", ":")).encode()
        ).hexdigest(),
        "pydantic_runtime": pydantic.__version__,
    }


def _runtime_distributions():
    return sorted(
        (distribution.metadata.get("Name", "").casefold(), distribution.version)
        for distribution in importlib.metadata.distributions()
        if distribution.metadata.get("Name")
    )


def _source_identity_digest():
    identity = {
        relative: sha256((REPOSITORY_ROOT / relative).read_bytes()).hexdigest()
        for relative in SOURCE_IDENTITY_PATHS
    }
    identity["evaluator_version"] = PLANNING_EVALUATOR_VERSION
    return sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _git_revision_pair():
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    parent_result = subprocess.run(
        ["git", "rev-parse", "HEAD^"], cwd=REPOSITORY_ROOT,
        capture_output=True, text=True, check=False,
    )
    parent = parent_result.stdout.strip() if parent_result.returncode == 0 else None
    return head, parent


def _rollback_measurement(rows):
    pairs = [row.get("retain_control_pair") for row in rows]
    if any(not isinstance(pair, dict) for pair in pairs):
        return None
    checks = (
        "same_selections", "same_support", "same_input_tokens", "same_input_bytes"
    )
    return not any(
        any(pair.get(field) is not True for field in checks) for pair in pairs
    )


def _summarize_validation_trace(case_id: str, trace: PlanningTrace, source_identity: str):
    """Reduce one bound validation trace to payload-free evaluation counters."""
    reasons = set(trace.reasons)
    attempted = bool(
        trace.proposal_digest is not None
        or trace.proposal_choice_count is not None
        or trace.choice_results
        or reasons != {"no_promoted_coverage"}
    )
    accepted = trace.strategy == "validated_narrowing"
    unauthorized_reasons = {
        "planning_unknown_or_duplicate_choice",
        "planning_field_outside_envelope",
        "planning_budget_outside_envelope",
        "planning_required_choice_omitted",
        "planning_required_choice_narrowed",
    }
    choice_count = len(trace.choice_results)
    proposal_attempts = int(attempted)
    rejected_proposals = int(attempted and not accepted)
    fallback_proposals = int(attempted and not accepted)
    narrowed_choices = sum(
        result.disposition == "narrowed" for result in trace.choice_results
    )
    rejected_choices = sum(
        result.disposition == "rejected" for result in trace.choice_results
    )
    retained_fallback_choices = sum(
        result.disposition == "retained" for result in trace.choice_results
    )
    unauthorized_attempts = int(bool(reasons & unauthorized_reasons))
    return {
        "proposal_attempts": int(attempted),
        "accepted_proposals": int(attempted and accepted),
        "rejected_proposals": rejected_proposals,
        "fallback_proposals": fallback_proposals,
        "rejected_choices": rejected_choices,
        "narrowed_choices": narrowed_choices,
        "retained_fallback_choices": retained_fallback_choices,
        "unauthorized_attempts": unauthorized_attempts,
        "choice_count": choice_count,
        "proposal_rejection_rate": (
            rejected_proposals / proposal_attempts if proposal_attempts else None
        ),
        "fallback_proposal_rate": (
            fallback_proposals / proposal_attempts if proposal_attempts else None
        ),
        "narrowed_choice_rate": narrowed_choices / choice_count if choice_count else None,
        "retained_fallback_rate": (
            retained_fallback_choices / choice_count if choice_count else None
        ),
        "unauthorized_attempt_rate": (
            unauthorized_attempts / proposal_attempts if proposal_attempts else None
        ),
        "evidence_identity": sha256(json.dumps(
            {
                "case_id": case_id,
                "source_identity": source_identity,
                "trace": trace.model_dump(mode="json"),
            }, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest(),
    }


def _aggregate_validation_metrics(rows):
    observations = [row["validation_observation"] for row in rows]
    measured = bool(observations) and all(observation is not None for observation in observations)
    fields = (
        "proposal_attempts",
        "accepted_proposals",
        "rejected_proposals",
        "fallback_proposals",
        "rejected_choices",
        "narrowed_choices",
        "retained_fallback_choices",
        "unauthorized_attempts",
    )
    return {
        "observed_case_count": sum(observation is not None for observation in observations),
        "total_case_count": len(rows),
        **{
            field: sum(observation[field] for observation in observations)
            if measured else None
            for field in fields
        },
        "proposal_rejection_rate": (
            sum(observation["rejected_proposals"] for observation in observations)
            / sum(observation["proposal_attempts"] for observation in observations)
            if measured and sum(observation["proposal_attempts"] for observation in observations)
            else None
        ),
        "fallback_proposal_rate": (
            sum(observation["fallback_proposals"] for observation in observations)
            / sum(observation["proposal_attempts"] for observation in observations)
            if measured and sum(observation["proposal_attempts"] for observation in observations)
            else None
        ),
        "narrowed_choice_rate": (
            sum(observation["narrowed_choices"] for observation in observations)
            / sum(observation["choice_count"] for observation in observations)
            if measured and sum(observation["choice_count"] for observation in observations)
            else None
        ),
        "retained_fallback_rate": (
            sum(observation["retained_fallback_choices"] for observation in observations)
            / sum(observation["choice_count"] for observation in observations)
            if measured and sum(observation["choice_count"] for observation in observations)
            else None
        ),
        "unauthorized_attempt_rate": (
            sum(observation["unauthorized_attempts"] for observation in observations)
            / sum(observation["proposal_attempts"] for observation in observations)
            if measured and sum(observation["proposal_attempts"] for observation in observations)
            else None
        ),
    }


def _retain_control(request):
    return {
        "baseline_digest": request.baseline_digest,
        "choices": [
            {
                "choice_id": choice.choice_id,
                "fields": choice.fields,
                "max_results": choice.max_results,
                "max_bytes": choice.max_bytes,
                "max_tokens": choice.max_tokens,
            }
            for choice in request.choices
        ],
    }


def evaluate(
    *,
    quality_observations: Mapping[str, PlanningAnswerQualityEvidence] | None = None,
    validation_traces: Mapping[str, PlanningTrace] | None = None,
):
    frozen = json.loads(FREEZE_PATH.read_text())
    identity = freeze_identity()
    if any(frozen[key] != value for key, value in identity.items()):
        raise ValueError("planning_baseline_changed_requires_new_version")
    head, parent = _git_revision_pair()
    if head != frozen["source_revision"] and parent != frozen["source_revision"]:
        raise ValueError("planning_baseline_source_revision_mismatch_requires_new_version")
    planner = baseline_planner()
    originals = {item["name"]: item for item in json.loads(FIXTURE_PATH.read_text())["fixtures"]}
    cases = json.loads(CORPUS_PATH.read_text())["cases"]
    rows = []
    for case in cases:
        if "base" in case:
            fixture = {**originals[case["base"]], **case["overrides"], "name": case["id"]}
        else:
            rule = next(rule for rule in planner.rules if rule.rule_id == case["rule"])
            entity_types = case.get("entity_types", list(rule.candidate_entity_types[:1]))
            fixture = {
                "name": case["id"],
                "application_id": rule.application_ids[0],
                "intent": case.get("intent", rule.phrases[0]),
                "provider_id": rule.provider_id,
                "source_class": case.get("source_class", "domain_current"),
                "operation": rule.operation,
                "allowed_fields": list(rule.fields),
                "rule_fields": list(rule.fields),
                "expected_fields": list(rule.fields),
                "excluded_fields": [],
                "answer_support_needs": list(rule.fields),
                "phrase": rule.phrases[0],
                "category": rule.category,
                "use_candidate_entities": rule.use_candidate_entities,
                "candidate_entities": [
                    {"entity_type": kind, "entity_id": f"synthetic-{kind}"} for kind in entity_types
                ],
                "expected_candidate_entities": (
                    [
                        {"entity_type": kind, "entity_id": f"synthetic-{kind}"}
                        for kind in entity_types
                    ]
                    if rule.use_candidate_entities
                    else []
                ),
                "max_context_tokens": case.get("max_context_tokens", 8192),
            }
        fixture.update({
            key: value
            for key, value in case.items()
            if key not in {"id", "family", "base", "overrides", "rule", "intent", "entity_types",
                           "max_context_tokens"}
        })
        fixture["name"] = case["id"]
        fixture["max_context_tokens"] = case.get(
            "max_context_tokens", fixture.get("max_context_tokens", 2_048)
        )
        if case.get("include_memory"):
            fixture.update(
                {
                    "provider_ids": [fixture["provider_id"], "ai_memory"],
                    "use_default_rules": True,
                    "expected_fields": [
                        *fixture["expected_fields"],
                        "content",
                        "memory_type",
                        "effective_at",
                    ],
                    "answer_support_needs": [*fixture["answer_support_needs"], "content"],
                }
            )
        try:
            result = _run_fixture(fixture, configured_planner=planner)
            paired = _run_fixture(
                fixture, configured_planner=planner, planning_variant=_retain_control
            )
            if (
                (case.get("authorized_competing_candidate_count")
                 or case.get("source_revision_transition"))
                and (result["result"] != "passed" or paired["result"] != "passed")
            ):
                raise ValueError(f"planning_fixture_contract_failed:{case['id']}")
            omitted = result["omitted_expected_fields"]
            overfetch = result["overfetch_fields"]
            failure = (
                "lexical_omission"
                if omitted and not result["planned_selections"]
                else (
                    "partial_selection_omission"
                    if omitted
                    else ("irrelevant_selection" if overfetch else "none")
                )
            )
            if case.get("expected_exclusion"):
                failure = "expected_policy_or_source_exclusion"
            rows.append(
                {
                    "id": case["id"],
                    "family": case["family"],
                    "application_id": fixture["application_id"],
                    "failure_class": failure,
                    "omitted_field_count": len(omitted),
                    "overfetch_field_count": len(overfetch),
                    "selected_source_count": result["selected_source_count"],
                    "selected_item_count": result["selected_item_count"],
                    "assembled_bytes": result["assembled_bytes"],
                    "estimated_input_tokens": result["estimated_input_tokens"],
                    "planning_latency_ms": result["planning_latency_ms"],
                    "total_latency_ms": result["latency_ms"],
                    "source_support_proxy": result["answer_support_needs_injected"],
                    "effective_sensitivity": result["effective_sensitivity"],
                    "assembled_context_digest": result["assembled_context_digest"],
                    "authorized_competing_candidate_count": result[
                        "authorized_competing_candidate_count"
                    ],
                    "selected_competing_candidate_count": result[
                        "selected_competing_candidate_count"
                    ],
                    "authorized_candidate_pattern": result["authorized_candidate_pattern"],
                    "authorized_candidate_catalog_valid": result[
                        "authorized_candidate_catalog_valid"
                    ],
                    "source_revision_transition": result["source_revision_transition"],
                    "source_revision_observations": result["source_revision_observations"],
                    "source_revision_transition_valid": result[
                        "source_revision_transition_valid"
                    ],
                    "provider_calls": len(result["provider_calls"]),
                    "trace": result["planning_trace"],
                    "retain_control_pair": {
                        "strategy": "retain-control-v1",
                        "evidence_kind": "scripted_non_model",
                        "same_selections": paired["planned_selections"]
                        == result["planned_selections"],
                        "same_support": paired["injected_support_fields"]
                        == result["injected_support_fields"],
                        "same_input_tokens": paired["estimated_input_tokens"]
                        == result["estimated_input_tokens"],
                        "same_input_bytes": paired["assembled_bytes"] == result["assembled_bytes"],
                        "total_latency_ms": paired["latency_ms"],
                        "planning_latency_ms": paired["planning_latency_ms"],
                        "planner_calls": paired["planning_trace"]["planner_calls"],
                    },
                }
            )
        except ContextPreparationError as error:
            rows.append(
                {
                    "id": case["id"],
                    "family": case["family"],
                    "application_id": fixture["application_id"],
                    "failure_class": "required_source_denial",
                    "reason": error.code,
                    "source_support_proxy": False,
                    "provider_calls": 0,
                    "assembled_bytes": None,
                    "estimated_input_tokens": None,
                    "effective_sensitivity": "unknown",
                    "assembled_context_digest": None,
                    "authorized_competing_candidate_count": fixture.get(
                        "authorized_competing_candidate_count", 0
                    ),
                    "selected_competing_candidate_count": 0,
                    "authorized_candidate_pattern": [],
                    "source_revision_transition": fixture.get("source_revision_transition"),
                    "source_revision_observations": [],
                    "source_revision_transition_valid": False,
                }
            )
    rows.extend(federation_planning_rows())
    quality_observations = quality_observations or {}
    validation_traces = validation_traces or {}
    row_ids = {row["id"] for row in rows}
    if set(quality_observations) - row_ids:
        raise ValueError("planning_quality_observation_case_unknown")
    if set(validation_traces) - row_ids:
        raise ValueError("planning_validation_trace_case_unknown")
    for row in rows:
        observation = quality_observations.get(row["id"])
        if observation is not None:
            expected_config = row.get("trace", {}).get("configuration_digest")
            expected_context = row.get("assembled_context_digest")
            if (
                expected_context is None
                or observation.assembled_context_digest != expected_context
                or observation.configuration_digest != expected_config
                or observation.strategy_version != ContextPlanner.VERSION
                or observation.tested_revision != head
            ):
                raise ValueError("planning_quality_observation_identity_mismatch")
            row["supported_answer_rate"] = observation.supported_answer_rate
            row["quality_evidence_identity"] = observation.evidence_identity
            row["quality_hard_boundaries_passed"] = observation.hard_boundaries_passed
        else:
            row["supported_answer_rate"] = None
            row["quality_evidence_identity"] = None
            row["quality_hard_boundaries_passed"] = None
        validation_trace = validation_traces.get(row["id"])
        if validation_trace is None:
            row["validation_observation"] = None
        else:
            expected_trace = row.get("trace", {})
            if (
                validation_trace.configuration_digest != expected_trace.get("configuration_digest")
                or validation_trace.baseline_digest != expected_trace.get("baseline_digest")
            ):
                raise ValueError("planning_validation_trace_identity_mismatch")
            row["validation_observation"] = _summarize_validation_trace(
                row["id"], validation_trace, identity["source_identity_digest"]
            )
        row["task_family"] = row.get("family", "unknown")
        row["source_pattern"] = row.get("authorized_candidate_pattern") or sorted({
            f"{selection['provider_id']}.{selection['operation']}"
            for selection in row.get("trace", {}).get("baseline", ())
        })
        row["sensitivity_class"] = row.get("effective_sensitivity", "unknown")
    slices = {}
    for application in sorted({row["application_id"] for row in rows}):
        subset = [row for row in rows if row["application_id"] == application]
        slices[application] = {
            "summary_only": True,
            "case_count": len(subset),
            "family_count": len({row["family"] for row in subset}),
            "failure_classes": dict(Counter(row["failure_class"] for row in subset)),
            "support_proxy_rate": sum(row["source_support_proxy"] for row in subset) / len(subset),
        }
    coverage_slices = {}
    for row in rows:
        key = PlanningCoverageKey(
            application_id=row["application_id"],
            task_family=row["task_family"],
            source_pattern=tuple(row["source_pattern"]),
            sensitivity_class=row["sensitivity_class"],
        )
        coverage_slices.setdefault(key, []).append(row)
    evaluated_coverage = []
    validation_metrics_by_coverage = {}
    for key, subset in sorted(
        coverage_slices.items(),
        key=lambda pair: (
            pair[0].application_id, pair[0].task_family,
            pair[0].source_pattern, pair[0].sensitivity_class,
        ),
    ):
        measured_quality = [row["supported_answer_rate"] for row in subset]
        evidence_identity = sha256(json.dumps(
            {
                "coverage": key.model_dump(mode="json"),
                "rows": [row["id"] for row in subset],
                "quality": [row["quality_evidence_identity"] for row in subset],
                "source_identity": identity["source_identity_digest"],
            }, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        validation_observations = [
            row["validation_observation"] for row in subset
            if row["validation_observation"] is not None
        ]
        validation_measured = (
            bool(validation_observations)
            and len(validation_observations) == len(subset)
        )
        proposal_attempts = (
            sum(item["proposal_attempts"] for item in validation_observations)
            if validation_measured else None
        )
        rejected_proposals = (
            sum(item["rejected_proposals"] for item in validation_observations)
            if validation_measured else None
        )
        fallback_proposals = (
            sum(item["fallback_proposals"] for item in validation_observations)
            if validation_measured else None
        )
        rejected_choices = (
            sum(item["rejected_choices"] for item in validation_observations)
            if validation_measured else None
        )
        narrowed_choices = (
            sum(item["narrowed_choices"] for item in validation_observations)
            if validation_measured else None
        )
        retained_fallback_choices = (
            sum(item["retained_fallback_choices"] for item in validation_observations)
            if validation_measured else None
        )
        unauthorized_attempts = (
            sum(item["unauthorized_attempts"] for item in validation_observations)
            if validation_measured else None
        )
        choice_count = (
            sum(item["choice_count"] for item in validation_observations)
            if validation_measured else None
        )
        measured = PlanningMeasurements(
            families=len({row["family"] for row in subset}),
            omission_rate=sum(
                row.get("failure_class") in {"lexical_omission", "partial_selection_omission"}
                for row in subset
            ) / len(subset),
            irrelevant_rate=sum(row.get("failure_class") == "irrelevant_selection" for row in subset)
            / len(subset),
            supported_answer_rate=(
                fmean(measured_quality)
                if measured_quality and all(value is not None for value in measured_quality)
                else None
            ),
            hard_boundary_violations=(
                sum(not row["quality_hard_boundaries_passed"] for row in subset)
                if all(row["quality_hard_boundaries_passed"] is not None for row in subset)
                else None
            ),
            coverage_key=key,
            measurement_origin=(
                "phase22_observed"
                if measured_quality and all(value is not None for value in measured_quality)
                else "synthetic_offline"
            ),
            measurement_version=PLANNING_MEASUREMENT_VERSION,
            evidence_identity=evidence_identity,
            total_tokens=(
                sum(row["estimated_input_tokens"] for row in subset)
                if all(row.get("estimated_input_tokens") is not None for row in subset)
                else None
            ),
            p95_latency_ms=(
                max(row["total_latency_ms"] for row in subset)
                if all(row.get("total_latency_ms") is not None for row in subset)
                else None
            ),
            planner_p95_latency_ms=(
                max(row["planning_latency_ms"] for row in subset)
                if all(row.get("planning_latency_ms") is not None for row in subset)
                else None
            ),
            rollback_verified=_rollback_measurement(subset),
            proposal_attempts=proposal_attempts,
            accepted_proposals=(
                sum(item["accepted_proposals"] for item in validation_observations)
                if validation_measured else None
            ),
            rejected_proposals=rejected_proposals,
            fallback_proposals=fallback_proposals,
            rejected_choices=rejected_choices,
            narrowed_choices=narrowed_choices,
            retained_fallback_choices=retained_fallback_choices,
            unauthorized_proposal_attempts=unauthorized_attempts,
            proposal_rejection_rate=(
                rejected_proposals / proposal_attempts
                if proposal_attempts else None
            ),
            fallback_proposal_rate=(
                fallback_proposals / proposal_attempts
                if proposal_attempts else None
            ),
            narrowed_choice_rate=(
                narrowed_choices / choice_count if choice_count else None
            ),
            retained_fallback_rate=(
                retained_fallback_choices / choice_count if choice_count else None
            ),
            unauthorized_attempt_rate=(
                unauthorized_attempts / proposal_attempts if proposal_attempts else None
            ),
        )
        validation_metrics_by_coverage[key] = {
            name: getattr(measured, name)
            for name in (
                "proposal_attempts", "accepted_proposals", "rejected_proposals",
                "fallback_proposals", "rejected_choices", "narrowed_choices",
                "retained_fallback_choices",
                "unauthorized_proposal_attempts", "proposal_rejection_rate",
                "fallback_proposal_rate", "narrowed_choice_rate", "retained_fallback_rate",
                "unauthorized_attempt_rate",
            )
        }
        evaluated_coverage.append({
            "coverage_key": key.model_dump(mode="json"),
            "case_ids": [row["id"] for row in subset],
            "independent_family_count": measured.families,
            "measurement_origin": measured.measurement_origin,
            "measurement_version": measured.measurement_version,
            "evidence_identity": measured.evidence_identity,
            "measured_supported_answer_rate": measured.supported_answer_rate,
            "validation_metrics": validation_metrics_by_coverage[key],
            "promoted": False,
            "promotion_reasons": list(promotion_reasons(measured, measured))
            + ["no_candidate_comparison"],
        })
    return {
        "schema_version": "planning-evaluation-v1",
        "identity": frozen,
        "tested_git_revision": head,
        "tested_source_identity_digest": identity["source_identity_digest"],
        "promotion_policy": "context-planning-promotion-v1",
        "rows": rows,
        "slices": slices,
        "coverage_slices": evaluated_coverage,
        "planner_calls": 0,
        "planner_tokens": 0,
        "planner_quota": 0,
        "model_answer_quality": (
            fmean(row["supported_answer_rate"] for row in rows
                  if row["supported_answer_rate"] is not None)
            if any(row["supported_answer_rate"] is not None for row in rows)
            else None
        ),
        "proposal_validation_metrics": _aggregate_validation_metrics(rows),
        "assisted_comparison": None,
        "unauthorized_proposal_pressure": None,
        "promoted_coverage": [],
        "decision": "non_promotion",
        "reason": "No measured model-answer/quota benefit; selection misses alone do not justify inference.",
    }


def main():
    emit(evaluate())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
