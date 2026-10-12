"""Paired memory read/maintenance experiments; synthetic evidence never promotes live coverage."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from time import perf_counter, process_time

from personal_ai.context.tokens import FakeTokenCounter
from personal_ai.evaluation.memory_context import MemoryFixtureAssembler
from personal_ai.evaluation.memory_lifecycle import NOW, apply_fixture, build_fixture, load_fixtures
from personal_ai.evaluation.output import emit
from personal_ai.memory.contracts import DerivedMemory, normalize
from personal_ai.memory.services import MemoryRetriever

VERSION = "memory-paired-v1"
VARIANTS = ("fixed", "compact", "consolidated")
# Declared before evaluating. Missing external/answer/resource evidence denies promotion.
PROMOTION = {
    "source_dependency_coverage": 1.0,
    "invalidated_leakage": 0,
    "false_memory": 0,
    "conflict_loss": 0,
    "scope_leakage": 0,
    "maximum_recall_regression": 0,
    "minimum_token_saving_fraction": 0.05,
    "requires_downstream_quality": True,
    "requires_postgres_resources": True,
}


class _EmbeddingObservations:
    def __init__(self, adapter):
        self.adapter = adapter
        self.calls = []

    def embed(self, texts, **kwargs):
        self.calls.append((bool(kwargs.get("query", False)), len(texts)))
        return self.adapter.embed(texts, **kwargs)


def evaluate():
    rows = []
    for fixture in load_fixtures():
        for variant in VARIANTS:
            env = build_fixture(fixture, variant)
            observations = _EmbeddingObservations(env["embedder"])
            env["embedder"] = env["worker"].embedder = observations
            pipeline_started, pipeline_cpu = perf_counter(), process_time()
            apply_fixture(env)
            started, cpu_started = perf_counter(), process_time()
            result = MemoryRetriever(
                env["settings"],
                env["memories"],
                env["messages"],
                env["embedder"],
                env["lifecycle"],
                clock=lambda: NOW,
            ).retrieve("local", "query", [])
            context = MemoryFixtureAssembler(
                env["settings"],
                FakeTokenCounter(),
                memories=env["memories"],
                messages=env["messages"],
                lifecycle=env["lifecycle"],
            ).assemble([], env["pending"], retrieval=result)
            selected = {
                item.memory.id: item.memory
                for item in result.selected
                if item.memory.id in context.selected_memory_ids
            }
            dependencies = dict(result.permission_dependencies)
            supported, false, scope_leakage, covered, required = set(), 0, 0, 0, 0
            for record in selected.values():
                originals = (
                    [
                        env["memories"].get(owner_id="local", memory_id=s.memory_id)
                        for s in record.sources
                    ]
                    if isinstance(record, DerivedMemory)
                    else [record]
                )
                supported.update(normalize(item.content) for item in originals)
                false += sum(
                    normalize(item.content) not in normalize(record.content) for item in originals
                )
                scope_leakage += int(
                    record.owner_id != "local"
                    or record.application_id != "personal_ai"
                    or record.workspace_id is not None
                )
                required += len(originals)
                dep_ids = {
                    dep.entity_ref.entity_id
                    for dep in dependencies.get(record.id, ())
                    if dep.entity_ref and dep.entity_ref.entity_type == "memory"
                }
                covered += sum(str(item.id) in dep_ids for item in originals)
            # The declared baseline target is unique supported claims, not every repeated ID.
            expected = {
                normalize(r.content)
                for label, r in env["records"].items()
                if r.owner_id == "local" and label not in fixture.get("forbidden_labels", ())
            }
            content_bytes = sum(
                len(item.model_dump_json().encode()) for item in env["memories"].records.values()
            )
            content_bytes += sum(
                len(item.model_dump_json().encode())
                for item in env["memories"].derived_records.values()
            )
            rows.append(
                {
                    "fixture": fixture["name"],
                    "variant": variant,
                    "represented_claims": len(supported),
                    "declared_claims": len(expected),
                    "claim_recall": len(supported & expected) / len(expected) if expected else 1,
                    "claim_precision": len(supported & expected) / len(supported)
                    if supported
                    else None,
                    "false_memory": false,
                    "scope_leakage": scope_leakage,
                    "source_dependency_coverage": covered / required if required else 1,
                    "active_exact_duplicates": len(selected)
                    - len({normalize(r.content) for r in selected.values()}),
                    "packed_tokens": context.memory_tokens,
                    "retrieval_and_build_ms": (perf_counter() - started) * 1000,
                    "retrieval_and_build_cpu_ms": (process_time() - cpu_started) * 1000,
                    "original_records": len(env["memories"].records),
                    "derived_records": len(env["memories"].derived_records),
                    "serialized_memory_bytes": content_bytes,
                    "index_bytes": None,
                    "maintenance_jobs": len(env["lifecycle"].jobs),
                    "logical_embedding_calls": len(observations.calls),
                    "query_embedding_calls": sum(query for query, _ in observations.calls),
                    "maintenance_embedding_calls": sum(
                        not query for query, _ in observations.calls
                    ),
                    "total_pipeline_ms": (perf_counter() - pipeline_started) * 1000,
                    "total_pipeline_cpu_ms": (process_time() - pipeline_cpu) * 1000,
                    "model_maintenance_calls": 0,
                    "model_maintenance_tokens": 0,
                    "physical_provider_attempts": 0,
                    "provider_quota_consumption": None,
                    "downstream_answer_quality": None,
                    "authority_confusion": None,
                    "near_duplicate_context_rate": None,
                    "conflict_marked_candidates": sum(
                        row.unresolved_conflict for row in result.trace.candidates
                    )
                    if result.trace
                    else 0,
                    "trace": result.trace.model_dump(mode="json") if result.trace else None,
                }
            )
    paths = sorted(
        path
        for path in Path(__file__).parents[1].rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
        and not path.name.startswith(("planning-baseline-", "memory-baseline-"))
    )
    digest = sha256()
    for path in paths:
        digest.update(str(path.relative_to(Path(__file__).parents[1])).encode())
        digest.update(path.read_bytes())
    for dependency in ("pyproject.toml", "uv.lock"):
        digest.update(dependency.encode())
        digest.update((Path(__file__).parents[3] / dependency).read_bytes())
    return {
        "evaluation_version": VERSION,
        "evidence_kind": "synthetic_offline",
        "source_digest": digest.hexdigest(),
        "criteria": PROMOTION,
        "rows": rows,
        "promoted_coverage": [],
        "promotion_reason": "missing_downstream_quality_and_postgres_resource_evidence",
        "ann_decision": "retain_exact_no_measured_bottleneck",
        "postgres_metrics": None,
    }


if __name__ == "__main__":
    report = evaluate()
    emit(report)
    raise SystemExit(
        0
        if all(
            r["false_memory"] == r["scope_leakage"] == 0 and r["source_dependency_coverage"] == 1
            for r in report["rows"]
        )
        else 1
    )
