"""Sealed paired experiment. Score only after each arm has finished."""

import asyncio
import json
from hashlib import sha256
from pathlib import Path
from random import Random
from statistics import mean
from tempfile import TemporaryDirectory
from uuid import NAMESPACE_URL, uuid5

from personal_ai.reasoning import adaptive
from personal_ai.workflow.reasoning import ENDPOINT_DIGEST

from .fixture import observe
from .lock import SEAL_SHA256
from .scoring import interval, percentile, score, work

FILES = Path(__file__).parent
SOURCE = FILES.parents[1]
LANE = ("cases.json", "split.json", "oracle.json", "manifest.json", "runner.py", "fixture.py", "scoring.py")
RUNTIME = (
    "reasoning/adaptive.py", "reasoning/adaptive_control.py", "reasoning/adaptive_plan.py", "reasoning/orchestration.py",
    "reasoning/grounded.py", "reasoning/grounded_receipts.py", "reasoning/adaptive_receipts.py",
    "contracts/reasoning_workflow.py", "workflow/adaptive.py", "workflow/reasoning.py",
    "workflow/service.py", "workflow/grounded.py", "workflow/grounded_execution.py",
    "persistence/postgres/workflows.py", "llm/execution.py", "llm/fake.py", "llm/synthetic_reasoning.py",
    "llm/workflow_fixture.py", "services/chat/service.py", "context/assembler.py", "retrieval/service.py",
    "evaluation/reasoning_grounded/fixture.py", "evaluation/reasoning_orchestrator/fixture.py",
)


def load(directory=FILES):
    seal = (directory / "seal.json").read_bytes()
    if sha256(seal).hexdigest() != SEAL_SHA256:
        raise ValueError("adaptive_experiment_seal_changed")
    lock = json.loads(seal)
    groups = {"lane": (directory, LANE), "runtime": (SOURCE, RUNTIME)}
    if set(lock) != {*groups, "policies"} or lock["policies"] != {
        policy.policy: policy.identity for policy in (adaptive.FINITE, adaptive.GROUNDED)
    }:
        raise ValueError("adaptive_experiment_policy_changed")
    for kind, (root, files) in groups.items():
        if set(lock[kind]) != set(files) or any(
            sha256((root / name).read_bytes()).hexdigest() != lock[kind][name] for name in files
        ):
            raise ValueError("adaptive_experiment_member_changed")
    manifest, cases, split, oracle = (
        json.loads((directory / f"{name}.json").read_bytes())
        for name in ("manifest", "cases", "split", "oracle")
    )
    if (
        set(cases) != set(split) or set(cases) != set(oracle) or set(manifest["holdout"]) != {"finite", "grounded"}
        or sum(sum(manifest[p].values()) for p in ("holdout", "development")) != len(cases)
        or any(
            sum(split[key]["partition"] == partition and case["profile"] == profile for key, case in cases.items())
            != count
            for partition in ("holdout", "development") for profile, count in manifest[partition].items()
        )
        or any(
            {"values", "eligible", "partition", "stratum", "oracle"} & case.keys()
            for case in cases.values()
        )
    ):
        raise ValueError("adaptive_experiment_split_or_custody_changed")
    return manifest, cases, split, oracle


def summarize(rows, manifest):
    by_arm, deltas, subgroups = {}, {}, {}
    for profile, contender in (("finite", "adaptive"), ("grounded", "one_shot")):
        selected = [row for row in rows if row["profile"] == profile]
        arms = manifest[f"{profile}_arms"]
        for arm in arms:
            group = [row for row in selected if row["arm"] == arm]
            exact = sum(row["exact"] for row in group)
            total_work = sum(row["work"] for row in group)
            latency = [row["elapsed_ms"] for row in group]
            by_arm[f"{profile}/{arm}"] = {
                "rows": len(group), "exact": exact, "work": round(total_work, 8),
                "exact_per_work": round(exact / total_work, 8) if total_work else None,
                "p50_ms": percentile(latency, 0.50), "p95_ms": percentile(latency, 0.95),
                "safety_vetoes": sum(not row["safe"] for row in group),
            }
        heldout = [row for row in selected if row["partition"] == "holdout" and row["arm"] == contender]
        options = {"seed": manifest["seeds"]["bootstrap"], "draws": manifest["bootstrap_draws"],
                   "confidence": manifest["confidence"]}
        for name, group in (("all", heldout), ("eligible", [row for row in heldout if row["eligible"]])):
            deltas[f"{profile}/{name}"] = {
                "exact": interval([row["paired_exact_delta"] for row in group], **options),
                "utility": interval([row["paired_utility_delta"] for row in group], **options),
            }
        for stratum in sorted({row["stratum"] for row in heldout}):
            group = [row for row in heldout if row["stratum"] == stratum]
            subgroups[f"{profile}/{stratum}"] = {
                "n": len(group), "exact_delta": sum(row["paired_exact_delta"] for row in group),
                "mean_utility_delta": round(mean(row["paired_utility_delta"] for row in group), 8),
            }
    return by_arm, deltas, subgroups


async def evaluate(*, case_ids=None):
    manifest, cases, split, oracle = load()
    rows = []
    rng = Random(manifest["seeds"]["arm_order"])
    with TemporaryDirectory(prefix="adaptive-eval-") as tmp:
        for case_id, case in cases.items():
            if case_ids is not None and case_id not in case_ids:
                continue
            profile = case["profile"]
            arms = list(manifest[f"{profile}_arms"])
            rng.shuffle(arms)
            pair = {}
            for arm in arms:
                key = uuid5(NAMESPACE_URL, f"reasoning-adaptive-v1/{case_id}/{arm}")
                with TemporaryDirectory(dir=tmp) as arm_dir:
                    observation = await observe(key, case, arm, Path(arm_dir).resolve())
                exact, safe, supported = score(case, oracle[case_id], observation)
                observation.pop("result")
                observation.pop("wire")
                expected_fault = {
                    "quota": "budget_exhausted", "deadline": "budget_exhausted", "cancel": "uncertain_effect",
                    "unknown": "uncertain_effect",
                }.get(case["fault"])
                if expected_fault is not None:
                    safe &= observation["reason"] == expected_fault and supported == 0
                if case["fault"] == "denied":
                    safe &= not supported and not any(
                        usage["dispatched"] for usage in observation["ledger"]["operations"].values()
                    )
                if arm in {"baseline", "shadow", "adaptive"}:
                    safe &= not observation["work_after_pass"]
                pair[arm] = {
                    "case_id": case_id, "profile": profile, "arm": arm, **split[case_id],
                    "eligible": oracle[case_id]["eligible"], **observation,
                    "exact": exact, "safe": bool(safe), "supported_slots": supported,
                    "work": work(observation["ledger"], manifest["work_units"]),
                }
            baseline, shadow = pair["baseline"], pair["shadow"]
            same = ("exact", "supported_slots", "outcome", "reason", "ledger")
            shadow["safe"] &= all(shadow[key] == baseline[key] for key in same)
            if profile == "finite" and split[case_id]["stratum"].startswith("simple"):
                adaptive_row = pair["adaptive"]
                adaptive_row["safe"] &= adaptive_row["ledger"] == baseline["ledger"]
            for arm in sorted(pair):
                row = pair[arm]
                row["paired_exact_delta"] = int(row["exact"]) - baseline["exact"]
                row["paired_work_delta"] = round(row["work"] - baseline["work"], 8)
                row["paired_utility_delta"] = round(row["paired_exact_delta"] - row["paired_work_delta"], 8)
                rows.append(row)

    vetoes = sum(not row["safe"] for row in rows)
    semantic = adaptive.digest([{k: v for k, v in row.items() if k != "elapsed_ms"} for row in rows])
    report = {
        "rows": len(rows), "cases": len({row["case_id"] for row in rows}), "safety_vetoes": vetoes,
        "custody": manifest["custody"], "semantic_sha256": semantic, "seal_sha256": SEAL_SHA256,
        "fixture_endpoint_sha256": ENDPOINT_DIGEST,
        "fixture_verdict": "SAFETY_VETO" if vetoes else "OFFLINE_SIGNAL_ONLY",
        "promotion": "NO_PROMOTION", "live_gates": "BLOCKED_UNVERIFIED", "external_harness": "NOT_RUN",
    }
    if case_ids is None:
        report["totals"], report["heldout_paired_95ci"], report["heldout_subgroups"] = summarize(rows, manifest)
    return report, rows


def main():
    report, rows = asyncio.run(evaluate())
    print(json.dumps({"observations": rows}, sort_keys=True))
    print(json.dumps(report, sort_keys=True))
    return int(bool(report["safety_vetoes"]))


if __name__ == "__main__":
    raise SystemExit(main())
