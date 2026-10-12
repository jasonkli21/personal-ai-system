"""Read/maintenance/reuse safety across the canonical runtime and stores."""

from contextlib import contextmanager
from datetime import timedelta

import pytest

from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.applications.registry import default_application_registry
from personal_ai.auth.scope import RequestScope, bind_request_scope, reset_request_scope
from personal_ai.context.runtime import EMPTY_CONTEXT_RUNTIME_REGISTRY
from personal_ai.context.tokens import FakeTokenCounter
from personal_ai.evaluation.memory_context import MemoryFixtureAssembler
from personal_ai.evaluation.memory_lifecycle import NOW, apply_fixture, build_fixture, load_fixtures
from personal_ai.memory.dependencies import (
    MemoryPermissionRevalidator,
    dependency_version,
    freshness,
)
from personal_ai.memory.lifecycle.policy import make_event
from personal_ai.memory.services import MemoryRetriever


@contextmanager
def request(owner="local", app="personal_ai", workspace=None):
    scope = RequestScope(
        owner_id=owner, application_id=app, workspace_id=workspace, request_id="p34"
    )
    token = bind_request_scope(scope)
    try:
        yield scope
    finally:
        reset_request_scope(token)


def environment(variant="fixed", name="repeated-explicit-preference"):
    fixture = next(f for f in load_fixtures() if f["name"] == name)
    return build_fixture(fixture, variant)


def retriever(env):
    return MemoryRetriever(
        env["settings"],
        env["memories"],
        env["messages"],
        env["embedder"],
        env["lifecycle"],
        clock=lambda: NOW,
    )


def change(env, record, kind):
    state = env["lifecycle"].get_state(owner_id="local", memory_id=record.id)
    event = make_event(
        owner_id="local",
        memory_id=record.id,
        event_type=kind,
        reason_code="phase34_fixture",
        policy_version="score-v1",
        idempotency_key=f"{kind}:{state.state_version}",
        expected_state_version=state.state_version,
        occurred_at=NOW,
    )
    if kind in ("forgotten", "reactivated"):
        # Exercise canonical projection transitions independently of automatic forgetting,
        # which deliberately protects preferences and memories with active dependents.
        from personal_ai.memory.lifecycle.transition import transition

        env["lifecycle"].states[("local", record.id)] = transition(state, event)
    else:
        assert env["lifecycle"].apply_event(event).status == "applied"


def test_retry_replay_preserves_one_original_and_lossless_values():
    env = environment()
    record = next(iter(env["records"].values()))
    values = (3.141592653589793, 1.0000000000000002, 1e-12)
    # A fresh repository validates but does not rewrite input arrays.
    env["memories"].records.pop(record.id)
    record = record.model_copy(update={"embedding": values})
    saved, created = env["memories"].create(record)
    assert created and saved.embedding == values
    assert env["memories"].create(record) == (saved, False)
    assert env["memories"].create(
        record.model_copy(
            update={
                "created_at": record.created_at + timedelta(seconds=1),
                "embedding": (1.0, 2.0, 3.0),
            }
        )
    ) == (saved, False)
    assert sum(item.id == record.id for item in env["memories"].records.values()) == 1


def test_compact_trace_and_original_rollback_preserve_provenance():
    env = environment("compact")
    result = retriever(env).retrieve("local", "query", [])
    assert len(result.selected) == 1
    assert "exact_redundancy" in dict(result.excluded).values()
    trace = result.trace
    assert trace.query.embedding_space.model_id == "fake-v1"
    assert trace.query.strategy_version == "memory-read-v1"
    assert trace.packing_version == "exact-redundancy-v1"
    assert all(row.origins == ("exact_vector",) for row in trace.candidates)
    assert trace.candidates[0].dependencies or trace.candidates[1].dependencies
    originals = dict(env["memories"].records)
    env["settings"].memory_experiment_variant = "fixed"
    baseline = retriever(env).retrieve("local", "query", [])
    assert len(baseline.selected) == 2
    assert env["memories"].records == originals


@pytest.mark.parametrize("fault", ["delete", "branch", "forget", "source_epoch"])
def test_revocation_between_retrieval_and_injection_and_later_reuse(fault):
    env = environment("consolidated")
    apply_fixture(env)
    record = next(iter(env["records"].values()))
    result = retriever(env).retrieve("local", "query", [])
    assert any(
        item.memory.source_memory_ids for item in result.selected if hasattr(item.memory, "sources")
    )
    dependencies = dict(result.permission_dependencies)
    view = next(item.memory for item in result.selected if hasattr(item.memory, "sources"))
    validator = MemoryPermissionRevalidator(
        env["settings"], env["memories"], env["messages"], env["lifecycle"]
    )
    with request():
        assert all(validator.is_current(dep) for dep in dependencies[view.id])
        if fault == "delete":
            env["memories"].records.pop(record.id)
        elif fault == "branch":
            user = env["messages"]._messages[record.source_message_ids[0]]
            from personal_ai.entities import MessageStatus

            env["messages"]._messages[user.id] = user.model_copy(
                update={"status": MessageStatus.SUPERSEDED}
            )
        elif fault == "forget":
            change(env, record, "forgotten")
        else:
            # Canonical source authority changes after admission (not caller-supplied proof).
            assistant = env["messages"]._messages[record.source_turn_id]
            from personal_ai.contracts.context_references import ContextSourceSnapshot
            from personal_ai.entities.turn_execution import TurnAttribution

            # Time-bound context is categorically ineligible for durable memory reuse.
            attribution = TurnAttribution(
                fact_source="server_observed",
                execution_origin="automatic_managed",
                provider_id="fake",
                model_id="fake",
                recorded_at=NOW,
                effective_context_sensitivity="personal",
                source_snapshots=(
                    ContextSourceSnapshot(
                        provider_id="conversation_history",
                        source_id="fixture",
                        source_version="epoch-2",
                        item_id="fixture",
                        owner_id="local",
                        application_id="personal_ai",
                        content_fingerprint="a" * 64,
                        source_classes=("conversation",),
                        expires_at=NOW - timedelta(seconds=1),
                    ),
                ),
            )
            env["messages"]._messages[assistant.id] = assistant.model_copy(
                update={"attribution": attribution}
            )
        assert not all(validator.is_current(dep) for dep in dependencies[view.id])
    assembled = MemoryFixtureAssembler(
        env["settings"],
        FakeTokenCounter(),
        memories=env["memories"],
        messages=env["messages"],
        lifecycle=env["lifecycle"],
    ).assemble([], env["pending"], retrieval=result)
    assert view.id not in assembled.selected_memory_ids
    assert view.id not in [
        item.memory.id for item in retriever(env).retrieve("local", "query", []).selected
    ]


def test_forget_reactivate_retires_old_binding_and_refreshes_under_new_identity():
    env = environment("consolidated")
    apply_fixture(env)
    original = next(iter(env["records"].values()))
    old_view = next(iter(env["memories"].derived_records.values()))
    old_version = old_view.sources[0].dependency_version
    # Use the same original that the compact view enumerates first.
    original = env["memories"].get(owner_id="local", memory_id=old_view.sources[0].memory_id)
    change(env, original, "forgotten")
    change(env, original, "reactivated")
    state = env["lifecycle"].get_state(owner_id="local", memory_id=original.id)
    assert dependency_version(original, state) != old_version
    result = retriever(env).retrieve("local", "query", [])
    assert old_view.id not in [item.memory.id for item in result.selected]
    env["coordinator"]._enqueue(
        env["completed"].model_copy(update={"id": env["pending"].id}),
        "consolidation",
        old_view.source_memory_ids,
    )
    new_job = list(env["lifecycle"].jobs.values())[-1]
    assert env["worker"].process(new_job.id) == "completed"
    assert len(env["memories"].derived_records) == 2
    assert all(
        env["memories"].get(owner_id="local", memory_id=i) for i in old_view.source_memory_ids
    )


def test_similarity_proposes_bounded_paraphrases_without_merge():
    env = environment()
    second = list(env["records"].values())[1]
    # A new exact user excerpt with compatible embeddings is still a different assertion.
    from personal_ai.memory.contracts import identity, normalize

    user = env["messages"]._messages[second.source_message_ids[0]]
    text = "I like calm cabins for overnight stays."
    user = user.model_copy(update={"content": text})
    env["messages"]._messages[user.id] = user
    from personal_ai.context.contracts import fingerprint

    second = second.model_copy(
        update={
            "content": text,
            "normalized_content": normalize(text),
            "source_fingerprint": fingerprint([user]),
        }
    )
    second = second.model_copy(update={"id": identity("local", second.source_fingerprint, second)})
    env["memories"].records[second.id] = second
    anchor = next(iter(env["records"].values()))
    cluster = env["lifecycle"].discover_related(owner_id="local", memory_id=anchor.id, limit=2)
    assert len(cluster) <= 2
    env["coordinator"]._enqueue(env["completed"], "consolidation", (anchor.id, second.id))
    job = list(env["lifecycle"].jobs.values())[-1]
    calls = len(env["embedder"].calls)
    assert env["worker"].process(job.id) == "completed"
    assert not env["memories"].derived_records
    assert len(env["embedder"].calls) == calls


def test_conflicts_remain_explicit_and_cannot_be_consolidated():
    env = environment("consolidated", "ambiguous-negation")
    apply_fixture(env)
    result = retriever(env).retrieve("local", "query", [])
    assert any(row.unresolved_conflict for row in result.trace.candidates)
    assert not env["memories"].derived_records
    context = MemoryFixtureAssembler(
        env["settings"],
        FakeTokenCounter(),
        memories=env["memories"],
        messages=env["messages"],
        lifecycle=env["lifecycle"],
    ).assemble([], env["pending"], retrieval=result)
    assert "unresolved conflict" in context.messages[0].content


@pytest.mark.parametrize(
    "owner,app,workspace",
    [
        ("other", "personal_ai", None),
        ("local", "other_app", None),
        ("local", "personal_ai", "other"),
    ],
)
def test_hard_scope_before_candidate_ranking(owner, app, workspace):
    env = environment()
    with request(owner, app, workspace):
        result = retriever(env).retrieve(owner, "query", [])
        assert not result.selected
    assert all(freshness(item) == "stable" for item in env["records"].values())


def test_production_composition_installs_shared_memory_dependency_authority(monkeypatch):
    from personal_ai.api.dependencies import get_context_assembler
    from personal_ai.context.repositories import InMemorySummaryRepository

    env = environment()

    class Factory:
        def memory_repository(self):
            return env["memories"]

        def memory_lifecycle_repository(self, memories, messages):
            assert memories is env["memories"] and messages is env["messages"]
            return env["lifecycle"]

    monkeypatch.setattr(
        "personal_ai.api.dependencies.persistence_factory", lambda settings: Factory()
    )
    registry = default_application_registry()
    assembler = get_context_assembler(
        EMPTY_CONTEXT_RUNTIME_REGISTRY,
        env["settings"],
        InMemorySummaryRepository(),
        None,
        None,
        None,
        env["messages"],
        registry,
    )
    assembler.counter = FakeTokenCounter()
    registration = registry.registration("personal_ai")
    with request() as scope:
        application_context = ApplicationContextRequest(
            definition=registration.definition,
            scope=scope,
            context_provider_capabilities=registration.context_providers,
            tool_capabilities=registration.tools,
        )
        result = retriever(env).retrieve(
            "local", "query", [], application_context=application_context
        )
        assert result.selected
        dependencies = dict(result.permission_dependencies)[result.selected[0].memory.id]
        assert all(assembler.permission_revalidator.is_current(dep) for dep in dependencies)
        change(env, result.selected[0].memory, "forgotten")
        assert not all(assembler.permission_revalidator.is_current(dep) for dep in dependencies)


def test_stable_episodic_and_volatile_source_freshness_are_not_universal_decay():
    fixture = {
        "name": "p34-freshness",
        "records": [
            {
                "label": "stable",
                "content": "I prefer quiet cabins for overnight stays.",
                "memory_type": "preference",
                "age_days": 4000,
            },
            {
                "label": "history",
                "content": "I visited a quiet lodge.",
                "memory_type": "episodic_observation",
                "age_days": 1000,
            },
            {
                "label": "volatile",
                "content": "Correction: I now prefer quiet rooms for overnight stays.",
                "memory_type": "explicit_correction",
            },
        ],
    }
    env = build_fixture(fixture, "compact")
    result = retriever(env).retrieve("local", "query", [])
    assert {row.freshness for row in result.trace.candidates} == {"stable", "episodic", "volatile"}
    assert len(result.selected) == 3  # age alone is not an expiry fact


def test_ineligible_high_similarity_cannot_starve_valid_candidate_before_limit():
    env = environment()
    records = list(env["records"].values())
    from personal_ai.entities import MessageStatus

    invalid = records[0]
    user = env["messages"]._messages[invalid.source_message_ids[0]]
    env["messages"]._messages[user.id] = user.model_copy(
        update={"status": MessageStatus.SUPERSEDED}
    )
    env["settings"].memory_retrieval_candidate_limit = 1
    result = retriever(env).retrieve("local", "query", [])
    assert [item.memory.id for item in result.selected] == [records[1].id]
    assert (invalid.id, "branch_mismatch") in result.excluded
    assert not result.trace.complete  # exact cap is conservatively reported partial


def test_incompatible_embedding_space_fails_closed_without_reembedding():
    env = environment()
    for record in env["records"].values():
        env["memories"].records[record.id] = record.model_copy(
            update={"embedding_space_version": "v2"}
        )
    before = {item.id: item.embedding for item in env["memories"].records.values()}
    result = retriever(env).retrieve("local", "query", [])
    assert not result.selected
    assert env["embedder"].calls == []  # fixture records no document coercion/reembed
    assert {item.id: item.embedding for item in env["memories"].records.values()} == before


def test_memory_dependencies_revoke_inherited_assistant_history_and_summaries():
    from personal_ai.applications.contracts import ManualImportReusePolicy
    from personal_ai.context.history import conversation_context_messages, message_context_authority
    from personal_ai.contracts.context_references import ContextSourceSnapshot
    from personal_ai.entities.turn_execution import TurnAttribution

    env = environment()
    result = retriever(env).retrieve("local", "query", [])
    record = result.selected[0].memory
    snapshot = ContextSourceSnapshot(
        provider_id="ai_memory",
        source_id=str(record.id),
        source_version="1",
        item_id=str(record.id),
        owner_id="local",
        application_id="personal_ai",
        content_fingerprint="a" * 64,
        source_classes=("ai_memory",),
        permission_dependencies=dict(result.permission_dependencies)[record.id],
    )
    assistant = env["completed"].model_copy(
        update={
            "attribution": TurnAttribution(
                fact_source="server_observed",
                execution_origin="automatic_managed",
                provider_id="fake",
                model_id="fake",
                recorded_at=NOW,
                effective_context_sensitivity="personal",
                source_snapshots=(snapshot,),
            )
        }
    )
    assert message_context_authority(assistant)[0] == snapshot.permission_dependencies
    validator = MemoryPermissionRevalidator(
        env["settings"], env["memories"], env["messages"], env["lifecycle"]
    )
    with request():
        assert conversation_context_messages(
            (env["pending"], assistant),
            manual_import_reuse=ManualImportReusePolicy(),
            permission_revalidator=validator,
            check_source_permissions=True,
            now=NOW,
        )
        env["memories"].records.pop(record.id)
        assert (
            conversation_context_messages(
                (env["pending"], assistant),
                manual_import_reuse=ManualImportReusePolicy(),
                permission_revalidator=validator,
                check_source_permissions=True,
                now=NOW,
            )
            == ()
        )


def test_legacy_flag_only_memory_proof_is_retired():
    from personal_ai.context.adapters import BuiltInContextPermissionRevalidator
    from personal_ai.contracts.context_references import ContextPermissionDependency

    env = environment()
    assert not BuiltInContextPermissionRevalidator(env["settings"]).is_current(
        ContextPermissionDependency(
            permission_id="ai_memory_read", version="memory-v1", purpose="legacy"
        )
    )


def test_paired_experiment_never_promotes_missing_quality_or_database_resources():
    from personal_ai.evaluation.memory_optimization import evaluate

    report = evaluate()
    assert len(report["rows"]) >= 30
    assert report["promoted_coverage"] == []
    assert report["postgres_metrics"] is None
    assert all(
        row["source_dependency_coverage"] == 1 and row["false_memory"] == 0
        for row in report["rows"]
    )


def test_postgres_adapter_authorizes_before_vector_scoring_and_top_k():
    from personal_ai.persistence.postgres.memory import PostgresMemoryRepository

    env = environment()
    records = list(env["records"].values())
    from contextlib import contextmanager

    class Rows:
        def __init__(self, rows):
            self.rows = rows

        def fetchone(self):
            return self.rows[0]

        def fetchall(self):
            return self.rows

    class Database:
        def __init__(self):
            self.checked = []
            self.scoring_calls = 0

        @contextmanager
        def connection(self):
            yield self

        def execute(self, sql, params):
            if sql.startswith("SELECT count"):
                return Rows([(2,)])
            if "AS distance" not in sql:
                return Rows(
                    [
                        (r.model_dump(mode="json", exclude={"embedding"}), r.embedding)
                        for r in records
                    ]
                )
            self.scoring_calls += 1
            assert self.checked == [r.id for r in records]
            assert params[-1] == [str(records[1].id)]
            assert "ORDER BY distance" not in sql
            return Rows([(str(records[1].id), records[1].embedding, 0.05)])

    database = Database()
    repository = PostgresMemoryRepository(database, object())

    def eligible(record):
        database.checked.append(record.id)
        return record.id == records[1].id

    matches = repository.search(
        owner_id="local",
        embedding=(1, 0, 0),
        model="fake-v1",
        dimensions=3,
        limit=1,
        eligible=eligible,
    )
    assert [r.memory.id for r in matches] == [records[1].id]
    assert database.scoring_calls == 1


def test_actor_binding_is_distinct_from_owner_identity():
    env = environment()
    result = retriever(env).retrieve("local", "query", [])
    dependency = dict(result.permission_dependencies)[result.selected[0].memory.id][0]
    validator = MemoryPermissionRevalidator(
        env["settings"], env["memories"], env["messages"], env["lifecycle"]
    )
    token = bind_request_scope(
        RequestScope(owner_id="local", acting_user_id="delegated-subject", request_id="actor")
    )
    try:
        assert not validator.is_current(dependency)
    finally:
        reset_request_scope(token)


def test_equal_time_contradiction_is_review_only_and_derived_text_cannot_supersede():
    from personal_ai.memory.lifecycle.policy import contradiction_decision
    env = environment("consolidated")
    apply_fixture(env)
    original = next(iter(env["records"].values()))
    correction = original.model_copy(update={"memory_type": "explicit_correction",
        "content": "Correction: I now prefer city hotels for overnight stays.",
        "normalized_content": "correction: i now prefer city hotels for overnight stays."})
    assert contradiction_decision(original, correction) == "review"
    derived = next(iter(env["memories"].derived_records.values()))
    assert contradiction_decision(original, derived) == "none"


def test_existing_derived_set_replays_without_embedding_or_rewriting_receipt_payload():
    env = environment("consolidated")
    calls = []
    original_embed = env["worker"].embedder.embed
    def counted(texts, **kwargs):
        calls.append(texts)
        return original_embed(texts, **kwargs)
    env["worker"].embedder.embed = counted
    apply_fixture(env)
    assert len(calls) == 1
    original = next(iter(env["memories"].derived_records.values()))
    env["coordinator"]._enqueue(env["completed"].model_copy(update={"id": env["pending"].id}),
                                "consolidation", original.source_memory_ids)
    job = list(env["lifecycle"].jobs.values())[-1]
    assert env["worker"].process(job.id) == "completed"
    assert len(calls) == 1
    assert next(iter(env["memories"].derived_records.values())) == original


def test_compact_view_can_fit_the_previous_over_budget_limit_with_complete_support():
    env = environment("consolidated", "derived-over-budget-source-fallback")
    env["settings"].memory_max_context_tokens = 58
    apply_fixture(env)
    result = retriever(env).retrieve("local", "query", [])
    context = MemoryFixtureAssembler(env["settings"], FakeTokenCounter(), memories=env["memories"],
        messages=env["messages"], lifecycle=env["lifecycle"]).assemble([], env["pending"], retrieval=result)
    view = next(iter(env["memories"].derived_records.values()))
    assert view.id in context.selected_memory_ids
    assert len(view.source_memory_ids) == 2
    assert env["memories"].records.keys() == set(view.source_memory_ids)


def test_sensitive_source_without_snapshots_is_ineligible_before_ranking():
    from personal_ai.entities.turn_execution import TurnAttribution
    env = environment("consolidated")
    apply_fixture(env)
    record = next(iter(env["records"].values()))
    assistant = env["messages"]._messages[record.source_turn_id]
    env["messages"]._messages[assistant.id] = assistant.model_copy(update={"attribution": TurnAttribution(
        fact_source="server_observed", execution_origin="automatic_managed", provider_id="fake",
        model_id="fake", recorded_at=NOW, effective_context_sensitivity="sensitive")})
    result = retriever(env).retrieve("local", "query", [])
    assert record.id not in [r.memory.id for r in result.selected]
    assert not any(hasattr(r.memory, "sources") for r in result.selected)
    assert (record.id, "context_sensitive") in result.excluded


def test_lost_lifecycle_projection_does_not_become_initial_active_state():
    env = environment("consolidated")
    apply_fixture(env)
    record = next(iter(env["records"].values()))
    result = retriever(env).retrieve("local", "query", [])
    assert result.selected
    env["lifecycle"].states.pop(("local", record.id))
    # Immutable events still establish that initial state cannot be assumed.
    assert env["lifecycle"].events[("local", record.id)]
    validator = MemoryPermissionRevalidator(env["settings"], env["memories"], env["messages"], env["lifecycle"])
    with request():
        assert not all(validator.is_current(d) for deps in dict(result.permission_dependencies).values() for d in deps)
    assert not retriever(env).retrieve("local", "query", []).selected
