"""Hermetic safety/fault contracts for the unregistered offline component."""

import itertools
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from threading import Barrier, Event, Thread

import pytest
from pydantic import ValidationError

from personal_ai.memory.consolidation import repository as repository_module
from personal_ai.memory.consolidation import sources as sources_module
from personal_ai.memory.consolidation.contracts import (
    GENERATION,
    MAX_CLAIMS,
    ConsolidationDenied,
    ConsolidationScope,
    SourceEnvelope,
    SourcePage,
)
from personal_ai.memory.consolidation.repository import OfflineProposalRepository
from personal_ai.memory.consolidation.sources import CORPUS_SHA256, FrozenFixtureSource, load_corpus


@pytest.fixture
def runtime():
    class Runtime:
        now = datetime(2026, 11, 3, 13, tzinfo=UTC)

        def __init__(self):
            self.source = FrozenFixtureSource(clock=lambda: self.now)
            self.repository = OfflineProposalRepository(self.source)

        def scope(self, session="procedure"):
            return next(s for s in self.source.scopes if s.session == session)

        def publish(self, session="procedure", through=None):
            scope = self.scope(session)
            size = len(self.source._streams[scope.key])
            self.source.publish(scope, size if through is None else through)
            return scope

        def commit(self, scope):
            lease = self.repository.claim(scope, "worker")
            page = self.source.page(scope, lease.cursor)
            return self.repository.commit(lease, page)

    return Runtime()


def test_frozen_preregistration_and_reproducible_comparison():
    # Corpus and arms were frozen before scoring. Reserved cases are author-visible.
    from personal_ai.evaluation.consolidation import evaluate

    assert (
        sources_module.sha256(
            sources_module.files("personal_ai.evaluation")
            .joinpath("fixtures/memory/offline-consolidation-v1.json")
            .read_bytes()
        ).hexdigest()
        == CORPUS_SHA256
    )
    a, b = evaluate(), evaluate()
    a.pop("elapsed_seconds")
    b.pop("elapsed_seconds")
    assert a == b
    assert a["denominators"] == {"development": 7, "reserved_author_visible": 5}
    assert a["scores"]["deterministic_pending"] == a["denominators"]
    assert a["scores"]["eligible_source_oracle"] == a["denominators"]
    assert a["model_utility"] == "unverified"
    assert not a["reserved_independent"] and not a["production_promotable"]
    assert a["resources"]["provider_calls"] == a["resources"]["provider_tokens"] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("owner", "foreign"),
        ("application", "foreign"),
        ("workspace", "foreign"),
        ("workspace", None),
        ("project", "foreign"),
        ("actor", "foreign"),
        ("actor", None),
        ("client", "foreign"),
        ("session", "foreign"),
        ("purpose", "foreign"),
        ("owner", "../secret"),
        ("owner", "secret\nvalue"),
        ("owner", "é"),
        ("owner", "x" * 65),
    ],
)
def test_exact_server_scope_at_claim_read_and_commit(runtime, field, value):
    rt = runtime
    scope = rt.publish()
    lease = rt.repository.claim(scope, "worker")
    page = rt.source.page(scope, 0)
    foreign = scope.model_copy(update={field: value})
    with pytest.raises(ConsolidationDenied, match="^offline_consolidation_denied$"):
        rt.repository.claim(foreign, "worker")
    assert rt.repository.pending(foreign) == ()
    with pytest.raises(ConsolidationDenied):
        rt.repository.commit(lease, page.model_copy(update={"scope": foreign}))
    assert rt.repository.diagnostics()["processed_source_positions"] == 0


@pytest.mark.parametrize(
    "mutation",
    [
        {"issuer": "forged-issuer"},
        {"issuer": None},
        {"revision": 2},
        {"epoch": 2},
        {"classification": "private"},
        {"sequence": True},
        {"sequence": 2},
        {"schema_version": "consolidation-source-v2"},
        {"source_id": "fabricated"},
        {"secret": "private-source-text"},
        {"evidence": "user_correction"},
        {"supersedes": "another-source"},
    ],
)
def test_structurally_coherent_forgery_never_supplies_source_authority(runtime, mutation):
    rt = runtime
    scope = rt.publish()
    lease = rt.repository.claim(scope, "worker")
    page = rt.source.page(scope, 0)
    forged = page.records[0].model_copy(update=mutation)
    candidate = page.model_copy(update={"records": (forged,)})
    with pytest.raises(ConsolidationDenied):
        rt.repository.commit(lease, candidate)
    assert not rt.repository.pending(scope)
    assert not rt.source.authentic(forged, scope)


def test_changed_fact_with_consistent_digest_is_still_a_forgery(runtime):
    rt = runtime
    scope = rt.publish()
    page = rt.source.page(scope, 0)
    record = page.records[0]
    forged = record.model_copy(
        update={"fact": record.fact.model_copy(update={"outcome": "failed"})}
    )
    lease = rt.repository.claim(scope, "worker")
    with pytest.raises(ConsolidationDenied):
        rt.repository.commit(lease, page.model_copy(update={"records": (forged,)}))
    assert rt.repository.diagnostics()["receipts"] == 0


@pytest.mark.parametrize(
    "session,expected",
    [
        ("procedure", ["procedure"]),
        ("lesson", ["lesson"]),
        ("duplicate", ["procedure"]),
        ("conflict", ["conflict"]),
        ("observed", []),
        ("correction", ["lesson"]),
        ("supersession", ["procedure"]),
        ("reserved-correction", ["procedure"]),
    ],
)
def test_typed_pending_policy_never_auto_accepts_or_certifies_task_success(
    runtime, session, expected
):
    rt = runtime
    scope = rt.publish(session)
    rt.commit(scope)
    pending = rt.repository.pending(scope)
    assert sorted(p.kind for p in pending) == expected
    for proposal in pending:
        assert proposal.status == "pending"
        assert proposal.verification == "synthetic_only_not_task_success"
        assert proposal.generation == GENERATION
        assert all(rt.source.resolve(scope, e) is not None for e in proposal.edges)
        assert len(proposal.model_dump_json().encode()) < 2048
    assert not hasattr(rt.repository, "accept")


@pytest.mark.parametrize("session", ["correction", "supersession"])
def test_published_correction_invalidates_cached_suggestion_before_processing(runtime, session):
    rt = runtime
    scope = rt.publish(session, 1)
    rt.commit(scope)
    cached = rt.repository.pending(scope)[0]
    assert rt.repository.validate_cached(scope, cached)
    rt.source.publish(scope, 2)
    assert rt.repository.pending(scope) == ()
    assert not rt.repository.validate_cached(scope, cached)
    rt.commit(scope)
    assert len(rt.repository.pending(scope)) == 1
    assert rt.repository.pending(scope)[0].fact != cached.fact
    assert not rt.repository.validate_cached(scope, cached)


def test_higher_authority_user_correction_wins_over_later_tool_suggestion(runtime):
    rt = runtime
    scope = rt.publish("reserved-correction", 1)
    rt.commit(scope)
    old = rt.repository.pending(scope)[0]
    rt.source.publish(scope, 2)
    rt.commit(scope)
    correction = rt.repository.pending(scope)[0]
    assert correction.authority == "user_asserted"
    rt.source.publish(scope, 3)
    receipt = rt.commit(scope)
    assert receipt.reasons == ("user_correction_wins",)
    assert rt.repository.pending(scope) == (correction,)
    assert not rt.repository.validate_cached(scope, old)


@pytest.mark.parametrize(
    "event", ["withdraw", "expire", "regrant", "project_forget", "owner_forget"]
)
def test_source_lifecycle_suppresses_cache_purges_bodies_and_keeps_receipts(runtime, event):
    rt = runtime
    scope = rt.publish()
    receipt = rt.commit(scope)
    cached = rt.repository.pending(scope)[0]
    source_id = cached.edges[0].source_id
    if event == "withdraw":
        rt.source.withdraw(scope, source_id)
    elif event == "regrant":
        rt.source.withdraw(scope, source_id)
        rt.source.regrant(scope, source_id)
    elif event == "expire":
        rt.now += timedelta(days=1)
    else:
        rt.repository.forget(
            owner=scope.owner, project=scope.project if event == "project_forget" else None
        )
    assert rt.repository.pending(scope) == ()
    assert not rt.repository.validate_cached(scope, cached)
    rt.repository.maintain()
    assert rt.repository.diagnostics()["retained_proposals"] == 0
    assert rt.repository.diagnostics()["receipts"] == 1
    assert rt.repository._states[scope.key].receipts == (receipt,)


def test_final_source_check_after_claim_and_explicit_terminal_skip(runtime):
    rt = runtime
    scope = rt.publish()
    lease = rt.repository.claim(scope, "worker")
    page = rt.source.page(scope, 0)
    rt.source.withdraw(scope, page.records[0].source_id)
    receipt = rt.repository.commit(lease, page)
    assert receipt.reasons == ("source_ineligible",)
    assert receipt.cursor == 1 and not rt.repository.pending(scope)


def test_expiry_at_commit_and_after_observation_are_distinct(runtime):
    rt = runtime
    scope = rt.publish()
    record = rt.source.page(scope, 0).records[0]
    rt.now = record.expires_at - timedelta(seconds=1)
    lease = rt.repository.claim(scope, "worker")
    rt.now = record.expires_at
    assert rt.repository.commit(lease, rt.source.page(scope, 0)).reasons == ("source_ineligible",)


def test_duplicate_page_lost_ack_and_changed_original_payload(runtime):
    rt = runtime
    scope = rt.publish()
    lease = rt.repository.claim(scope, "worker")
    page = rt.source.page(scope, 0)
    with pytest.raises(ConsolidationDenied):
        rt.repository.commit(lease, page, fault="after_commit")
    receipt = rt.repository.observe(scope, page.original_key)
    assert receipt and receipt.cursor == 1
    assert receipt.proposal_count == len(rt.repository.pending(scope))
    assert rt.repository.commit(lease, page) == receipt
    # After revoke, replay is only the content-free original outcome, never text.
    rt.source.withdraw(scope, page.records[0].source_id)
    assert rt.repository.commit(lease, page) == receipt
    forged = page.records[0].model_copy(update={"revision": 2})
    with pytest.raises(ConsolidationDenied):
        rt.repository.commit(lease, page.model_copy(update={"records": (forged,)}))
    with pytest.raises(ConsolidationDenied):
        rt.repository.commit(lease, page, original_key="a" * 64)
    assert rt.repository.diagnostics()["receipts"] == 1
    assert not rt.repository.pending(scope)


def test_crash_before_commit_leaves_entire_transition_unchanged(runtime):
    rt = runtime
    scope = rt.publish()
    lease = rt.repository.claim(scope, "worker")
    page = rt.source.page(scope, 0)
    prior = rt.repository._states[scope.key]
    with pytest.raises(ConsolidationDenied):
        rt.repository.commit(lease, page, fault="before_commit")
    assert rt.repository._states[scope.key] == prior
    assert rt.repository.observe(scope, page.original_key) is None
    receipt = rt.repository.commit(lease, page)
    assert receipt.cursor == 1


def test_expired_lease_takeover_and_forged_worker_fence(runtime):
    rt = runtime
    scope = rt.publish()
    first = rt.repository.claim(scope, "first")
    page = rt.source.page(scope, 0)
    with pytest.raises(ConsolidationDenied):
        rt.repository.claim(scope, "second")
    rt.now = first.expires_at
    second = rt.repository.claim(scope, "second")
    assert second.fence > first.fence
    for bad in (
        first,
        second.model_copy(update={"worker": "forged"}),
        second.model_copy(update={"cursor": 1}),
    ):
        with pytest.raises(ConsolidationDenied):
            rt.repository.commit(bad, page)
    assert rt.repository.commit(second, page).cursor == 1


def test_two_simultaneous_claims_have_one_winner(runtime):
    rt = runtime
    scope = rt.publish()
    barrier = Barrier(2)

    def claim(worker):
        barrier.wait(timeout=2)
        try:
            return rt.repository.claim(scope, worker)
        except ConsolidationDenied:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ("one", "two")))
    assert sum(r is not None for r in results) == 1


def test_separate_worker_facades_share_cas_and_original_key_recovery(runtime):
    rt = runtime
    scope = rt.publish()
    other = OfflineProposalRepository(rt.source)
    first = rt.repository.claim(scope, "first")
    with pytest.raises(ConsolidationDenied):
        other.claim(scope, "second")
    page = rt.source.page(scope, 0)
    rt.now = first.expires_at
    second = other.claim(scope, "second")
    with pytest.raises(ConsolidationDenied):
        rt.repository.commit(first, page)
    with pytest.raises(ConsolidationDenied):
        other.commit(second, page, fault="after_commit")
    assert rt.repository.observe(scope, page.original_key) == other.observe(
        scope, page.original_key
    )
    assert rt.repository.commit(first, page).cursor == 1
    fresh = OfflineProposalRepository(rt.source)
    assert fresh.pending(scope) == rt.repository.pending(scope)
    assert fresh.claim(scope, "third").cursor == 1


@pytest.mark.parametrize("order", list(itertools.permutations(range(3))))
def test_page_order_property_never_skips_source_sequences(runtime, order):
    rt = runtime
    scope = rt.publish("duplicate")
    original = rt.source.page(scope, 0)
    if order == (0, 1, 2):
        page = SourcePage(scope=scope, after=0, records=tuple(original.records[i] for i in order))
        lease = rt.repository.claim(scope, "worker")
        assert rt.repository.commit(lease, page).cursor == 3
    else:
        with pytest.raises(ValidationError):
            SourcePage(scope=scope, after=0, records=tuple(original.records[i] for i in order))
        assert rt.repository.diagnostics()["processed_source_positions"] == 0


def test_page_gap_duplicate_and_generation_mismatch_cannot_advance(runtime):
    rt = runtime
    scope = rt.publish("reserved-procedure")
    lease = rt.repository.claim(scope, "worker")
    first = rt.source.page(scope, 0)
    for page in (
        rt.source.page(scope, 4),
        first.model_copy(update={"after": 1}),
        first.model_copy(update={"generation": "changed"}),
        first.model_copy(update={"records": (first.records[0], first.records[0])}),
    ):
        with pytest.raises(ConsolidationDenied):
            rt.repository.commit(lease, page)
    assert rt.repository.commit(lease, first).cursor == 4
    assert rt.commit(scope).cursor == 5
    assert len(rt.repository.pending(scope)) == 1


@pytest.mark.parametrize("cap", ["MAX_RECEIPTS", "MAX_PROPOSALS", "MAX_BYTES"])
def test_write_quota_denial_is_atomic_and_never_prunes_fences(runtime, monkeypatch, cap):
    rt = runtime
    scope = rt.publish()
    lease = rt.repository.claim(scope, "worker")
    page = rt.source.page(scope, 0)
    monkeypatch.setattr(repository_module, cap, 0)
    prior = rt.repository._states[scope.key]
    with pytest.raises(ConsolidationDenied):
        rt.repository.commit(lease, page)
    assert rt.repository._states[scope.key] == prior
    rt.repository.forget(owner=scope.owner)
    assert not rt.repository.pending(scope)
    with pytest.raises(ConsolidationDenied):
        rt.repository.claim(scope, "later")


def test_claim_budget_is_finite_and_does_not_affect_another_session(runtime):
    rt = runtime
    scope = rt.publish()
    for _ in range(MAX_CLAIMS):
        lease = rt.repository.claim(scope, "worker")
        rt.now = lease.expires_at
    with pytest.raises(ConsolidationDenied):
        rt.repository.claim(scope, "worker")
    other = rt.publish("lesson")
    assert rt.repository.claim(other, "worker").fence == 1


def test_wall_time_deadline_before_assignment_is_atomic(runtime, monkeypatch):
    rt = runtime
    scope = rt.publish()
    lease = rt.repository.claim(scope, "worker")
    page = rt.source.page(scope, 0)
    times = iter((0, 0, 3))
    monkeypatch.setattr(repository_module, "monotonic", lambda: next(times))
    prior = rt.repository._states[scope.key]
    with pytest.raises(ConsolidationDenied):
        rt.repository.commit(lease, page)
    assert rt.repository._states[scope.key] == prior


def test_source_expiry_while_staging_cannot_commit_eligible_output(runtime, monkeypatch):
    rt = runtime
    scope = rt.publish()
    page = rt.source.page(scope, 0)
    rt.now = page.records[0].expires_at - timedelta(seconds=1)
    lease = rt.repository.claim(scope, "worker")
    prior = rt.repository._states[scope.key]
    make_receipt = repository_module.BatchReceipt

    def expire_after_staging(**fields):
        receipt = make_receipt(**fields)
        rt.now = page.records[0].expires_at
        return receipt

    monkeypatch.setattr(repository_module, "BatchReceipt", expire_after_staging)
    with pytest.raises(ConsolidationDenied):
        rt.repository.commit(lease, page)
    assert rt.repository._states[scope.key] == prior
    assert rt.repository.commit(lease, page).reasons == ("source_ineligible",)


def test_issuer_lock_fences_withdrawal_through_commit(runtime):
    rt = runtime
    scope = rt.publish()
    lease = rt.repository.claim(scope, "worker")
    page = rt.source.page(scope, 0)
    attempting = Event()

    def withdraw():
        attempting.set()
        rt.source.withdraw(scope, page.records[0].source_id)

    with rt.source.guard():
        thread = Thread(target=withdraw)
        thread.start()
        assert attempting.wait(timeout=1)
        rt.repository.commit(lease, page)
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert not rt.repository.pending(scope)


def test_stale_state_restore_never_restores_source_or_forget_authority(runtime):
    rt = runtime
    scope = rt.publish()
    rt.commit(scope)
    stale = rt.repository._states[scope.key]
    cached = stale.proposals[0]
    rt.repository.forget(owner=scope.owner, project=scope.project)
    # Adversarial state rollback is not a supported API. The current issuer still
    # rejects restored payloads. Rolling back both issuer and DB requires E2+.
    rt.repository._states[scope.key] = stale
    assert not rt.repository.pending(scope)
    assert not rt.repository.validate_cached(scope, cached)
    rt.repository.maintain()
    assert rt.repository._states[scope.key].proposals == ()


def test_publication_rollback_regrant_and_unknown_payload_are_denied(runtime):
    rt = runtime
    scope = rt.publish("duplicate")
    with pytest.raises(ConsolidationDenied):
        rt.source.publish(scope, 1)
    with pytest.raises(ConsolidationDenied):
        rt.source.publish(scope, True)
    with pytest.raises(ConsolidationDenied):
        rt.source.withdraw(scope, "unknown")
    record = rt.source.page(scope, 0).records[0]
    rt.source.withdraw(scope, record.source_id)
    first_epoch = rt.source._epochs[scope.key, record.source_id]
    rt.source.regrant(scope, record.source_id)
    assert rt.source._epochs[scope.key, record.source_id] > first_epoch
    assert not rt.source.current(record, scope)
    with pytest.raises(ConsolidationDenied):
        OfflineProposalRepository(object())


def test_denials_and_diagnostics_never_log_source_or_private_payload(runtime, caplog, capsys):
    rt = runtime
    scope = rt.publish()
    lease = rt.repository.claim(scope, "worker")
    page = rt.source.page(scope, 0)
    sentinel = "SECRET-private-transcript-hidden-reasoning"
    poisoned = page.records[0].model_copy(update={"fact": {"command": sentinel}})
    with pytest.raises(ConsolidationDenied) as error:
        rt.repository.commit(lease, page.model_copy(update={"records": (poisoned,)}))
    output = json.dumps(rt.repository.diagnostics()) + repr(rt.repository) + repr(rt.source)
    output += str(error.value) + caplog.text + capsys.readouterr().out
    assert sentinel not in output and scope.owner not in output
    assert "make backend-lint" not in output


def test_contract_rejects_incomplete_unbounded_and_opaque_evidence(runtime):
    record = runtime.source._streams[runtime.scope().key][0].model_dump(mode="json")
    for mutation in (
        {"issuer": None},
        {"epoch": 0},
        {"sequence": True},
        {"observed_at": "2026-11-03T12:00:00"},
        {"expires_at": "2027-11-03T12:00:00Z"},
        {"payload": "x" * 17000},
        {"fact": {"command": "arbitrary command"}},
    ):
        with pytest.raises(ValidationError):
            SourceEnvelope.model_validate({**record, **mutation})
    with pytest.raises(ValidationError):
        ConsolidationScope.model_validate({**runtime.scope().model_dump(), "secret": "no"})
    assert len(load_corpus()["records"]) <= 128
    assert len(CORPUS_SHA256) == len(sha256(b"").hexdigest())


def test_known_other_session_cannot_supply_page_or_cached_proposal(runtime):
    rt = runtime
    scope, other = rt.publish(), rt.publish("lesson")
    lease = rt.repository.claim(scope, "worker")
    with pytest.raises(ConsolidationDenied):
        rt.repository.commit(lease, rt.source.page(other, 0))
    rt.commit(other)
    assert not rt.repository.validate_cached(scope, rt.repository.pending(other)[0])


def test_input_fanout_cycles_and_oversized_copies_fail_with_uniform_errors(runtime):
    rt = runtime
    scope = rt.publish("reserved-procedure")
    lease = rt.repository.claim(scope, "worker")
    page = rt.source.page(scope, 0)
    circular = page.model_copy()
    circular.__dict__["records"] = (circular,)
    oversized = page.records[0].model_copy(update={"source_id": "x" * 17000})
    for invalid in (
        circular,
        page.model_copy(update={"records": page.records * 40}),
        page.model_copy(update={"records": page.records + (page.records[0],)}),
        page.model_copy(update={"records": (oversized,)}),
    ):
        with pytest.raises(ConsolidationDenied, match="^offline_consolidation_denied$"):
            rt.repository.commit(lease, invalid)
    assert rt.repository.diagnostics()["processed_source_positions"] == 0


def test_source_epoch_capacity_denies_regrant_and_still_allows_forget(runtime):
    rt = runtime
    scope = rt.publish()
    rt.commit(scope)
    record = rt.source.page(scope, 0).records[0]
    rt.source._epochs[scope.key, record.source_id] = 1023
    with pytest.raises(ConsolidationDenied):
        rt.source.regrant(scope, record.source_id)
    assert not rt.repository.pending(scope)
    rt.repository.forget(owner=scope.owner)
    assert rt.repository.diagnostics()["receipts"] == 1
    assert rt.repository.diagnostics()["retained_proposals"] == 0


def test_not_yet_observed_source_and_clock_expiry_fail_closed(runtime):
    rt = runtime
    scope = rt.publish()
    source = rt.source.page(scope, 0).records[0]
    rt.now = source.observed_at - timedelta(seconds=1)
    assert rt.commit(scope).reasons == ("source_ineligible",)
    assert not rt.repository.pending(scope)


def test_lock_acquisition_has_finite_timeout(runtime):
    rt = runtime
    scope = rt.publish()
    locked, release = Event(), Event()

    def hold():
        with rt.source.guard():
            locked.set()
            release.wait(timeout=4)

    thread = Thread(target=hold)
    thread.start()
    assert locked.wait(timeout=1)
    try:
        with pytest.raises(ConsolidationDenied):
            rt.source.page(scope, 0)
    finally:
        release.set()
        thread.join(timeout=1)
    assert not thread.is_alive()
