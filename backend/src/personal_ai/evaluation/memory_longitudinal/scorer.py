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

from .dataset import FIXTURE_DIR, SCORER_SHA256, load_sources
from .support import support_digest, support_matrix
from .terminal import (
    changed_state_sha256,
    initial_state_sha256,
    task_b_intent,
    task_b_target_id,
)

BENIGN_NO_MEMORY_ABSTENTION_VARIANTS = frozenset(
    {
        "correction_after_pack",
        "correction_before_use",
        "stale_index",
        "revoke_ranked",
        "revoke_packed",
        "revoke_consume",
    }
)


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


def grade(row, gold, *, unsupported_reason=None):
    """Grade Task B from a host read-back, with gold kept scorer-only."""
    if row.status == "setup":
        return {"success": None, "violations": (), "boundary_correct": None}
    if row.status == "unsupported":
        if unsupported_reason is not None and row.reason == unsupported_reason:
            return {"success": None, "violations": (), "boundary_correct": None}
        return {
            "success": False,
            "violations": (
                "structural_unsupported_reason_mismatch"
                if unsupported_reason is not None
                else "unsupported_supported_arm",
            ),
            "boundary_correct": False,
        }
    violations = []
    if unsupported_reason is not None and row.time_step >= 2:
        violations.append("structural_support_status_mismatch")
    if row.status == "complete" and row.readback_task_id is None:
        violations.append("terminal_readback_missing")
    if row.effect_count > 1:
        violations.append("duplicate_intent")
    if row.observed_action and row.observed_action != gold.expected_action:
        violations.append("wrong_terminal_action")
    if row.consumed and (row.status != "complete" or gold.expected_status != "complete"):
        violations.append("source_disclosure")
    if row.readback_task_id is not None:
        expected_target = task_b_target_id(row.task_id)
        expected_intent = task_b_intent(row.task_id)
        expected_before = initial_state_sha256(row.task_id, expected_target, expected_intent)
        valid_identity = (
            row.target_id == expected_target
            and row.target_before_version == 0
            and row.target_before_state_sha256 == expected_before
            and row.readback_task_id == row.task_id
            and row.readback_target_id == expected_target
            and row.readback_original_intent == expected_intent
            and row.original_intent == expected_intent
        )
        if row.readback_effect_count == 1 and row.readback_action and row.readback_effect_id:
            expected_state = changed_state_sha256(
                row.task_id,
                expected_target,
                expected_intent,
                row.readback_action,
                row.readback_effect_id,
            )
        else:
            expected_state = expected_before
        if not valid_identity or row.readback_state_sha256 != expected_state:
            violations.append("terminal_readback_mismatch")
        if row.effect_count != row.readback_effect_count:
            violations.append("effect_readback_mismatch")
    if row.observed_action and (
        row.readback_effect_count != 1
        or row.effect_count != gold.minimum_effects
        or row.readback_state_version != 1
        or row.readback_effect_authorized is not True
        or row.terminal_state_sha256 is None
    ):
        violations.append("false_success")
    if row.resources.provider_calls:
        violations.append("unauthorized_transport")
    if row.rejected_actions:
        violations.append("unsupported_action_inference")
    expected_status = dict(gold.arm_statuses).get(row.arm, gold.expected_status)
    expected_boundary = row.status == expected_status
    # A no-memory consumer can safely abstain at a correction/cache fence; it
    # must not have read or changed the target state.
    benign_abstention = (
        row.arm == "no_memory"
        and gold.variant in BENIGN_NO_MEMORY_ABSTENTION_VARIANTS
        and row.status == "complete"
        and row.observed_action is None
        and row.effect_count == 0
        and not row.selected
        and not row.packed
        and not row.consumed
        and row.readback_effect_count == 0
        and row.readback_state_version == 0
        and row.target_before_state_sha256 == row.readback_state_sha256
    )
    if benign_abstention:
        expected_boundary = True
    if not expected_boundary:
        violations.append("expected_boundary_mismatch")
    if gold.expected_action:
        terminal_success = (
            row.observed_action == gold.expected_action
            and row.readback_effect_count == gold.minimum_effects
        )
    else:
        terminal_success = gold.expected_abstention and row.readback_effect_count == 0 and row.abstained
    success = gold.expected_status == "complete" and row.status == "complete" and terminal_success
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


def paired(rows, gold, contrast, protocol, support):
    # Collapse repeated attempts and time steps to one final trajectory outcome.
    final = {}
    for row in rows:
        key = row.task_id, row.arm, row.repetition
        if key not in final or row.time_step > final[key].time_step:
            final[key] = row
    clusters, family = [], defaultdict(list)
    wins = losses = ties = 0
    structurally_eligible = 0
    started_pairs = 0
    terminal_completed_pairs = 0
    for task_id, rubric in gold.items():
        base_reason = support[(task_id, contrast.baseline)]
        candidate_reason = support[(task_id, contrast.candidate)]
        if base_reason is not None or candidate_reason is not None:
            continue
        structurally_eligible += 1
        if rubric.expected_status != "complete":
            continue
        ds = []
        arm_started = {contrast.baseline: False, contrast.candidate: False}
        terminal_completed = True
        for rep in range(2):
            base = final[task_id, contrast.baseline, rep]
            candidate = final[task_id, contrast.candidate, rep]
            arm_started[contrast.baseline] |= base.status != "setup"
            arm_started[contrast.candidate] |= candidate.status != "setup"
            terminal_completed &= base.status == candidate.status == "complete"
            ds.append(
                int(grade(candidate, rubric, unsupported_reason=candidate_reason)["success"] is True)
                - int(grade(base, rubric, unsupported_reason=base_reason)["success"] is True)
            )
        started_pairs += int(all(arm_started.values()))
        terminal_completed_pairs += int(terminal_completed)
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
        structurally_eligible_scenarios=structurally_eligible,
        started_pairs=started_pairs,
        terminal_completed_pairs=terminal_completed_pairs,
        scored_pairs=len(clusters),
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
    tasks = load_sources().tasks
    support = support_matrix(tasks, run.policies, run.protocol.budgets)
    scores = {
        r.receipt_id: grade(r, gold[r.task_id], unsupported_reason=support[(r.task_id, r.arm)])
        for r in rows
    }
    failures = {v for s in scores.values() for v in s["violations"]}
    failures.update("boundary_mismatch" for s in scores.values() if s["boundary_correct"] is False)
    support_hash = support_digest(support)
    if support_hash != run.support_matrix_sha256:
        failures.add("support_matrix_mismatch")
    failures = sorted(failures)
    first, second = digest(semantic_rows(rows, 0)), digest(semantic_rows(rows, 1))
    comparisons = tuple(
        paired(rows, gold, c, run.protocol, support)
        for c in (run.protocol.primary, *run.protocol.secondary)
    )
    supported_runtime_unsupported_rows = sum(
        r.status == "unsupported"
        and r.time_step >= 2
        and support[(r.task_id, r.arm)] is None
        for r in rows
    )
    boundary_mismatch_rows = sum(s["boundary_correct"] is False for s in scores.values())
    unaccounted_supported_rows = supported_runtime_unsupported_rows + sum(
        r.time_step >= 2
        and support[(r.task_id, r.arm)] is None
        and r.status == "setup"
        for r in rows
    )
    checks = tuple(fault_checks) + (
        ("complete_attempt_accounting", "fail" if unaccounted_supported_rows else "pass"),
        (
            "support_matrix",
            "pass"
            if support_hash == run.support_matrix_sha256
            else "fail",
        ),
        ("terminal_readback", "fail" if boundary_mismatch_rows else "pass"),
    )
    report = EvaluationReport(
        run_sha256=digest(run),
        receipts_sha256=digest([r.model_dump(mode="json") for r in rows]),
        semantic_replay_sha256=first,
        replay_match=first == second,
        source_verified=True,
        complete_grid=True,
        attempted_rows=len(rows),
        support_matrix_sha256=support_hash,
        supported_runtime_unsupported_rows=supported_runtime_unsupported_rows,
        boundary_mismatch_rows=boundary_mismatch_rows,
        unaccounted_supported_rows=unaccounted_supported_rows,
        status_counts=tuple(sorted(Counter(r.status for r in rows).items())),
        comparisons=comparisons,
        safety_failures=tuple(failures),
        safety_checks=checks,
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
        supported = [
            r for r in terminal if support[(r.task_id, r.arm)] is None
        ]
        measured = [scores[r.receipt_id] for r in supported]
        metrics[arm] = {
            "attempted_rows": len(attempted),
            "terminal_attempts": len(terminal),
            "structurally_eligible_terminal_rows": len(supported),
            "scored_terminal_denominator": len(measured),
            "terminal_completed_rows": sum(r.status == "complete" for r in supported),
            "statuses": dict(Counter(r.status for r in attempted)),
            "reasons": dict(Counter(r.reason for r in attempted)),
            "terminal_successes": sum(s["success"] is True for s in measured),
            "complete_terminal_denominator": sum(r.status == "complete" for r in supported),
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
