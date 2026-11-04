"""Author-visible, hash-pinned E1 retrieval study; no model or network mode."""

import json
import platform
from collections import Counter, defaultdict
from datetime import datetime
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from statistics import mean, pstdev
from time import monotonic

from personal_ai.auth.scope import RequestScope
from personal_ai.context.builder import SOURCE_CLASSES, ContextBuildPolicy
from personal_ai.llm.client import EmbeddingSpace
from personal_ai.memory.contracts import MemoryQuery
from personal_ai.memory.research.contracts import ResearchQuery, ResearchResult, digest
from personal_ai.memory.research.engine import MemoryNavigationResearch
from personal_ai.memory.research.source import CORPUS_SHA256, FixtureAuthority, fixture

MANIFEST_SHA256 = "871fd335e6233981b27251d00b98d3236fdcb3667fae6a5fb944e84addbc0ba5"


def study():
    payload = (
        files("personal_ai.evaluation")
        .joinpath("fixtures/memory/memory-navigation-study-v2.json")
        .read_bytes()
    )
    if sha256(payload).hexdigest() != MANIFEST_SHA256:
        raise ValueError("study_manifest_changed")
    value = json.loads(payload)
    if value["fixture_sha256"] != CORPUS_SHA256 or value["cases"] != len(fixture()["cases"]):
        raise ValueError("study_fixture_changed")
    return value


def policy(*, global_tokens=4096, memory_tokens=1024):
    return ContextBuildPolicy(
        global_input_tokens=global_tokens,
        source_max_tokens={
            s: min(global_tokens, memory_tokens) if s == "ai_memory" else global_tokens
            for s in SOURCE_CLASSES
        },
    )


def query_for(case, arm="lexical", *, now=None):
    text = case["query"]
    canonical = MemoryQuery(
        scope=RequestScope(**case["scope"], request_id="navigation-study"),
        max_items=16,
        max_tokens=1024,
        candidate_limit=100,
        sensitivity_ceiling="public",
        embedding_space=EmbeddingSpace(
            "fake",
            "unavailable-real-embedding",
            3,
            "l2",
            "RETRIEVAL_DOCUMENT",
            "RETRIEVAL_QUERY",
            "v1",
        ),
        strategy="fixed",
        as_of=now or datetime.fromisoformat(fixture()["clock"]),
        query_fingerprint=sha256(text.encode()).hexdigest(),
        time_budget_seconds=2,
        deadline=monotonic() + (-1 if case.get("expired_deadline") else 2),
    )
    return ResearchQuery(
        canonical=canonical,
        project=case["project"],
        text=text,
        arm=arm,
        kinds=case.get("kinds", ()),
        source_classes=case.get("source_classes", ()),
        observed_after=case.get("observed_after"),
    )


def score(case, result, source, query):
    """Rubric sees results only after the consumer finishes; it never steers ranks."""
    expected = set(case["expected_ids"])
    selected, packed = set(result.selected_ids), set(result.packed_ids)
    expected_citations = {source._records[i].source_id for i in expected}
    actual_citations = set(result.citations)
    successful = result.status == case["expected_status"] and (
        result.status != "ok" or result.answer == case["expected_answer"]
    )
    leaks = 0
    if result.status == "ok":
        for identifier in selected | packed:
            if identifier not in source._records or not source.eligible(
                source._records[identifier], query
            ):
                leaks += 1
    else:
        leaks = int(bool(selected or packed or result.answer or actual_citations))
    false_support = int(
        result.answer is not None
        and (
            result.answer != case["expected_answer"]
            or not actual_citations
            or not actual_citations.issubset(expected_citations)
        )
    )
    return {
        "success": successful,
        "abstained": result.status == "ok" and result.answer is None,
        "exact_attribution": actual_citations == expected_citations
        if expected
        else not actual_citations,
        "false_support": false_support,
        "violations": leaks,
        "recall": len(selected & expected) / len(expected) if expected else None,
        "precision": len(selected & expected) / len(selected) if selected else None,
        "packed_recall": len(packed & expected) / len(expected) if expected else None,
    }


def source_identities():
    source_root = Path(__file__).parents[1]
    dependencies = (
        source_root / "context/builder.py",
        source_root / "context/tokens.py",
        source_root / "context/contracts.py",
        source_root / "memory/contracts.py",
        source_root / "memory/services.py",
        source_root / "memory/dependencies.py",
        source_root / "retrieval/service.py",
        source_root / "llm/client.py",
    )
    paths = [Path(__file__), *source_root.joinpath("memory/research").glob("*.py"), *dependencies]
    return {
        str(path.relative_to(Path(__file__).parents[1])): sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
        if path.is_file()
    }


def run_study():
    inputs = source_identities()
    manifest, corpus = study(), fixture()
    rows = []
    for case in corpus["cases"]:
        # Rubric fields are not passed to the engine or consumer.
        task = {k: v for k, v in case.items() if not k.startswith("expected")}
        for arm in manifest["arms"]:
            source = FixtureAuthority()
            engine = MemoryNavigationResearch(source, enabled=True)
            query = query_for(task, arm)

            def hook(stage, task=task, source=source):
                mutation = task.get("mutation")
                if mutation and mutation["stage"] == stage:
                    source.transition(mutation["action"], mutation["id"])

            failure_kind = None
            try:
                result = engine.run(
                    query,
                    policy(),
                    cancelled=lambda task=task: task.get("cancel", False),
                    hook=hook,
                )
            except Exception as exc:  # noqa: BLE001 - retain every failed attempt, then fail the run
                failure_kind = type(exc).__name__
                result = ResearchResult(status="unavailable", reason="evaluation_failure")
            metrics = score(case, result, source, query)
            rows.append(
                {
                    "case": case["id"],
                    "family": case["family"],
                    "arm": arm,
                    "result": result.model_dump(mode="json"),
                    "failure_kind": failure_kind,
                    **metrics,
                }
            )
    aggregates, paired = {}, {}
    for arm in manifest["arms"]:
        attempted = [r for r in rows if r["arm"] == arm]
        complete = [r for r in attempted if r["result"]["status"] == "ok"]
        supported = [r for r in attempted if r["result"]["status"] != "unsupported"]
        aggregates[arm] = {
            "denominator": len(attempted),
            "supported": len(supported),
            "complete": len(complete),
            "success": sum(r["success"] for r in supported),
            "success_completed": sum(r["success"] for r in complete),
            "success_boundaries": sum(r["success"] for r in supported if r not in complete),
            "abstentions": sum(r["abstained"] for r in complete),
            "exact_attribution": sum(r["exact_attribution"] for r in complete),
            "false_support": sum(r["false_support"] for r in attempted),
            "violations": sum(r["violations"] for r in attempted),
            "statuses": dict(Counter(r["result"]["status"] for r in attempted)),
            "reasons": dict(Counter(r["result"]["reason"] for r in attempted)),
            "mean_tokens": mean(r["result"]["tokens"] for r in complete) if complete else None,
            "mean_memory_tokens": mean(r["result"]["memory_tokens"] for r in complete)
            if complete
            else None,
            "mean_latency_ms": mean(r["result"]["elapsed_ms"] for r in attempted),
            "max_index_bytes": max(r["result"]["index_bytes"] for r in attempted),
            "mean_index_build_ms": mean(r["result"]["index_build_ms"] for r in attempted)
            if attempted
            else None,
            "mean_preflight_ms": mean(r["result"]["preflight_ms"] for r in attempted)
            if attempted
            else None,
            "mean_retrieval_ms": mean(r["result"]["retrieval_ms"] for r in attempted)
            if attempted
            else None,
            "mean_packing_ms": mean(r["result"]["packing_ms"] for r in attempted)
            if attempted
            else None,
            "mean_consume_ms": mean(r["result"]["consume_ms"] for r in attempted)
            if attempted
            else None,
            "recall": mean(r["recall"] for r in complete if r["recall"] is not None)
            if any(r["recall"] is not None for r in complete)
            else None,
            "precision": mean(r["precision"] for r in complete if r["precision"] is not None)
            if any(r["precision"] is not None for r in complete)
            else None,
            "provider_calls": 0,
            "reported_usage": None,
            "cost": "offline_no_charge",
            "model_quality": "unmeasured",
            "evidence": "E1_author_visible",
        }
        families = defaultdict(list)
        for row in supported:
            base = next(r for r in rows if r["arm"] == "no_memory" and r["case"] == row["case"])
            if base["result"]["status"] != "unsupported":
                families[row["family"]].append(int(row["success"]) - int(base["success"]))
        paired[arm] = {
            f: {
                "n": len(ds),
                "mean_delta": mean(ds),
                "population_sd": pstdev(ds),
                "confidence_interval": None,
            }
            for f, ds in families.items()
        }
    semantic_rows = [
        {k: v for k, v in row.items() if k != "result"}
        | {
            "result": {
                k: v
                for k, v in row["result"].items()
                if k
                not in (
                    "elapsed_ms",
                    "index_build_ms",
                    "preflight_ms",
                    "retrieval_ms",
                    "packing_ms",
                    "consume_ms",
                    "generation",
                )
            }
        }
        for row in rows
    ]
    if source_identities() != inputs:
        raise ValueError("study_source_changed_during_run")
    study()
    fixture()
    return {
        "manifest": manifest,
        "manifest_sha256": MANIFEST_SHA256,
        "source_hashes": inputs,
        "fixture_sha256": CORPUS_SHA256,
        "semantic_replay_digest": digest(semantic_rows),
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "aggregates": aggregates,
        "paired_vs_no_memory": paired,
        "rows": rows,
        "limitations": [
            "scripted consumer only",
            "no independent holdout",
            "no real embeddings",
            "no model utility",
            "native and deployed authority unverified",
            "adaptive and request-aware use lexical recall in this study",
        ],
    }


def main():
    first, second = run_study(), run_study()
    if (
        first["semantic_replay_digest"] != second["semantic_replay_digest"]
        or first["source_hashes"] != second["source_hashes"]
    ):
        raise SystemExit("semantic replay mismatch")
    output = Path("../artifacts/memory-navigation")
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(json.dumps(first, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "semantic_replay_digest": first["semantic_replay_digest"],
                "aggregates": first["aggregates"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if any(row["violations"] or row["failure_kind"] for row in first["rows"]):
        raise SystemExit("safety veto")


if __name__ == "__main__":
    main()
