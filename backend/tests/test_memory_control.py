"""MEM-2 authority, CAS, boundedness and content-independent control scoring."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier
from time import monotonic
from uuid import uuid4

import pytest

from personal_ai.evaluation.control_runtime import ControlRuntime
from personal_ai.evaluation.knowledge_runtime import request
from personal_ai.evaluation.memory_control import (
    candidate,
    evaluate,
    load_corpus,
    mutation,
    run_probe,
)
from personal_ai.memory.control_contracts import ControlIntent, ReviewInput, SearchInput
from personal_ai.memory.control_repository import legacy_operation_fingerprint, operation_key
from personal_ai.memory.control_tools import MemoryToolRun, tool_definitions
from personal_ai.memory.lifecycle import MemoryLifecycleEvent
from personal_ai.memory.lifecycle.repositories import event_idempotency_id
from personal_ai.settings import Settings


@pytest.mark.parametrize("case", load_corpus()[0].cases, ids=lambda c: c.id)
def test_versioned_control_corpus(case):
    assert run_probe(case.input) == case.expected


def test_evaluator_uses_precise_write_metrics_and_discloses_public_scenarios():
    result = evaluate()
    assert result["classification"].startswith("author-visible synthetic/offline")
    assert result["safety"] == {
        "unauthorized_reads": 0,
        "unauthorized_active_knowledge_mutations": 0,
        "unauthorized_pending_proposal_mutations": 0,
        "unauthorized_control_receipt_mutations": 0,
        "false_successes": 0,
    }


def test_model_schemas_have_no_authority_or_mutation_fields():
    definitions = tool_definitions()
    assert {d["name"] for d in definitions} == {
        "search_memory",
        "fetch_memory",
        "list_memory_topics",
        "propose_memory",
    }
    forbidden = {
        "owner_id",
        "acting_user_id",
        "application_id",
        "workspace_id",
        "verified",
        "receipt_id",
        "source_epoch",
        "authority",
        "permission",
        "operation_id",
    }
    for definition in definitions:
        assert definition["input_schema"]["additionalProperties"] is False
        assert not forbidden.intersection(definition["input_schema"]["properties"])


def test_review_is_not_admission_and_new_service_shares_pending_and_receipts():
    rt = ControlRuntime()
    with rt.user():
        record = rt.seed()
        result = rt.service.propose(candidate())
        service = rt.for_scope(rt.scope)
        assert service.proposals().proposals[0].id == result.target_id
        body = ReviewInput(**mutation().model_dump(), decision="reviewed")
        assert service.mutate("reviewed", result.target_id, body).status == "reviewed"
        assert service.mutate("reviewed", result.target_id, body).replayed
        assert len(rt.memories.knowledge_records) == 1
        assert service.read(SearchInput()).items[0].id == record.id
        assert (
            service.mutate("revise", record.id, mutation()).status == "unsupported_evidence_source"
        )
        assert (
            rt.lifecycle.get_state(owner_id=rt.scope.owner_id, memory_id=record.id).state_version
            == 0
        )


@pytest.mark.parametrize(
    "change",
    [
        {"acting_user_id": "test-issuer|actor-b"},
        {"acting_user_id": None},
        {"application_id": "shopping"},
        {"workspace_id": "repo-beta"},
    ],
)
def test_other_actor_with_own_grant_cannot_review_or_mutate_guess(change):
    rt = ControlRuntime()
    with rt.user():
        record = rt.seed()
        proposal = rt.service.propose(candidate())
        other = rt.scope.model_copy(update=change)
        rt.authority.projects[
            (
                (other.owner_id, other.application_id, other.workspace_id, other.acting_user_id),
                "repo-alpha",
            )
        ] = record.project
        # Even a verified B principal only owns B data; None has no mutation authority.
        principal = (
            replace(rt.principal, subject="actor-b") if "acting_user_id" in change else rt.principal
        )
        with rt.user(other, principal):
            service = rt.for_scope(other)
            assert service.proposals().proposals == ()
            assert service.read(SearchInput()).items == ()
            for action, target in [
                ("forget", record.id),
                ("revise", record.id),
                ("reviewed", proposal.target_id),
            ]:
                assert service.mutate(action, target, mutation()).status in {
                    "forbidden_or_not_found",
                    "unsupported_evidence_source",
                }
        assert (
            rt.lifecycle.get_state(owner_id=rt.scope.owner_id, memory_id=record.id).state_version
            == 0
        )


def test_racing_forgets_and_reviews_have_one_cas_winner():
    rt = ControlRuntime()
    with rt.user():
        record = rt.seed()
        proposal = rt.service.propose(candidate())
    for action, target in [("forget", record.id), ("reviewed", proposal.target_id)]:
        barrier = Barrier(2)

        def worker(_, action=action, target=target, barrier=barrier):
            with rt.user():
                barrier.wait()
                return rt.service.mutate(action, target, mutation()).status

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, range(2)))
        assert sorted(results) == sorted(
            ["applied" if action == "forget" else "reviewed", "conflict"]
        )
    with rt.user():
        assert len(rt.lifecycle.list_events(owner_id=rt.scope.owner_id, memory_id=record.id)) == 1


def test_raw_lifecycle_cannot_use_verified_user_actor():
    rt = ControlRuntime()
    with rt.user():
        record = rt.seed()
        key = "forged-user-event"
        event = MemoryLifecycleEvent(
            id=event_idempotency_id(key),
            owner_id=rt.scope.owner_id,
            memory_id=record.id,
            event_type="forgotten",
            reason_code="fake",
            policy_version="fake",
            actor="verified_user",
            occurred_at=rt.now,
            idempotency_key=key,
            expected_state_version=0,
        )
        assert rt.lifecycle.apply_event(event).reason == "control_transaction_required"


def test_source_revocation_between_service_check_still_allows_user_forget(monkeypatch):
    rt = ControlRuntime()
    with rt.user():
        record = rt.seed()
        original = rt.repository.execute

        def revoke(*args):
            edge = record.evidence.edges[0]
            rt.memories.revoke_knowledge_source(
                scope=rt.scope,
                resolver_id=edge.resolver_id,
                source_id=edge.source_id,
                expected_epoch=0,
            )
            return original(*args)

        monkeypatch.setattr(rt.repository, "execute", revoke)
        assert rt.service.mutate("forget", record.id, mutation()).status == "applied"
        assert (
            rt.lifecycle.get_state(owner_id=rt.scope.owner_id, memory_id=record.id).state_version
            == 1
        )
        assert len(rt.memories.control_receipts) == 1


def test_expired_operation_never_reexecutes_and_new_intent_cannot_reuse_key():
    rt = ControlRuntime()
    with rt.user():
        record = rt.seed()
        req = mutation()
        assert rt.service.mutate("forget", record.id, req).status == "applied"
        rt.now += timedelta(days=31)
        rt.principal = replace(rt.principal, authenticated_at=int(rt.now.timestamp()))
        with rt.user():
            assert rt.service.mutate("forget", record.id, req).status == "expired"
        assert len(rt.memories.control_receipts) == 1
        assert (
            rt.lifecycle.get_state(owner_id=rt.scope.owner_id, memory_id=record.id).state_version
            == 1
        )


def test_exact_forget_replay_survives_project_revision_drift():
    rt = ControlRuntime()
    with rt.user():
        record = rt.seed()
        req = mutation()
        assert rt.service.mutate("forget", record.id, req).status == "applied"
        receipt_key = operation_key(rt.scope, req.operation_id)
        receipt = rt.memories.control_receipts[receipt_key]
        rt.memories.control_receipts[receipt_key] = receipt.model_copy(
            update={
                "fingerprint": legacy_operation_fingerprint(
                    record.project,
                    ControlIntent(
                        operation_id=req.operation_id,
                        action="forget",
                        target_id=record.id,
                        expected_version=req.expected_version,
                        actor="verified_user",
                    ),
                ),
                "project_id": record.project.project_id,
            }
        )
        key = (rt.scope.owner_id, rt.scope.application_id, rt.scope.workspace_id, rt.scope.acting_user_id)
        rt.authority.projects[(key, "repo-alpha")] = record.project.model_copy(
            update={"revision": "rev-after-commit"}
        )
        assert rt.service.mutate("forget", record.id, req).replayed
        altered = mutation(version=1, operation_id=req.operation_id)
        assert rt.service.mutate("forget", record.id, altered).reason == "operation_id_reused"


def test_authenticated_user_can_forget_expired_or_revoked_history():
    rt = ControlRuntime()
    with rt.user():
        record = rt.seed()
        rt.now += timedelta(days=31)
        principal = replace(rt.principal, authenticated_at=int(rt.now.timestamp()))
        with rt.user(principal=principal):
            assert rt.service.mutate("forget", record.id, mutation()).status == "applied"
            assert not rt.service.read(SearchInput(), memory_id=record.id).items
            assert (
                rt.lifecycle.get_state(owner_id=rt.scope.owner_id, memory_id=record.id).state_version
                == 1
            )


def test_proposal_ttl_erases_content_on_next_write_but_preserves_replay_key():
    rt = ControlRuntime()
    with rt.user():
        key = uuid4()
        result = rt.service.propose(candidate(), operation_id=key)
        rt.now += timedelta(days=2)
        assert not rt.service.proposals().proposals
        assert rt.service.propose(candidate(), operation_id=key).status == "expired"
        rt.service.propose(candidate())
        assert all(p.id != result.target_id for p in rt.memories.control_proposals.values())
        assert len(rt.memories.control_receipts) == 2


def test_idle_proposal_gc_physically_erases_expired_content_and_keeps_key():
    rt = ControlRuntime()
    with rt.user():
        key = uuid4()
        result = rt.service.propose(candidate(), operation_id=key)
        rt.now += timedelta(days=3)
        assert result.target_id in {p.id for p in rt.memories.control_proposals.values()}
        assert rt.repository.purge_expired_proposals(as_of=rt.now, limit=1) == 1
        assert not rt.memories.control_proposals
        assert rt.service.propose(candidate(), operation_id=key).status == "expired"


def test_receipt_capacity_never_prunes_expired_keys():
    rt = ControlRuntime()
    with rt.user():
        record = rt.seed()
        for index in range(256):
            rt.now += timedelta(days=2)
            result = rt.service.propose(candidate())
            assert result.status == "proposed_for_review", index
        assert rt.service.propose(candidate()).status == "limit_exceeded"
        assert len(rt.memories.control_receipts) == 256
        principal = replace(rt.principal, authenticated_at=int(rt.now.timestamp()))
        with rt.user(principal=principal):
            assert rt.service.mutate("forget", record.id, mutation()).status == "applied"
        assert len(rt.memories.control_receipts) == 257


def test_forget_remains_available_after_256_conflict_receipts():
    rt = ControlRuntime()
    with rt.user():
        record = rt.seed()
        for _ in range(256):
            assert rt.service.mutate("forget", record.id, mutation(version=999)).status == "conflict"
        assert len(rt.memories.control_receipts) == 256
        request = mutation()
        assert rt.service.mutate("forget", record.id, request).status == "applied"
        assert rt.service.mutate("forget", record.id, request).replayed
        assert len(rt.memories.control_receipts) == 257


def test_candidate_limit_and_zero_record_negative_control():
    rt = ControlRuntime()
    with rt.user():
        assert rt.service.read(SearchInput()).items == ()
        for index in range(33):
            rt.seed(f"run-{index}")
        result = rt.service.read(SearchInput(query="backend-lint"))
        assert result.status == "found"
        assert len(result.items) == 8
        assert result.truncated


def test_final_release_revalidation_removes_concurrent_revocation(monkeypatch):
    rt = ControlRuntime()
    with rt.user():
        rt.seed()
        original = rt.service._view

        def revoke(row):
            view = original(row)
            rt.authority.revoked.add(row.evidence.edges[0].source_id)
            return view

        monkeypatch.setattr(rt.service, "_view", revoke)
        assert not rt.service.read(SearchInput()).items


def test_tool_deadline_huge_json_disable_and_rebind():
    rt = ControlRuntime()
    with rt.user():
        rt.seed()
        run = MemoryToolRun(rt.service)
        assert run.invoke("propose_memory", " " * 5000).status == "rejected"
        run.deadline = monotonic() - 1
        assert run.invoke("search_memory", {}).status == "limit_exceeded"
        run = MemoryToolRun(rt.service)
        other = rt.scope.model_copy(update={"acting_user_id": None})
        with request(other):
            assert not run.invoke("search_memory", {}).items
        rt.settings.memory_agent_tools_enabled = False
        assert run.invoke("propose_memory", candidate().model_dump()).status == "disabled"


def test_flags_default_off_and_require_selection_management():
    settings = Settings(_env_file=None, ai_provider="gemini", ai_model="synthetic")
    assert not any(
        (
            settings.memory_agent_tools_enabled,
            settings.memory_user_management_enabled,
            settings.memory_user_mutations_enabled,
        )
    )
    for flag in (
        "memory_agent_tools_enabled",
        "memory_user_management_enabled",
        "memory_user_mutations_enabled",
    ):
        with pytest.raises(ValueError):
            Settings(_env_file=None, ai_provider="gemini", ai_model="synthetic", **{flag: True})


def test_lease_exit_failure_after_commit_is_unknown_then_exact_key_reconciles(monkeypatch):
    from contextlib import contextmanager

    rt = ControlRuntime()
    with rt.user():
        record = rt.seed()
        req = mutation()
        original = rt.authority.lease

        @contextmanager
        def fail_release(*args):
            with original(*args):
                yield
            raise OSError("synthetic failed lease release after commit")

        with monkeypatch.context() as patch:
            patch.setattr(rt.authority, "lease", fail_release)
            assert rt.service.mutate("forget", record.id, req).status == "unknown_commit"
        assert rt.service.mutate("forget", record.id, req).replayed
        assert (
            rt.lifecycle.get_state(owner_id=rt.scope.owner_id, memory_id=record.id).state_version
            == 1
        )


def test_fake_fenced_erasure_covers_control_content_and_replay_metadata():
    rt = ControlRuntime()
    with rt.user():
        rt.service.propose(candidate())
        with pytest.raises(ValueError, match="fence_required"):
            rt.repository.erase_owner(rt.scope.owner_id)
        rt.memories.knowledge_fenced_owners.add(rt.scope.owner_id)
        rt.repository.erase_owner(rt.scope.owner_id)
        assert not rt.memories.control_proposals and not rt.memories.control_receipts
        assert rt.service.propose(candidate()).status == "temporarily_unavailable"


def test_tool_read_preserves_revocable_permission_dependency():
    rt = ControlRuntime()
    with rt.user():
        record = rt.seed()
        run = MemoryToolRun(rt.service)
        result = run.invoke("fetch_memory", {"memory_id": str(record.id)})
        dependency = result.items[0].permission_dependencies[0]
        assert rt.knowledge.is_current(dependency)
        assert rt.service.mutate("forget", record.id, mutation()).status == "applied"
        assert not rt.knowledge.is_current(dependency)
