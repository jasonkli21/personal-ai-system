"""Additive scope/provenance/governance/regrant and capacity contracts."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import RequestScope
from personal_ai.evaluation.control_runtime import ControlRuntime
from personal_ai.memory.consolidation.contracts import (
    BACKFILL_GENERATION,
    GENERATION,
    ConsolidationDenied,
)
from personal_ai.memory.consolidation.governance import ProposalReviewPreview
from personal_ai.memory.consolidation.policy import proposal_current
from personal_ai.memory.consolidation.repository import OfflineProposalRepository
from personal_ai.memory.consolidation.sources import FrozenFixtureSource, load_corpus
from personal_ai.memory.control_contracts import ReviewInput
from personal_ai.memory.control_service import MemoryControlService
from personal_ai.memory.knowledge import ProjectSnapshot

NOW = datetime(2026, 11, 3, 13, tzinfo=UTC)


def runtime(session, *, generation=GENERATION):
    source = FrozenFixtureSource(clock=lambda: NOW, corpus="v2")
    repo = OfflineProposalRepository(source, generation=generation)
    scope = next(s for s in source.scopes if s.session == session)
    return source, repo, scope


def drive(source, repo, scope, through=None):
    source.publish(scope, len(source._streams[scope.key]) if through is None else through)
    # The lease is the durable cursor; no local accumulator can skip a failed page.
    for _ in range(32):
        lease = repo.claim(scope, "adversarial")
        page = source.page(scope, lease.cursor, generation=repo.generation)
        if page is None:
            return
        repo.commit(lease, page)
        if len(page.records) < 4:
            return
    raise AssertionError("bounded driver exhausted")


@pytest.mark.parametrize(
    "session",
    ["nullable-actor", "other-application", "other-actor", "other-owner-project", "other-client"],
)
def test_multiple_legitimate_scopes_remain_isolated(session):
    source, repo, scope = runtime(session)
    drive(source, repo, scope)
    candidate = repo.pending(scope)[0]
    for other in source.scopes:
        if other != scope:
            assert not repo.pending(other)
            assert not repo.validate_cached(other, candidate)
    assert repo.validate_cached(scope, candidate)
    # A different valid owner's deletion never touches this namespace.
    repo.forget(owner="unknown-owner")
    assert repo.pending(scope) == (candidate,)


def test_fresh_source_after_regrant_is_eligible_but_original_is_not():
    source, repo, scope = runtime("fresh-regrant")
    drive(source, repo, scope, 1)
    old = repo.pending(scope)[0]
    source.withdraw(scope, "renewable")
    source.regrant(scope, "renewable")
    assert not repo.pending(scope)
    drive(source, repo, scope, 2)
    fresh = repo.pending(scope)[0]
    assert fresh.fact.outcome == "failed" and fresh.edges[0].epoch == 3
    assert fresh.edges[0].revision == 2
    assert not repo.validate_cached(scope, old)


def test_withdrawing_user_correction_never_resurrects_lower_authority_cache():
    source, repo, scope = runtime("correction-withdrawn")
    drive(source, repo, scope, 1)
    old = repo.pending(scope)[0]
    source.publish(scope, 2)
    assert not repo.validate_cached(scope, old)
    source.withdraw(scope, "correction-withdrawn-2")
    assert not repo.validate_cached(scope, old)
    drive(source, repo, scope, 2)
    assert not repo.pending(scope)


def test_contradictory_user_corrections_stay_unresolved_and_commands_do_not_merge():
    source, repo, scope = runtime("user-conflict")
    drive(source, repo, scope)
    conflict = repo.pending(scope)[0]
    assert conflict.kind == "conflict" and conflict.authority == "unresolved"
    assert len(conflict.edges) == 2 and proposal_current(conflict, source)
    source, repo, scope = runtime("multi-command")
    drive(source, repo, scope)
    assert len(repo.pending(scope)) == 3
    assert len({p.fact.command for p in repo.pending(scope)}) == 3


@pytest.mark.parametrize("mutation", ["fact", "authority", "kind", "duplicate_edges", "scope"])
def test_current_edge_alone_cannot_support_forged_proposition(mutation):
    source, repo, scope = runtime("multi-command")
    drive(source, repo, scope)
    candidate = repo.pending(scope)[0]
    changed = {
        "fact": {
            "fact": candidate.fact.model_copy(
                update={"outcome": "failed" if candidate.fact.outcome == "passed" else "passed"}
            )
        },
        "authority": {"authority": "user_asserted"},
        "kind": {"kind": "conflict"},
        "duplicate_edges": {"edges": (candidate.edges[0], candidate.edges[0])},
        "scope": {"scope": next(s for s in source.scopes if s != scope)},
    }[mutation]
    forged = candidate.model_copy(update=changed)
    assert not proposal_current(forged, source)
    assert not repo.validate_cached(scope, forged)


def test_real_byte_capacity_denial_is_atomic_and_forget_remains_available():
    source, repo, scope = runtime("capacity-pressure")
    source.publish(scope, 65)
    rejected = False
    for _ in range(32):
        lease = repo.claim(scope, "capacity")
        page = source.page(scope, lease.cursor)
        prior = repo._states[scope.key]
        try:
            repo.commit(lease, page)
        except ConsolidationDenied:
            assert repo._states[scope.key] == prior
            rejected = True
            break
    assert rejected and prior.cursor < 65
    receipts = len(prior.receipts)
    repo.forget(owner=scope.owner, project=scope.project)
    assert not repo.pending(scope)
    assert len(repo._states[scope.key].receipts) == receipts
    assert not repo._states[scope.key].proposals


def test_explicit_backfill_has_separate_checkpoint_keys_and_cannot_reuse_old_lease():
    source, first, scope = runtime("multi-command")
    drive(source, first, scope)
    original = first.pending(scope)
    backfill = OfflineProposalRepository(source, generation=BACKFILL_GENERATION)
    lease = backfill.claim(scope, "backfill")
    assert lease.cursor == 0
    with pytest.raises(ConsolidationDenied):
        backfill.commit(lease, source.page(scope, 0))
    backfill.commit(lease, source.page(scope, 0, generation=BACKFILL_GENERATION))
    assert first.pending(scope) == original
    assert {p.key for p in original}.isdisjoint(p.key for p in backfill.pending(scope))


def controls_for(scope, revision="revision-a"):
    controls = ControlRuntime()
    controls.now = NOW
    request = RequestScope(
        owner_id=scope.owner,
        application_id=scope.application,
        workspace_id=scope.workspace,
        acting_user_id=scope.actor,
        request_id="synthetic-review-preview",
    )
    principal = AuthenticatedPrincipal(
        issuer="fixture-issuer",
        subject="actor-a",
        owner_id=scope.owner,
        email=None,
        issued_at=int(NOW.timestamp()),
        authenticated=True,
        authenticated_at=int(NOW.timestamp()),
        audience="fixture-audience",
        authorized_party=scope.client,
    )
    project = ProjectSnapshot(
        project_id=scope.project,
        revision=revision,
        branch="synthetic",
        permission_version="fixture-grant",
    )
    key = (scope.owner, scope.application, scope.workspace, scope.actor)
    controls.authority.projects[(key, scope.project)] = project
    service = MemoryControlService(
        controls.knowledge, controls.repository, request, scope.project, clock=lambda: controls.now
    )
    return controls, request, principal, service


def test_canonical_review_dry_run_requires_current_auth_and_never_writes():
    source, repo, scope = runtime("multi-command")
    drive(source, repo, scope)
    candidate = next(p for p in repo.pending(scope) if p.kind == "procedure")
    controls, request, principal, service = controls_for(scope)
    bridge = ProposalReviewPreview(repo)
    body = ReviewInput(operation_id=uuid4(), expected_version=0, confirm=True, decision="reviewed")
    assert bridge.preview(scope, candidate, service).status == "denied"
    with controls.user(request, principal):
        preview = bridge.preview(scope, candidate, service, review=body)
        assert preview.status == "preview_only"
        assert preview.pending.status == "pending"
        assert preview.review.status == "reviewed"
        assert preview.review.reason == "review_is_not_admission"
        assert preview.edges == candidate.edges
        assert not controls.memories.knowledge_records
        assert not controls.memories.control_proposals and not controls.memories.control_receipts
        assert repo.pending(scope)
        stale = body.model_copy(update={"expected_version": 1})
        assert bridge.preview(scope, candidate, service, review=stale).review.status == "conflict"
        source.withdraw(scope, candidate.edges[0].source_id)
        assert bridge.preview(scope, candidate, service).status == "denied"


@pytest.mark.parametrize(
    "scenario",
    [
        "stale_auth",
        "wrong_client",
        "wrong_project",
        "nullable_actor",
        "review_only_lesson",
        "review_only_conflict",
    ],
)
def test_governance_denials_and_typed_review_only_kinds(scenario):
    session = {"nullable_actor": "nullable-actor", "review_only_conflict": "user-conflict"}.get(
        scenario, "multi-command"
    )
    source, repo, scope = runtime(session)
    drive(source, repo, scope)
    candidate = next((p for p in repo.pending(scope) if p.kind == "lesson"), repo.pending(scope)[0])
    if scenario not in {"review_only_lesson", "review_only_conflict", "nullable_actor"}:
        candidate = next(p for p in repo.pending(scope) if p.kind == "procedure")
    controls, request, principal, service = controls_for(
        scope, "changed" if scenario == "wrong_project" else "revision-a"
    )
    if scenario == "stale_auth":
        controls.now += timedelta(days=1)
    if scenario == "wrong_client":
        principal = replace(principal, authorized_party="another-valid-client")
    with controls.user(request, principal):
        result = ProposalReviewPreview(repo).preview(scope, candidate, service)
    assert result.status == ("preview_only" if scenario.startswith("review_only_") else "denied")
    if scenario.startswith("review_only_"):
        assert result.canonical_mapping == "typed_review_only"
        assert result.pending.content is None and result.candidate == candidate


def test_additive_fixture_preregisters_quality_metrics_and_reserved_scope_cases():
    corpus = load_corpus("v2")
    assert len(corpus["records"]) == 88 and len(corpus["tasks"]) == 14
    assert "false_support" in corpus["preregistration"]["metrics"]
    assert not corpus["preregistration"]["reserved_independence"]


def test_quality_benchmark_is_reproducible_and_separates_scripted_utility():
    from personal_ai.evaluation.consolidation_quality import evaluate

    first, second = evaluate(), evaluate()
    first.pop("elapsed_seconds")
    second.pop("elapsed_seconds")
    assert first == second
    assert first["scores"]["deterministic_pending"] == {
        "correct": 14,
        "tasks": 14,
        "false_support": 0,
        "cross_scope_leakage": 0,
    }
    assert first["scores"]["fixed_first_assertion"]["false_support"] == 7
    assert first["checks"]["ineligible_edge_leakage"] == 0
    assert first["checks"]["entailment_failures"] == 0
    assert first["real_model_utility"] == "unverified"


def test_scripted_consumer_gets_no_expectations_or_live_candidate_objects():
    from personal_ai.evaluation.consolidation_quality import consume, pack, proposal_cards

    source, repo, scope = runtime("multi-command")
    drive(source, repo, scope)
    query = {"command": "make memory-eval", "revision": "revision-a"}
    messages = pack(proposal_cards(repo, scope))
    assert consume(messages, scope.key, query) == {"status": "advice", "outcome": "passed"}
    assert consume(pack([]), scope.key, query) == {"status": "abstain", "outcome": None}
    # Drop the command-bearing serialized card: a hidden candidate cannot rescue it.
    cards = [c for c in proposal_cards(repo, scope) if c["command"] != query["command"]]
    assert consume(pack(cards), scope.key, query)["status"] == "abstain"


@pytest.mark.parametrize("session", ["multi-command", "user-conflict"])
def test_typed_lesson_and_conflict_review_dry_runs_reuse_canonical_cas(session):
    source, repo, scope = runtime(session)
    drive(source, repo, scope)
    candidate = next((p for p in repo.pending(scope) if p.kind == "lesson"), repo.pending(scope)[0])
    controls, request, principal, service = controls_for(scope)
    review = ReviewInput(
        operation_id=uuid4(), expected_version=0, confirm=True, decision="rejected"
    )
    with controls.user(request, principal):
        preview = ProposalReviewPreview(repo).preview(scope, candidate, service, review=review)
        assert preview.status == "preview_only" and preview.canonical_mapping == "typed_review_only"
        assert preview.candidate == candidate and preview.pending.content is None
        assert preview.review.status == "rejected"
        assert not controls.memories.control_proposals and not controls.memories.knowledge_records
        poisoned = review.model_copy(update={"authority": "forged"})
        assert (
            ProposalReviewPreview(repo).preview(scope, candidate, service, review=poisoned).status
            == "denied"
        )


def test_optional_local_pilot_denies_missing_runtime_and_unapproved_cases():
    import asyncio

    from personal_ai.evaluation.consolidation_quality import evaluate_local, local_preflight
    from personal_ai.settings import Settings

    settings = Settings(
        _env_file=None, ai_provider="fake", ai_model="synthetic", inference_profile="offline_fake"
    )
    assert local_preflight(settings) == {
        "status": "blocked",
        "reason": "local_profile_not_configured",
    }
    assert asyncio.run(evaluate_local("multi-command", settings, None))["status"] == "blocked"
    assert asyncio.run(evaluate_local("other-actor", settings, None))["status"] == "blocked"


def test_local_pilot_uses_existing_chat_entry_for_all_arms_with_equal_budgets(monkeypatch):
    import asyncio

    from personal_ai.evaluation import consolidation_quality, real_tasks
    from personal_ai.llm import execution
    from personal_ai.settings import Settings

    settings = Settings(
        _env_file=None,
        ai_provider="fake",
        ai_model="synthetic",
        max_context_tokens=4096,
        max_response_tokens=128,
        summary_trigger_tokens=2048,
        request_timeout_seconds=30,
    )
    calls = []

    async def run_case(actual_settings, pair, case, arm, run_id):
        assert actual_settings is settings
        assert "expected" not in case and "Do not execute anything" in case["prompt"]
        calls.append((arm, pair, actual_settings.max_context_tokens))
        return {"arm": arm, "provider_calls": "fake_unverified"}

    monkeypatch.setattr(
        consolidation_quality,
        "local_preflight",
        lambda _: {"status": "available_for_explicit_pilot"},
    )
    marker = object()
    monkeypatch.setattr(execution, "compose_pair", lambda *args: marker)
    monkeypatch.setattr(real_tasks, "run_case", run_case)
    result = asyncio.run(consolidation_quality.evaluate_local("multi-command", settings, object()))
    assert [c[0] for c in calls] == ["direct", "selected", "eligible"]
    assert all(c[1] is marker and c[2] == 4096 for c in calls)
    assert result["evidence_tier"] == "E2_attempt" and not result["production_promotable"]
