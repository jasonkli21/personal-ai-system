"""Paired synthetic end-to-end research experiments; live quality stays unmeasured."""

import argparse
import asyncio
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit
from uuid import uuid4, uuid5

from personal_ai.agents.research.repositories import InMemoryResearchRepository
from personal_ai.api.research import research_service
from personal_ai.artifacts.consumers import retain_evaluation
from personal_ai.auth.scope import ApplicationScope
from personal_ai.evaluation.provider_matrix import git_revision
from personal_ai.evaluation.research import NOW, _application_context
from personal_ai.evaluation.retrieval_contracts import (
    ResearchExperimentSummary,
    RetrievalMeasurements,
    promotion_reasons,
)
from personal_ai.search.contracts import FakeSearchAdapter, SearchResult
from personal_ai.search.policy import SnippetExtractor
from personal_ai.search.providers.brave import SearchError
from personal_ai.search.runtime import SEARCH_ADAPTERS, SearchAdapterRegistration
from personal_ai.settings import Settings

DIRECTORY = Path(__file__).parent / "fixtures" / "research"
VARIANTS = ("literal-extractive-v1", "compact-extractive-v1", "qualifier-v1", "expansion-v1")


def load_configuration():
    fixture_bytes = (DIRECTORY / "retrieval-heldout-v1.json").read_bytes()
    baseline_bytes = (DIRECTORY / "retrieval-baseline-v1.json").read_bytes()
    baseline = json.loads(baseline_bytes)
    if sha256(fixture_bytes).hexdigest() != baseline["fixture_sha256"]:
        raise ValueError("frozen_baseline_fixture_mismatch")
    return json.loads(fixture_bytes), baseline, sha256(baseline_bytes).hexdigest()


def runtime_identity():
    source = Path(__file__).parents[1]
    files = sorted(source.rglob("*.py"))
    backend = source.parents[1]
    files.extend(backend / name for name in ("pyproject.toml", "uv.lock"))
    return sha256(json.dumps([(str(path.relative_to(backend)), sha256(path.read_bytes()).hexdigest())
                              for path in files]).encode()).hexdigest()


async def measure(case, variant):
    """Use the actual API composition seam with an installed public fixture adapter."""
    from personal_ai.agents.research.contracts import ResearchRequest

    settings = Settings(
        _env_file=None, ai_provider="gemini", ai_model="synthetic", research_enabled=True,
        research_storage="memory", research_search_adapter="heldout",
        research_retrieval_experiments_enabled=True,
        research_packing_strategy=(variant if variant in VARIANTS[:2] else VARIANTS[0]),
        research_max_queries=2 if variant == "expansion-v1" else 1,
        research_query_strategy=variant if variant in {"qualifier-v1", "expansion-v1"}
        else "literal-snippet-v1",
    )
    adapter = FakeSearchAdapter(
        tuple(SearchResult.model_validate(s) for s in case["sources"]),
        error=SearchError(case["adapter_error"]) if case.get("adapter_error") else None,
    )
    # Sequential evaluator only; restore the installed catalog before returning.
    prior = SEARCH_ADAPTERS.get("heldout")
    SEARCH_ADAPTERS["heldout"] = SearchAdapterRegistration(
        lambda settings, usage: adapter, synthetic=True
    )
    try:
        service = research_service(settings, InMemoryResearchRepository(), "local", _application_context())
    finally:
        if prior is None:
            del SEARCH_ADAPTERS["heldout"]
        else:
            SEARCH_ADAPTERS["heldout"] = prior
    service.clock = lambda: NOW
    if case.get("invalid_output"):
        from personal_ai.llm.fake import FakeLLMClient

        service.llm = FakeLLMClient(("Unsupported factual claim [99]",))
    synthesis_calls, counting_calls, output_bytes = 0, 0, 0
    original_stream = service.llm.stream_bounded
    original_count = service.context.counter.count

    async def observed_stream(*args, **kwargs):
        nonlocal synthesis_calls, output_bytes
        synthesis_calls += 1
        async for delta in original_stream(*args, **kwargs):
            output_bytes += len(delta.encode())
            yield delta

    def observed_count(*args, **kwargs):
        nonlocal counting_calls
        counting_calls += 1
        return original_count(*args, **kwargs)

    service.llm.stream_bounded = observed_stream
    service.context.counter.count = observed_count
    request = ResearchRequest(question=case["question"], freshness=case.get("freshness", "general"),
                              idempotency_key=uuid4())
    started = perf_counter()
    created = await service.create(request)
    claimed = await service.prepare_run(created.id)
    async for _ in service.stream(claimed):
        pass
    session = await service.detail(created.id)
    latency = (perf_counter() - started) * 1000
    evidence = {e.id: e for e in session.evidence}
    selection = session.selection
    selected = selection.evidence_ids if selection else ()
    passages = {evidence[i].passage for i in selected}
    oracle = set()
    for source in case["sources"]:
        try:
            passage = SnippetExtractor().extract(source["text"])
        except Exception:  # noqa: BLE001, S112 - deliberately malformed fixture snippets
            continue
        if case["expected"] == "completed" and passage:
            oracle.add(passage)
    hits = len(oracle & passages)
    supports = selection.derived.support if selection and selection.derived else ()
    exact = bool(selection) and len(supports) == len(selected) and all(
        s.fingerprint == evidence[s.evidence_id].content_fingerprint
        and s.end == len(evidence[s.evidence_id].passage)
        for s in supports
    )
    conflict = case["name"] in {"conflicting-sources", "near-duplicate-negation"}
    fresh = all(evidence[i].expires_at > NOW for i in selected)
    completed = session.state == "completed"
    metrics = RetrievalMeasurements(
        constraint_retention=float(all(q.normalized_query.startswith(request.question)
                                       for q in session.queries)),
        evidence_recall=hits / len(oracle) if oracle else 1,
        evidence_precision=hits / len(passages) if passages else 1,
        freshness_compliance=float(fresh),
        source_diversity=len({urlsplit(s.canonical_url).hostname for s in session.observations
                              if s.status == "accepted"}),
        conflict_visibility=float(oracle <= passages) if conflict else None,
        exact_support=float(exact) if selection else 1,
        # Strict literal validator establishes support/citations for the excerpt
        # answer. It does not establish live model question-answering quality.
        supported_answer=float(completed) if oracle else None,
        unsupported_claim_rate=0 if completed else None,
        citation_correctness=1 if completed else None,
        calls=len(adapter.calls), quota=None,
        synthesis_invocations=synthesis_calls, token_count_invocations=counting_calls,
        total_token_estimate=(selection.token_count if selection else 0)
        + int(output_bytes * 1.1 + .999),
        retrieved_bytes=sum(len(s.text.encode()) for s in adapter.results) * len(adapter.calls),
        packed_tokens=selection.token_count if selection else 0, latency_ms=latency,
    )
    return metrics, session


async def run(*, repository=None, artifacts=None, owner_id="local", scope=None):
    cases, frozen, baseline_digest = load_configuration()
    run_id, timestamp = uuid4(), datetime.now(UTC)
    scope = scope or ApplicationScope()
    rows, summaries = [], []
    for case in cases:
        control, _ = await measure(case, VARIANTS[0])
        for variant in VARIANTS[1:]:
            candidate, session = await measure(case, variant)
            config = {"strategy": variant, "max_queries": 2 if variant == "expansion-v1" else 1,
                      "origin": "synthetic_offline", "scorer": "literal-support-v1",
                      "runtime_identity": runtime_identity()}
            summary = ResearchExperimentSummary(
                id=uuid5(run_id, case["name"] + ":" + variant), owner_id=owner_id,
                application_id=scope.application_id, workspace_id=scope.workspace_id,
                evaluation_run_id=run_id, case_id=case["name"], task_family=case["name"],
                source_profile="synthetic-public-v1", strategy_id=variant,
                configuration_sha256=sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
                fixture_sha256=frozen["fixture_sha256"], baseline_sha256=baseline_digest,
                tested_revision=git_revision(), baseline=control, candidate=candidate,
                created_at=timestamp, expires_at=timestamp + timedelta(days=30),
            )
            summaries.append(summary)
            rows.append({"name": case["name"] + ":" + variant, "state": session.state,
                         "variant": variant, "baseline": control.model_dump(),
                         "candidate": candidate.model_dump(),
                         "promotion_reasons": promotion_reasons(summary)})
    artifact = None
    if artifacts is not None:
        artifact = retain_evaluation(artifacts, rows, owner_id=owner_id, scope=scope,
                                     evaluation_run_id=run_id)
    if artifact is not None:
        share, remainder = divmod(artifact.compressed_bytes, len(summaries))
        summaries = [summary.model_copy(update={
            "artifact_id": artifact.artifact_id,
            "candidate": summary.candidate.model_copy(update={
                "retained_artifact_bytes": share + int(index < remainder),
            }),
        }) for index, summary in enumerate(summaries)]
    if repository is not None:
        for summary in summaries:
            repository.save(summary)
    return {"schema_version": "research-paired-eval-v1", "origin": "synthetic_offline",
            "frozen_baseline": frozen, "promotion": "not_promoted", "rows": rows,
            "artifact_status": "ready" if artifact else "not_retained",
            "retained_artifact_bytes": artifact.compressed_bytes if artifact else 0,
            "live_answer_quality": "unmeasured", "quota": "unmeasured"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--persist-owner", help="Explicit canonical evaluation owner; opt-in Postgres/P20")
    args = parser.parse_args()
    repository, artifacts = None, None
    if args.persist_owner:
        from personal_ai.persistence.factory import persistence_factory
        from personal_ai.settings import get_settings

        settings = get_settings()
        factory = persistence_factory(settings)
        repository = factory.research_experiment_repository()
        artifacts = factory.artifact_service(settings)
    print(json.dumps(asyncio.run(run(repository=repository, artifacts=artifacts,
                                     owner_id=args.persist_owner or "local")), indent=2))


if __name__ == "__main__":
    main()
