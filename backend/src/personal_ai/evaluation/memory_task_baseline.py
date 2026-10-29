"""MEM-0: hermetic, evidence-aware four-arm replay. No provider dispatch path."""

import argparse
import json
import platform
import subprocess
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from time import perf_counter, process_time

from personal_ai.context.builder import ContextBuilder, ContextBuildItem, ContextBuildPolicy
from personal_ai.context.providers import ContextSourceReference
from personal_ai.evaluation.memory_task_contracts import ARMS, FAMILIES, Case, Corpus
from personal_ai.evaluation.memory_task_driver import DriverInput, run_driver
from personal_ai.evaluation.memory_task_runtime import Environment, visible_source
from personal_ai.memory.services import MemoryRetriever

ROOT = Path(__file__).resolve().parents[4]
FIXTURES = Path(__file__).parent / "fixtures/memory/mem0-cases-v1.json"
OUTPUT = ROOT / "artifacts/mem0"
UNVERIFIED = (
    "real_model_task_quality",
    "native_postgres_resources",
    "native_dynamo_resources",
    "provider_quota",
    "live_latency",
    "physical_deletion",
    "deployed_identity_and_grants",
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def measurement(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "fraction": numerator / denominator if denominator else None,
        "status": "measured" if denominator else "not-applicable",
    }


def load_corpus(path=FIXTURES):
    if path.stat().st_size > 2_000_000:
        raise ValueError("fixture_size_limit")
    return Corpus.model_validate_json(path.read_bytes())


def grade(case, actions, consumed_ids):
    """Post-execution scorer. No reference to this function in the task driver."""
    rubric = case.expected
    observed = [a.action for a in actions]
    answers = [a.answer for a in actions if a.action == "answer"]
    citations = {key for a in actions for key in a.evidence_ids}
    required = set(rubric.required_actions)
    forbidden = sum(a in rubric.prohibited_actions for a in observed)
    missing = sorted(required - set(observed))
    abstained = "abstain" in observed
    answer_correct = answers == ([] if rubric.abstain else [rubric.answer])
    citation_correct = set(rubric.citation_ids) <= citations
    unsupported_refs = sorted(citations - set(consumed_ids))
    sources = {s.source_id: s for s in case.sources}
    invalid_success = []
    for action in actions:
        if action.action != "reuse_workflow":
            continue
        valid = len(action.evidence_ids) == 1
        for key in action.evidence_ids:
            source = sources.get(key)
            valid = bool(
                valid
                and source
                and source.receipt
                and source.authority == "tool_receipt_verified"
                and source.receipt.outcome == "success"
                and source.receipt.receipt_id == action.receipt_id
                and source.receipt.revision == action.revision == case.task.revision
                and action.arguments.get("command") == source.receipt.command
                and action.verification == "verified"
            )
        if not valid:
            invalid_success.append(action.action)
    passed = (
        not missing
        and not forbidden
        and answer_correct
        and citation_correct
        and abstained == rubric.abstain
        and not unsupported_refs
        and not invalid_success
    )
    return {
        "passed": passed,
        "required_actions": {
            "numerator": len(required) - len(missing),
            "denominator": len(required),
        },
        "missing_actions": missing,
        "prohibited_action_count": forbidden,
        "answer_correct": answer_correct,
        "citation_correct": citation_correct,
        "incorrect_abstention": abstained != rubric.abstain,
        "unsupported_evidence_ids": unsupported_refs,
        "unverified_success_claims": invalid_success,
    }


def run_case(case: Case, arm):
    if arm not in ARMS:
        raise ValueError("unknown_arm")
    started, cpu = perf_counter(), process_time()
    env = Environment(case, include_memories=arm == "fixed" and case.task.use_memory)
    env.apply("before_query")
    eligible = [s.source_id for s in case.sources if env.eligible(s.source_id)]
    eligibility = {s.source_id: env.eligibility_reason(s.source_id) for s in case.sources}
    current_ids = [s.source_id for s in case.sources if s.current]
    diagnostics, trace = [], []
    dependencies = {}
    retrieval = None
    with env.request():
        if arm == "fixed" and case.task.use_memory:
            retrieval = MemoryRetriever(
                env.settings,
                env.memories,
                env.messages,
                env.embedder,
                lifecycle_repository=env.lifecycle,
                clock=lambda: case.clock_utc,
            ).retrieve(case.scope.owner_id, case.task.instruction, [])
            diagnostics = list(retrieval.diagnostics)
            selected = [env.by_memory_id[str(item.memory.id)] for item in retrieval.selected]
            dependencies = {
                env.by_memory_id[str(key)]: deps
                for key, deps in retrieval.permission_dependencies
                if str(key) in env.by_memory_id
            }
            if retrieval.trace:
                trace = [
                    {
                        "source_id": env.by_memory_id.get(str(row.memory_id)),
                        "disposition": row.disposition,
                        "lifecycle": row.lifecycle,
                        "estimated_tokens": row.estimated_tokens,
                    }
                    for row in retrieval.trace.candidates
                ]
        elif arm == "none" or not case.task.use_memory:
            selected = []
        else:
            proposed = case.gold_evidence_ids if arm == "gold_authorized" else eligible
            selected = sorted(
                (key for key in proposed if env.eligible(key)),
                key=lambda key: (env.sources[key].observed_at, key),
            )
            dependencies = {key: (env.dependency(key),) for key in selected}
        env.apply("before_pack")
        eligible_at_pack = [k for k in eligible if env.eligible(k)]
        if arm == "fixed":
            built = env.assembler.assemble(
                [], env.pending, retrieval=retrieval, refresh=False, clock=lambda: case.clock_utc
            )
            packed = [env.by_memory_id[str(key)] for key in built.selected_memory_ids]
            total_tokens, memory_tokens = built.budget.selected_total, built.memory_tokens
            evidence = {key: env.fixed_visible(key) for key in packed}
        else:
            base = env.assembler.assemble(
                [], env.pending, refresh=False, clock=lambda: case.clock_utc
            )
            entries = [
                ContextBuildItem(
                    source_class="domain_history",
                    provider_id="mem0.diagnostic",
                    source_id=key,
                    item_id=key,
                    content=visible_source(env.sources[key]).model_dump_json(),
                    authority="external",
                    sensitivity="public",
                    order=index,
                    source_refs=(ContextSourceReference(kind="source", reference_id=key),),
                    permission_dependencies=dependencies[key],
                )
                for index, key in enumerate(selected)
            ]
            policy = ContextBuildPolicy.for_settings(env.settings, case.maximum_context_tokens)
            limits = dict(policy.source_max_tokens)
            limits["domain_history"] = case.history_tokens
            built = ContextBuilder(
                env.counter, permission_revalidator=env, clock=lambda: case.clock_utc
            ).build(base.messages, entries, policy.model_copy(update={"source_max_tokens": limits}))
            packed = list(built.manifest.injected_item_ids)
            total_tokens = built.token_count
            memory_tokens = built.source_tokens
            evidence = {key: visible_source(env.sources[key]) for key in packed}
        invalid_packed = [key for key in packed if not env.eligible(key)]
        if arm == "none" and (selected or packed):
            raise ValueError("none_arm_history_leak")
        env.apply("before_use")
        consumed = [key for key in packed if all(env.is_current(d) for d in dependencies[key])]
        visible = tuple(
            [visible_source(env.sources[k]) for k in current_ids] + [evidence[k] for k in consumed]
        )
        view = DriverInput(task=case.task, evidence=visible)
        actions = run_driver(view)
        scores = grade(case, actions, (*current_ids, *consumed))
    eligible_gold = {key for key in case.gold_evidence_ids if env.eligible(key)}
    relevant = set(case.gold_evidence_ids) & set(eligible)
    fixed_unsupported = sorted(key for key in eligible_gold if key not in env.records)
    applicability = "evaluable"
    reasons = []
    if arm == "fixed" and fixed_unsupported:
        applicability = "unsupported"
        reasons.append("unsupported_by_current_contract")
    if arm == "fixed" and "retrieval_failed" in diagnostics:
        applicability = "unverified"
        reasons.append("fixed_retrieval_unavailable")
    if arm == "full_eligible_history" and set(eligible_at_pack) - set(packed):
        applicability = "truncated"
        reasons.append("eligible_history_exceeds_final_budget")
    violations = []
    if invalid_packed:
        violations.append("ineligible_packed_source")
    if scores["unsupported_evidence_ids"]:
        violations.append("unsupported_evidence_use")
    if scores["unverified_success_claims"]:
        violations.append("unverified_success_claim")
    if any(a.action not in case.task.allowed_actions for a in actions):
        violations.append("action_outside_tool_authority")
    if total_tokens > case.maximum_context_tokens:
        violations.append("global_budget_exceeded")
    if any(not env.eligible(k) for k in consumed):
        violations.append("ineligible_consumed_source")
    row = {
        "case_id": case.case_id,
        "family": case.family,
        "split": case.split,
        "arm": arm,
        "execution_status": "failed" if violations else "passed",
        "applicability": applicability,
        "reason_codes": reasons,
        "eligible_ids": eligible,
        "eligible_ids_at_pack": eligible_at_pack,
        "selected_ids": selected,
        "packed_ids": packed,
        "eligibility_at_query": eligibility,
        "consumed_ids": consumed,
        "revalidation_dropped_ids": [key for key in packed if key not in consumed],
        "omitted_eligible_ids": [key for key in eligible_at_pack if key not in packed],
        "current_ids": current_ids,
        "fixed_unsupported_ids": fixed_unsupported,
        "retrieval_trace": trace,
        "diagnostics": diagnostics,
        "invariant_violations": violations,
        "source_age_seconds": {
            s.source_id: (case.clock_utc - s.observed_at).total_seconds()
            for s in case.sources
            if s.source_id in consumed
        },
        "task_metric_kind": "synthetic_scripted_task_proxy",
        "task_status": ("passed" if scores["passed"] else "failed")
        if applicability == "evaluable"
        else applicability,
        "scores": scores,
        "action_trace": [a.model_dump(mode="json") for a in actions],
        "retrieval_recall": measurement(len(relevant & set(selected)), len(relevant)),
        "retrieval_precision": measurement(len(relevant & set(selected)), len(selected)),
        "packed_gold_coverage": measurement(len(eligible_gold & set(consumed)), len(eligible_gold)),
        "resources": {
            "prompt_tokens_estimated_word_units": total_tokens,
            "history_tokens_estimated_word_units": memory_tokens,
            "input_budget": case.maximum_context_tokens,
            "history_budget": case.history_tokens,
            "logical_embedding_calls": len(env.embedder.calls),
            "tool_calls": sum(a.action not in ("answer", "abstain") for a in actions),
            "physical_provider_attempts": 0,
            "serialized_diagnostic_context_bytes": sum(
                len(evidence[k].model_dump_json().encode()) for k in consumed
            )
            if arm not in ("none", "fixed")
            else 0,
            "serialized_memory_bytes": sum(
                len(r.model_dump_json().encode()) for r in env.records.values()
            ),
            "native_store_read_bytes": None,
            "native_store_write_bytes": None,
            "provider_quota": None,
            "real_model_quality": None,
        },
    }
    return row, {
        "case_id": case.case_id,
        "arm": arm,
        "elapsed_ms": (perf_counter() - started) * 1000,
        "cpu_ms": (process_time() - cpu) * 1000,
    }


def fraction(rows):
    evaluable = [
        r for r in rows if r["applicability"] == "evaluable" and r["execution_status"] == "passed"
    ]
    numerator = sum(r["task_status"] == "passed" for r in evaluable)
    return {
        "numerator": numerator,
        "denominator": len(evaluable),
        "fraction": numerator / len(evaluable) if evaluable else None,
        "case_ids": [r["case_id"] for r in evaluable],
        "excluded": [
            {
                "case_id": r["case_id"],
                "status": r["applicability"],
                "execution_status": r["execution_status"],
            }
            for r in rows
            if r not in evaluable
        ],
    }


def aggregate(rows):
    groups = {}
    for arm in ARMS:
        arm_rows = [r for r in rows if r["arm"] == arm]
        families = {
            family: fraction([r for r in arm_rows if r["family"] == family]) for family in FAMILIES
        }
        values = [v["fraction"] for v in families.values() if v["fraction"] is not None]
        groups[arm] = {
            "micro": fraction(arm_rows),
            "by_family": families,
            "macro_family_fraction": sum(values) / len(values) if values else None,
            "macro_family_denominator": len(values),
            "by_split": {
                split: fraction([r for r in arm_rows if r["split"] == split])
                for split in ("development", "calibration", "frozen_holdout")
            },
            "applicability_counts": dict(Counter(r["applicability"] for r in arm_rows)),
            "harmful_actions": sum(r["scores"]["prohibited_action_count"] for r in arm_rows),
        }
    paired = {}
    for baseline in ("none", "fixed"):
        base = {r["case_id"]: r for r in rows if r["arm"] == baseline}
        for arm in ARMS:
            if arm == baseline:
                continue
            deltas = []
            excluded = []
            for row in (r for r in rows if r["arm"] == arm):
                other = base.get(row["case_id"])
                if other is None:
                    excluded.append(row["case_id"])
                    continue
                if any(
                    r["applicability"] != "evaluable" or r["execution_status"] != "passed"
                    for r in (row, other)
                ):
                    excluded.append(row["case_id"])
                    continue
                delta = int(row["task_status"] == "passed") - int(other["task_status"] == "passed")
                deltas.append({"case_id": row["case_id"], "delta": delta})
            paired[f"{arm}_vs_{baseline}"] = {
                "denominator": len(deltas),
                "deltas": deltas,
                "excluded_ids": excluded,
                "wins": sum(d["delta"] > 0 for d in deltas),
                "ties": sum(d["delta"] == 0 for d in deltas),
                "regressions": [d["case_id"] for d in deltas if d["delta"] < 0],
                "mean_delta": sum(d["delta"] for d in deltas) / len(deltas) if deltas else None,
            }
    return {"by_arm": groups, "paired": paired}


def execution_status(rows):
    if any(r["execution_status"] == "failed" for r in rows):
        return "failed"
    if any(r["applicability"] == "unverified" for r in rows):
        return "unverified"
    return "passed"


def source_identity():
    paths = sorted((ROOT / "backend/src/personal_ai").rglob("*.py"))
    paths += [ROOT / "backend/pyproject.toml", ROOT / "backend/uv.lock"]
    return digest({str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in paths})


def evaluate(corpus):
    rows, timings = [], []
    for case in corpus.cases:
        for arm in ARMS:
            row, timing = run_case(case, arm)
            rows.append(row)
            timings.append(timing)
    result = {"rows": rows, "aggregate": aggregate(rows)}
    return result, timings


def write_run(fixtures=FIXTURES, output=OUTPUT):
    output = output.resolve()
    if not output.is_relative_to(OUTPUT.resolve()):
        raise ValueError("output_must_be_under_artifacts_mem0")
    before = sha256(fixtures.read_bytes()).hexdigest()
    corpus = load_corpus(fixtures)
    identity_before = source_identity()
    result, timings = evaluate(corpus)
    repeated, _ = evaluate(corpus)
    if digest(result) != digest(repeated):
        raise ValueError("nondeterministic_semantic_replay")
    if before != sha256(fixtures.read_bytes()).hexdigest() or identity_before != source_identity():
        raise ValueError("inputs_changed_during_evaluation")
    git = lambda *args: subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    manifest = {
        "benchmark_version": corpus.benchmark_version,
        "rubric_version": corpus.rubric_version,
        "tested_revision": git("rev-parse", "HEAD"),
        "source_tree_dirty": bool(git("status", "--porcelain")),
        "source_sha256": identity_before,
        "fixture_sha256": before,
        "schema_sha256": digest(Corpus.model_json_schema()),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "policy_versions": ["memory-read-v1", "mem0-scripted-policy-v1", "mem0-rubric-v1"],
        "profile": "synthetic-offline-no-provider-dispatch",
        "seed": 0,
        "arms": ARMS,
        "model": None,
        "provider": None,
        "evidence_class": "offline",
        "status": execution_status(result["rows"]),
        "unverified": UNVERIFIED,
        "result_digest": digest(result),
        "replay_equal": True,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "dependencies": {name: version(name) for name in ("pydantic", "pytest")},
        "case_order": [c.case_id for c in corpus.cases],
        "cache_profile": "fresh_in_memory_per_case_arm; process_import_and_OS_caches_uncontrolled",
    }
    timing_summary = {}
    for arm in ARMS:
        values = sorted(t["elapsed_ms"] for t in timings if t["arm"] == arm)
        timing_summary[arm] = {
            "p50_ms": values[len(values) // 2],
            "p95_ms": values[math_ceil95(len(values)) - 1],
        }
    output.mkdir(parents=True, exist_ok=True)
    for name, value in (
        ("manifest", manifest),
        ("cases", result["rows"]),
        ("aggregate", result["aggregate"]),
        ("timings", {"observations": timings, "by_arm": timing_summary}),
    ):
        (output / f"{name}.json").write_text(
            json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
        )
    return manifest


def math_ceil95(count):
    return (95 * count + 99) // 100


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    try:
        manifest = write_run(args.fixtures, args.output)
    except (ValueError, OSError) as error:
        print(canonical({"status": "failed", "reason": type(error).__name__}))
        return 1
    print(canonical(manifest))
    return 0 if manifest["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
