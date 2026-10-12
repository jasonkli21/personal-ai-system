"""Frozen macro-planning benchmark; model outcomes remain explicitly unmeasured.

Uses configured deployment rules, shared assembler/provider/builder and built-in
profile/memory adapters. Domain payloads/counts are synthetic, never live proof.
No training, model inference or private artifact retention is performed.
"""

from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

from personal_ai.context.deployment import configured_context_runtime
from personal_ai.context.planner import ContextPlanner
from personal_ai.context.providers import ContextPreparationError
from personal_ai.evaluation.context_planner import FIXTURE_PATH, _run_fixture
from personal_ai.evaluation.output import emit
from personal_ai.evaluation.planning_fixtures import federation_planning_rows
from personal_ai.evaluation.planning_promotion import PlanningMeasurements, promotion_reasons
from personal_ai.settings import Settings

CORPUS_PATH = Path(__file__).parent / "fixtures/context/planning-heldout-v1.json"
FREEZE_PATH = Path(__file__).parent / "fixtures/context/planning-baseline-v1.json"


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
    from personal_ai.context import planner

    return {
        "baseline_version": ContextPlanner.VERSION,
        "configuration_digest": baseline_planner().configuration_digest,
        "algorithm_digest": sha256(Path(planner.__file__).read_bytes()).hexdigest(),
        "corpus_digest": sha256(CORPUS_PATH.read_bytes()).hexdigest(),
        "fixture_dependency_digest": sha256(FIXTURE_PATH.read_bytes()).hexdigest(),
        "federation_fixture_digest": sha256(
            (Path(__file__).parent / "planning_fixtures.py").read_bytes()
        ).hexdigest(),
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


def evaluate():
    frozen = json.loads(FREEZE_PATH.read_text())
    identity = freeze_identity()
    if any(frozen[key] != value for key, value in identity.items()):
        raise ValueError("planning_baseline_changed_requires_new_version")
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
                "max_context_tokens": case.get("max_context_tokens", 8192),
            }
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
                }
            )
    rows.extend(federation_planning_rows())
    slices = {}
    for application in sorted({row["application_id"] for row in rows}):
        subset = [row for row in rows if row["application_id"] == application]
        measured = PlanningMeasurements(
            families=len({row["family"] for row in subset}),
            omission_rate=sum(
                row["failure_class"] in {"lexical_omission", "partial_selection_omission"}
                for row in subset
            )
            / len(subset),
            irrelevant_rate=sum(row["failure_class"] == "irrelevant_selection" for row in subset)
            / len(subset),
            rollback_verified=all(
                row.get("retain_control_pair", {}).get("same_selections", True) for row in subset
            ),
        )
        slices[application] = {
            "case_count": len(subset),
            "family_count": len({row["family"] for row in subset}),
            "failure_classes": dict(Counter(row["failure_class"] for row in subset)),
            "support_proxy_rate": sum(row["source_support_proxy"] for row in subset) / len(subset),
            "promotion": "denied",
            "promotion_reasons": promotion_reasons(measured, measured),
        }
    coverage_slices = {}
    for row in rows:
        providers = tuple(
            sorted(
                f"{selection['provider_id']}.{selection['operation']}"
                for selection in row.get("trace", {}).get("baseline", ())
            )
        )
        key = (row["application_id"], row["family"], providers)
        coverage_slices.setdefault(key, []).append(row["id"])
    return {
        "schema_version": "planning-evaluation-v1",
        "identity": frozen,
        "promotion_policy": "context-planning-promotion-v1",
        "rows": rows,
        "slices": slices,
        "coverage_slices": [
            {
                "application_id": app,
                "task_family": family,
                "source_pattern": providers,
                "case_ids": case_ids,
                "promoted": False,
                "reason": "insufficient_independent_families_and_no_model_comparison",
            }
            for (app, family, providers), case_ids in sorted(coverage_slices.items())
        ],
        "planner_calls": 0,
        "planner_tokens": 0,
        "planner_quota": 0,
        "model_answer_quality": None,
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
