"""Scorer-only gold and scenario-clustered descriptive uncertainty."""

import random
from collections import Counter, defaultdict
from hashlib import sha256
from statistics import mean, pvariance
from typing import Literal

from pydantic import Field, model_validator

from personal_ai.memory.research.experiments.artifacts import parse_json
from personal_ai.memory.research.experiments.contracts import (
    Arm,
    EvaluationReport,
    Family,
    Identity,
    PairedMetric,
    Record,
    Split,
    Status,
    digest,
)

from .dataset import FIXTURE_DIR, SCORER_SHA256


class Gold(Record):
    task_id: Identity
    family: Family
    variant: Identity
    split: Split
    expected_status: Literal["complete", "denied", "cancelled", "timed_out", "incomplete", "error"]
    expected_action: Identity | None
    expected_abstention: bool
    minimum_effects: int = Field(ge=0, le=1)
    arm_statuses: tuple[tuple[Arm, Status], ...] = Field(default=(), max_length=12)


class ScoringSeal(Record):
    version: Literal["memory-longitudinal-scorer-v1"]
    gold: tuple[Gold, ...] = Field(min_length=48, max_length=96)

    @model_validator(mode="after")
    def coverage(self):
        if len({g.task_id for g in self.gold}) != len(self.gold):
            raise ValueError("scorer_duplicate")
        if sorted(Counter(g.family for g in self.gold).values()) != [8] * 6:
            raise ValueError("scorer_family_coverage")
        if sorted(Counter(g.split for g in self.gold).values()) != [12, 12, 24]:
            raise ValueError("scorer_split_coverage")
        return self


def load_gold():
    payload = FIXTURE_DIR.joinpath("memory-longitudinal-scorer-v1.json").read_bytes()
    if len(payload) > 65536 or sha256(payload).hexdigest() != SCORER_SHA256:
        raise ValueError("scorer_identity_changed")
    return ScoringSeal.model_validate(parse_json(payload, limit=65536))


def grade(row, gold):
    """Only newly observed target effects can establish Task B action success."""
    if row.status == "setup":
        return {"success": None, "violations": (), "boundary_correct": None}
    if row.status == "unsupported":
        return {"success": None, "violations": (), "boundary_correct": None}
    violations = []
    if row.effect_count > 1:
        violations.append("duplicate_intent")
    if row.observed_action and row.observed_action != gold.expected_action:
        violations.append("wrong_terminal_action")
    if row.observed_action and (row.effect_count != 1 or row.terminal_state_sha256 is None):
        violations.append("false_success")
    if row.consumed and row.status != "complete":
        violations.append("source_disclosure")
    if row.resources.provider_calls:
        violations.append("unauthorized_transport")
    if row.rejected_actions:
        violations.append("unsupported_action_inference")
    success = (
        gold.expected_status == "complete"
        and row.status == "complete"
        and (
            row.observed_action == gold.expected_action
            and (not gold.expected_action or row.effect_count == gold.minimum_effects)
            and (not gold.expected_abstention or row.abstained)
        )
    )
    expected_boundary = row.status == dict(gold.arm_statuses).get(row.arm, gold.expected_status)
    # A no-memory consumer holds no stale index/card at a correction/cache fence.
    if (
        row.arm == "no_memory"
        and gold.variant in ("correction_after_pack", "correction_before_use", "stale_index")
        and row.status == "complete"
        and row.observed_action is None
    ):
        expected_boundary = True
    if row.status not in ("complete", "unsupported") and not expected_boundary:
        violations.append("unexpected_attempt_failure")
    return {
        "success": success and not violations,
        "violations": tuple(violations),
        "boundary_correct": expected_boundary,
    }


def semantic_rows(rows, repetition):
    result = []
    timing = {"elapsed_ms", "index_build_ms", "retrieval_ms", "packing_ms", "consumption_ms"}
    for row in rows:
        if row.repetition != repetition:
            continue
        data = row.model_dump(mode="json", exclude={"repetition", "run_sha256"})
        data["resources"] = {k: v for k, v in data["resources"].items() if k not in timing}
        result.append(data)
    return sorted(result, key=lambda r: (r["task_id"], r["arm"], r["time_step"]))


def paired(rows, gold, contrast, protocol):
    # Collapse repeated attempts and time steps to one final trajectory outcome.
    final = {}
    for row in rows:
        key = row.task_id, row.arm, row.repetition
        if key not in final or row.time_step > final[key].time_step:
            final[key] = row
    clusters, family = [], defaultdict(list)
    wins = losses = ties = 0
    for task_id, rubric in gold.items():
        if rubric.expected_status != "complete":
            continue
        ds = []
        for rep in range(2):
            base = final[task_id, contrast.baseline, rep]
            candidate = final[task_id, contrast.candidate, rep]
            if base.status != "complete" or candidate.status != "complete":
                break
            ds.append(
                int(grade(candidate, rubric)["success"]) - int(grade(base, rubric)["success"])
            )
        if len(ds) != 2:
            continue
        delta = mean(ds)
        clusters.append(delta)
        family[rubric.family].append(delta)
        wins += delta > 0
        losses += delta < 0
        ties += delta == 0
    interval = None
    if clusters:
        rng = random.Random(protocol.bootstrap_seed)
        # Scenario clusters, not steps/repetitions, are sampled independently.
        samples = sorted(
            mean(rng.choices(clusters, k=len(clusters))) * 100
            for _ in range(protocol.bootstrap_samples)
        )
        interval = samples[int(0.025 * len(samples))], samples[int(0.975 * len(samples)) - 1]
    return PairedMetric(
        baseline=contrast.baseline,
        candidate=contrast.candidate,
        attempted_scenarios=len(gold),
        eligible_pairs=len(clusters),
        excluded_pairs=len(gold) - len(clusters),
        wins=wins,
        losses=losses,
        ties=ties,
        delta_pp=mean(clusters) * 100 if clusters else None,
        interval_pp=interval,
        variance=pvariance(clusters) if clusters else None,
        family_delta_pp=tuple((f, mean(values) * 100) for f, values in sorted(family.items())),
    )


def analyze(run, rows, fault_checks):
    seal = load_gold()
    gold = {g.task_id: g for g in seal.gold}
    scores = {r.receipt_id: grade(r, gold[r.task_id]) for r in rows}
    failures = sorted({v for s in scores.values() for v in s["violations"]})
    first, second = digest(semantic_rows(rows, 0)), digest(semantic_rows(rows, 1))
    comparisons = tuple(
        paired(rows, gold, c, run.protocol) for c in (run.protocol.primary, *run.protocol.secondary)
    )
    report = EvaluationReport(
        run_sha256=digest(run),
        receipts_sha256=digest([r.model_dump(mode="json") for r in rows]),
        semantic_replay_sha256=first,
        replay_match=first == second,
        source_verified=True,
        complete_grid=True,
        attempted_rows=len(rows),
        status_counts=tuple(sorted(Counter(r.status for r in rows).items())),
        comparisons=comparisons,
        safety_failures=tuple(failures),
        safety_checks=tuple(fault_checks),
        limitations=(
            "author_visible",
            "scripted_action_proxy",
            "no_real_embeddings",
            "no_native_cost_or_model_utility",
            "no_live_promotion",
            "no_blind_acceptance",
            "scenario_clusters_small_and_correlated",
            "no_significance_claim",
        ),
    )
    metrics = {}
    for arm in (p.arm for p in run.policies):
        attempted = [r for r in rows if r.arm == arm]
        terminal = [r for r in attempted if r.time_step >= 2]
        latency = sorted(r.resources.elapsed_ms for r in attempted)
        measured = [scores[r.receipt_id] for r in terminal if r.status == "complete"]
        metrics[arm] = {
            "attempted_rows": len(attempted),
            "terminal_attempts": len(terminal),
            "statuses": dict(Counter(r.status for r in attempted)),
            "reasons": dict(Counter(r.reason for r in attempted)),
            "terminal_successes": sum(bool(s["success"]) for s in measured),
            "complete_terminal_denominator": len(measured),
            "boundary_correct": sum(
                scores[r.receipt_id]["boundary_correct"] is True for r in terminal
            ),
            "observed_actions": sum(r.observed_action is not None for r in terminal),
            "abstentions": sum(r.abstained for r in terminal),
            "rediscoveries": sum(r.rediscoveries for r in attempted),
            "rejected_actions": sum(r.rejected_actions for r in attempted),
            "estimated_tokens": sum(r.resources.fixture_token_estimate for r in attempted),
            "tool_calls": sum(r.resources.tool_calls for r in attempted),
            "maintenance_calls": sum(r.resources.maintenance_calls for r in attempted),
            "index_bytes_peak": max(r.resources.index_bytes for r in attempted),
            "retained_bytes_peak": max(r.resources.retained_bytes for r in attempted),
            "latency_p50_ms": latency[len(latency) // 2],
            "latency_p95_ms": latency[int(0.95 * (len(latency) - 1))],
            "provider_calls": 0,
            "actual_tokens": None,
            "billed_cost": None,
            "model_utility": "not_observed",
            "native_resources": None,
        }
    return report, metrics
