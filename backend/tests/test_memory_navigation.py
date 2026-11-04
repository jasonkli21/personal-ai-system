"""Authority, cache, concurrency, bounds and canonical-builder research contracts."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
from time import monotonic

import pytest
from pydantic import ValidationError

from personal_ai.context.builder import ContextBuildItem
from personal_ai.evaluation.memory_navigation import policy, query_for
from personal_ai.memory.research.contracts import ResearchFailure, ResearchQuery, digest
from personal_ai.memory.research.engine import MemoryNavigationResearch
from personal_ai.memory.research.index import browse, fetch_topic, fuse, terms
from personal_ai.memory.research.semantic import CanonicalSemanticRanks
from personal_ai.memory.research.source import FixtureAuthority, fixture


def setup(arm="lexical", **case_changes):
    case = {**fixture()["cases"][0], **case_changes}
    source = FixtureAuthority()
    query = query_for(case, arm)
    return source, MemoryNavigationResearch(source, enabled=True), query


def test_disabled_and_missing_issuer_are_distinct_from_empty_memory():
    _, _, query = setup()
    assert MemoryNavigationResearch().run(query, policy()).status == "disabled"
    assert MemoryNavigationResearch(enabled=True).run(query, policy()).status == "unavailable"
    with pytest.raises(ResearchFailure, match="source_profile_unsupported"):
        MemoryNavigationResearch(object(), enabled=True)


@pytest.mark.parametrize(
    "field,value",
    [
        ("owner_id", "foreign"),
        ("application_id", "shopping"),
        ("workspace_id", "foreign"),
        ("acting_user_id", "foreign"),
    ],
)
def test_scope_fences_before_scoring(field, value):
    base = fixture()["cases"][0]
    _, engine, query = setup(scope={**base["scope"], field: value})
    result = engine.run(query, policy())
    assert result.status == "denied"
    assert not result.selected_ids and not result.packed_ids and result.tokens == 0


def test_index_excludes_other_scopes_expiry_corrections_future_and_restricted():
    source, engine, query = setup()
    index = engine.index(query)
    ids = {e.record_id for e in index.entries}
    assert {"check", "version-new", "conflict-a", "conflict-b"} <= ids
    assert not ids & {
        "version-old",
        "expired",
        "future",
        "withdrawn",
        "old-grant",
        "other-owner",
        "other-app",
        "other-actor",
        "other-project",
        "other-workspace",
        "restricted",
    }
    # Stable ordering/generation after replay and different insertion order.
    source._records = dict(reversed(tuple(source._records.items())))
    assert engine.index(query) == index
    assert len(index.model_dump_json().encode()) < 262144


@pytest.mark.parametrize("stage", ["ranked", "packed", "consume"])
@pytest.mark.parametrize("action", ["forget", "revoke", "correct", "expire", "regrant", "purge"])
def test_last_boundary_mutation_suppresses_all_payload(stage, action):
    source, engine, query = setup()
    result = engine.run(
        query,
        policy(),
        hook=lambda current: source.transition(action, "check") if current == stage else None,
    )
    assert result.status == "denied"
    assert not result.selected_ids and not result.packed_ids and result.answer is None
    assert not result.citations and result.tokens == 0


def test_browse_and_leaf_read_revalidate_independently():
    source, engine, query = setup()
    index = engine.index(query)
    roots = browse(source, index, query)
    root = next(r for r in roots if r.label == "Engineering")
    topic = next(
        t for t in browse(source, index, query, parent_id=root.id) if t.label == "Validation"
    )
    assert "check" in {r.id for r in fetch_topic(source, index, query, topic.id)}
    source.transition("revoke", "check")
    for operation in (
        lambda: browse(source, index, query),
        lambda: fetch_topic(source, index, query, topic.id),
        lambda: source.fetch(index, query, ("check",)),
    ):
        with pytest.raises(ResearchFailure, match="generation_changed"):
            operation()


def test_cache_snapshot_restore_tamper_restart_and_old_identity_regrant_deny():
    source, engine, query = setup()
    snapshot = engine.index(query)
    tampered = snapshot.model_copy(update={"entries": snapshot.entries[1:]})
    with pytest.raises(ResearchFailure, match="index_integrity"):
        browse(source, tampered, query)
    source.transition("revoke", "check")
    source.transition("regrant", "check")
    restarted = MemoryNavigationResearch(source, enabled=True)
    with pytest.raises(ResearchFailure, match="generation_changed"):
        browse(source, snapshot, query)
    assert "check" not in {e.record_id for e in restarted.index(query).entries}
    assert restarted.index(query).generation != snapshot.generation


def test_concurrent_lookup_forget_fences_surviving_snapshot():
    source, engine, query = setup()
    ranked, mutated = Event(), Event()

    def hook(stage):
        if stage == "ranked":
            ranked.set()
            assert mutated.wait(1)

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = pool.submit(engine.run, query, policy(), hook=hook)
        assert ranked.wait(1)
        source.transition("forget", "check")
        mutated.set()
        assert result.result(timeout=1).status == "denied"


def test_concurrent_owner_purge_and_index_build_never_make_old_cache_authority():
    source, engine, query = setup()
    barrier = Barrier(2)

    def index():
        barrier.wait(timeout=1)
        try:
            return engine.index(query)
        except ResearchFailure:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = pool.submit(index)
        barrier.wait(timeout=1)
        source.transition("purge", "check")
        snapshot = result.result(timeout=1)
    if snapshot is not None:
        with pytest.raises(ResearchFailure):
            browse(source, snapshot, query)
    assert engine.run(query, policy()).status == "denied"


def test_current_time_expiry_invalidates_without_any_mutation_event():
    source, engine, query = setup()
    index = engine.index(query)
    source._clock = lambda: query.canonical.as_of + timedelta(days=30)
    with pytest.raises(ResearchFailure, match="generation_changed"):
        browse(source, index, query)


def test_correction_remains_dominant_even_after_withdrawal():
    source, engine, query = setup(query="compiler version")
    source.transition("forget", "version-new")
    assert "version-old" not in {e.record_id for e in engine.index(query).entries}
    assert engine.run(query, policy()).answer is None


def test_conflicts_pack_atomically_and_keep_negation_and_provenance():
    _, engine, query = setup(query="SQLite")
    result = engine.run(query, policy())
    assert set(result.packed_ids) >= {"conflict-a", "conflict-b"}
    assert result.answer == "unresolved"
    index = engine.index(query)
    group = engine.pack(query, index, ("conflict-a", "conflict-b"), policy())
    packed = engine.pack(
        query,
        index,
        ("conflict-a", "conflict-b"),
        policy(memory_tokens=group.build.memory_tokens - 1),
    )
    assert not ({"conflict-a", "conflict-b"} & set(packed.build.included_item_ids))
    _, engine, query = setup(query="deployment publish")
    index = engine.index(query)
    packed = engine.pack(query, index, ("negation",), policy())
    assert "never run publish" in str(packed.build.messages)
    assert packed.build.manifest.items[0].source_reference_count == 1
    assert packed.build.manifest.items[0].dependency_versions
    assert packed.build.manifest.items[0].sensitivity == "public"


def test_poisoned_topic_labels_are_sanitized_and_text_has_no_effects():
    _, engine, query = setup(query="ignore instructions")
    index = engine.index(query)
    assert all("ignore" not in t.label.lower() and "/" not in t.label for t in index.topics)
    result = engine.run(query, policy())
    assert result.status == "ok" and result.provider_calls == 0
    assert result.answer == "untrusted"


@pytest.mark.parametrize("arm", ["lexical", "request_aware", "adaptive", "eligible_full_context"])
def test_memory_cannot_steal_required_current_source_or_exceed_any_budget(arm):
    _, engine, query = setup(arm)
    current = ContextBuildItem(
        source_class="domain_current",
        provider_id="fixture",
        source_id="current",
        item_id="current",
        content="current " * 100,
        authority="authoritative",
        sensitivity="public",
        required=True,
    )
    index = engine.index(query)
    packed = (
        engine.pack(
            query,
            index,
            ("check",),
            policy(global_tokens=200, memory_tokens=80),
            protected=(current,),
        )
        if arm != "eligible_full_context"
        else None
    )
    if packed:
        assert "current" in packed.build.included_item_ids
        assert packed.build.token_count <= 200
        assert packed.build.memory_tokens <= 80
        assert packed.build.token_count == engine.counter.count(packed.build.messages).tokens
    result = engine.run(query, policy(global_tokens=200, memory_tokens=80), protected=(current,))
    if arm == "eligible_full_context":
        assert (
            result.status == "unsupported" and result.reason == "eligible_full_context_infeasible"
        )
    else:
        assert result.status == "ok" and result.tokens <= 200


def test_candidate_query_term_page_and_deadline_caps_are_explicit():
    source, engine, query = setup()
    canonical = query.canonical.model_copy(update={"candidate_limit": 1})
    limited = query.model_copy(update={"canonical": canonical})
    assert engine.run(limited, policy()).status == "incomplete"
    assert engine.run(query, policy(), cancelled=lambda: True).status == "cancelled"
    expired = query.model_copy(
        update={"canonical": query.canonical.model_copy(update={"deadline": monotonic() - 1})}
    )
    assert engine.run(expired, policy()).status == "timed_out"
    index = engine.index(query)
    with pytest.raises(ResearchFailure, match="expansion_cap"):
        fetch_topic(source, index, query, index.topics[0].id, page=2)
    for text in ("a" * 65, " ".join(f"term{i}" for i in range(129))):
        with pytest.raises(ResearchFailure, match="term_cap"):
            terms(text)


@pytest.mark.parametrize(
    "changes",
    [
        {"top_k": 17},
        {"text": "x" * 2049},
        {"observed_after": "2026-01-01T00:00:00"},
        {"owner_id": "caller-owned"},
    ],
)
def test_untrusted_query_fields_and_unbounded_inputs_rejected(changes):
    _, _, query = setup()
    with pytest.raises(ValidationError):
        ResearchQuery.model_validate({**query.model_dump(), **changes})


def test_hierarchical_arm_uses_at_most_one_extra_page_and_preserves_exact_fetch():
    _, engine, query = setup("topic_hierarchical", query="Operations Recovery")
    result = engine.run(query, policy())
    assert 1 <= result.fetch_pages <= 2 and result.answer == "dry check"
    assert result.citations == ("source-paraphrase",)


def test_semantic_hybrid_require_matching_complete_eligible_universe():
    source, engine, query = setup("hybrid_reranked", query="compiler version")
    index = engine.index(query)
    ids = tuple(e.record_id for e in index.entries)
    frame = CanonicalSemanticRanks(
        origin="fake_vector_contract",
        generation=index.generation,
        query_identity=index.query_identity,
        query_fingerprint=query.canonical.query_fingerprint,
        embedding_identity=query.canonical.embedding_space.identity,
        universe=ids,
        ranking=tuple(reversed(ids)),
    )
    assert engine.run(query, policy(), semantic=frame).status == "unsupported"
    result = engine.run(query, policy(), semantic=frame, allow_fake_vectors_for_contract_test=True)
    assert result.status == "ok" and result.selected_ids[0] == "version-new"
    for updates in (
        {"embedding_identity": digest("different")},
        {"universe": ids[1:]},
        {"ranking": ids[1:]},
        {"query_fingerprint": digest("other query")},
    ):
        invalid = frame.model_copy(update=updates)
        assert (
            engine.run(
                query, policy(), semantic=invalid, allow_fake_vectors_for_contract_test=True
            ).status
            == "unsupported"
        )
    source.transition("revoke", "check")
    assert (
        engine.run(
            query, policy(), semantic=frame, allow_fake_vectors_for_contract_test=True
        ).status
        == "unsupported"
    )
    assert fuse(("exact", "paraphrase"), ("paraphrase", "exact")) == ("exact", "paraphrase")


def test_lease_unavailable_and_cancellation_between_pack_and_consume_fail_closed():
    source, engine, query = setup()
    assert (
        engine.run(
            query,
            policy(),
            hook=lambda stage: (
                source.transition("unavailable", "check") if stage == "packed" else None
            ),
        ).status
        == "unavailable"
    )
    _, engine, query = setup()
    cancelled = Event()
    result = engine.run(
        query,
        policy(),
        cancelled=cancelled.is_set,
        hook=lambda stage: cancelled.set() if stage == "packed" else None,
    )
    assert result.status == "cancelled" and not result.packed_ids


def test_cold_authority_restart_refuses_a_prior_process_cache_and_dependency():
    source, engine, query = setup()
    old = engine.index(query)
    dependency = source.dependency(source._records["check"])
    fresh_source = FixtureAuthority()
    with pytest.raises(ResearchFailure, match="generation_changed"):
        browse(fresh_source, old, query)
    assert not fresh_source.is_current(dependency)


def test_natural_corpus_and_topic_quota_exhaustion_fail_explicitly():
    source, engine, query = setup()
    template = source._records["check"]
    for i in range(101):
        record = template.model_copy(update={"id": f"extra-{i}", "source_id": f"source-extra-{i}"})
        source._records[record.id] = record
    assert engine.run(query, policy()).status == "incomplete"
    source, engine, query = setup()
    for i in range(20):
        record = template.model_copy(
            update={
                "id": f"extra-{i}",
                "source_id": f"source-extra-{i}",
                "topic": (f"Root {i}", f"Leaf {i}"),
            }
        )
        source._records[record.id] = record
    result = engine.run(query, policy())
    assert result.status == "incomplete" and result.reason == "topic_cap"


def test_pack_rejects_incomplete_conflict_and_consumer_rejects_substituted_content():
    from personal_ai.llm.client import ChatMessage
    from personal_ai.memory.research.engine import PackedResearchContext

    _, engine, query = setup(query="storage")
    index = engine.index(query)
    with pytest.raises(ResearchFailure, match="conflict_group_incomplete"):
        engine.pack(query, index, ("conflict-a",), policy())
    _, engine, query = setup()
    index = engine.index(query)
    packed = engine.pack(query, index, ("check",), policy())
    changed = tuple(
        ChatMessage(m.role, m.content.replace("backend-lint", "publish"))
        for m in packed.build.messages
    )
    forged = PackedResearchContext(
        index, query, packed.build.model_copy(update={"messages": changed}), ("check",)
    )
    with pytest.raises(ResearchFailure, match="packed_content_changed"):
        engine.consume(forged)


def test_actual_canonical_retriever_result_adapts_without_changing_fixed():
    from dataclasses import replace
    from hashlib import sha256

    from personal_ai.auth.scope import RequestScope, bind_request_scope, reset_request_scope
    from personal_ai.memory.research.contracts import ResearchScope
    from tests.test_memory_revalidation import environment, retriever

    env = environment()
    scope = RequestScope(owner_id="local", acting_user_id="actor", request_id="semantic-contract")
    token = bind_request_scope(scope)
    try:
        result = retriever(env).retrieve("local", "query", [])
        assert result.trace.complete and result.trace.query.strategy == "fixed"
        _, engine, query = setup()
        index = engine.index(query)
        canonical = result.trace.query.model_copy(
            update={"sensitivity_ceiling": "public", "max_tokens": 1024}
        )
        query = query.model_copy(update={"canonical": canonical, "text": "query"})
        entries = tuple(
            entry.model_copy(
                update={
                    "record_id": f"canonical-{n}",
                    "content_fingerprint": sha256(row.memory.content.encode()).hexdigest(),
                }
            )
            for n, (entry, row) in enumerate(zip(index.entries, result.candidates))
        )
        index = index.model_copy(
            update={"scope": ResearchScope.from_request(scope), "entries": entries}
        )
        mapping = {
            str(row.memory.id): entry.record_id
            for row, entry in zip(result.candidates, entries, strict=True)
        }
        frame = CanonicalSemanticRanks.from_retrieval(
            result, query, index, mapping, fake_vectors=True
        )
        assert set(frame.validated(query, index, allow_fake=True)) == set(mapping.values())
        with pytest.raises(ResearchFailure, match="semantic_universe_mismatch"):
            CanonicalSemanticRanks.from_retrieval(
                replace(result, candidates=result.candidates[:1]),
                query,
                index,
                mapping,
                fake_vectors=True,
            )
        assert retriever(env).retrieve("local", "query", []).selected == result.selected
    finally:
        reset_request_scope(token)
