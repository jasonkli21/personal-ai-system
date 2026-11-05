"""Governance safety behavior; public fixtures supply no runtime authority."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from personal_ai.evaluation import memory_governance as campaign
from personal_ai.evaluation.governance_simulator import Fixture, uid
from personal_ai.evaluation.knowledge_runtime import request
from personal_ai.memory.governance.contracts import (
    DeletionPropagationReceipt,
    EffectiveGrantDecision,
    ResourceLimits,
    ShareIntent,
    StoreVerification,
)
from personal_ai.memory.governance.operations import OperatorRequest, operator_plan
from personal_ai.memory.governance.policy import effective
from personal_ai.memory.governance.service import GovernanceService

CASES = json.loads(campaign.FIXTURE.read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_governance_scenario_preserves_expected_scope_and_temporal_outcome(case):
    actual, receipts, _ = campaign.exercise(case)
    assert actual == case["expected"]
    assert receipts  # Setup, denied and unavailable outcomes remain visible.


def test_manifest_has_complete_six_family_grid_and_eight_scope_pairs():
    assert len(CASES) >= 36
    assert len({c["id"] for c in CASES}) == len(CASES)
    assert len({c["family"] for c in CASES}) == 6
    pairs = [c for c in CASES if c["action"] == "scope"]
    assert len(pairs) == 16
    assert len({c["pair"] for c in pairs}) == 8
    for pair in {c["pair"] for c in pairs}:
        assert {c["variant"] for c in pairs if c["pair"] == pair} == {"positive", "negative"}


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "v2"),
        ("expected_revision", True),
        ("expected_revision", "0"),
        ("purpose", "*"),
        ("ceiling", "delegate"),
        ("expires_at", "2026-11-04T00:00:00"),
        ("host", {"verified": True}),
        ("decision_proof", "*"),
    ],
)
def test_untrusted_schema_or_policy_fields_cannot_create_authority(field, value):
    f = Fixture()
    body = f.intent().model_dump(mode="json")
    body[field] = value
    with pytest.raises(ValidationError):
        ShareIntent.model_validate(body)


def test_constructed_or_copied_model_cannot_bypass_service_validation():
    f = Fixture()
    bad = f.intent().model_copy(update={"purpose": "delegate"})
    with pytest.raises(ValidationError):
        f.service.mutate(f.host.manager, bad)
    assert not f.store.load("owner-a").grants


def test_unregistered_copied_scope_and_unapproved_decision_proof_fail_closed():
    f = Fixture()
    intent = f.intent()
    assert f.service.mutate(f.host.manager.model_copy(), intent).outcome == "denied"
    forged = intent.model_copy(update={"decision_proof": "invented-proof"})
    assert f.service.mutate(f.host.manager, forged).outcome == "denied"
    assert not f.store.load("owner-a").receipts


def test_no_host_is_unavailable_even_for_forged_allow_receipt():
    f = Fixture(no_host=True)
    intent = f.intent()
    assert f.service.mutate(f.host.manager, intent).outcome == "unavailable"
    forged = EffectiveGrantDecision(
        allowed=True,
        reason="ok",
        epochs={"owner": 0, "source": 0, "target": 0, "generation": 1},
        grant_fingerprint="0" * 64,
    )
    assert not f.observe(intent, prior=forged).allowed


def test_canonical_source_revoke_invalidates_overlay_and_shared_builder():
    f = Fixture()
    intent, receipt = f.grant()
    assert receipt.outcome == "committed"
    selected = f.observe(intent)
    built = f.pack(intent, selected)
    assert f.consume(intent, selected, built)
    # Change only the existing canonical authority, leaving overlay epochs untouched.
    f.host.canonical_authority.revoked.add(f.host.record.evidence.edges[0].source_id)
    assert not f.observe(intent).allowed
    assert not f.pack(intent, selected).manifest.injected_item_ids
    assert not f.consume(intent, selected, built)
    assert f.revoke(intent).outcome == "committed"


def test_canonical_lifecycle_forget_alone_suppresses_overlay():
    from personal_ai.memory.lifecycle.contracts import MemoryLifecycleEvent
    from personal_ai.memory.lifecycle.repositories import event_idempotency_id

    f = Fixture()
    intent, _ = f.grant()
    with f.host.guard(), request(f.host.canonical_scope):
        outcome = f.host.lifecycle.apply_event(
            MemoryLifecycleEvent(
                id=event_idempotency_id("canonical-only", "travel", "workspace-a"),
                application_id="travel",
                workspace_id="workspace-a",
                scope_version=2,
                owner_id="owner-a",
                memory_id=f.host.record.id,
                event_type="forgotten",
                reason_code="developer_verification",
                policy_version="verified-knowledge-v1",
                actor="developer_test",
                occurred_at=f.host.now,
                idempotency_key="canonical-only",
                expected_state_version=0,
            )
        )
    assert outcome.status == "applied"
    assert f.host.state.owner_active  # No duplicate lifecycle flag needed.
    assert not f.observe(intent).allowed


def test_old_snapshot_cannot_overwrite_surviving_grant_or_original_key_authority():
    f = Fixture()
    intent, _ = f.grant()
    old = f.store.load("owner-a")
    assert f.revoke(intent).outcome == "committed"
    anchor = dict(f.store.surviving)
    f.store.ledgers["owner-a"] = old
    assert not f.observe(intent).allowed
    assert f.revoke(intent).outcome == "unavailable"
    assert f.service.mutate(f.host.manager, intent).outcome == "unavailable"
    assert f.store.surviving == anchor


def test_duplicate_concurrent_first_submissions_commit_once():
    f = Fixture()
    intent = f.intent()
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda _: f.service.mutate(f.host.manager, intent), range(2)))
    assert sorted(r.outcome for r in receipts) == ["committed", "replayed"]
    assert f.store.load("owner-a").revision == 1


def test_expired_grant_can_be_revoked_after_target_and_source_rights_loss():
    f = Fixture()
    intent, _ = f.grant()
    f.host.now += timedelta(days=2)
    f.host.change(source_allowed=False, target_allowed=False)
    assert f.revoke(intent).outcome == "committed"


def test_regrant_requires_new_id_and_new_epoch_even_after_expiry():
    f = Fixture()
    intent, _ = f.grant()
    assert f.revoke(intent).outcome == "committed"
    assert f.service.mutate(f.host.manager, f.intent("reuse")).outcome == "conflict"
    fresh = f.intent("fresh", grant_id=uid("fresh"))
    assert f.service.mutate(f.host.manager, fresh).outcome == "committed"
    assert f.observe(fresh).epochs.generation == 2
    assert not f.observe(intent).allowed
    assert f.service.mutate(f.host.manager, intent).outcome == "replayed"
    assert not f.observe(intent).allowed


def test_replacement_then_revoke_never_reveals_prior_grant():
    f = Fixture()
    old, _ = f.grant()
    fresh = f.intent("fresh", grant_id=uid("fresh"))
    assert f.service.mutate(f.host.manager, fresh).outcome == "committed"
    assert not f.observe(old).allowed
    assert f.revoke(fresh).outcome == "committed"
    assert not f.observe(old).allowed


@pytest.mark.parametrize("limit", ["grants", "source_fences"])
def test_safety_receipts_remain_when_grant_or_fence_quota_exhausted(limit):
    f = Fixture(limits=ResourceLimits(**{limit: 1}))
    intent, _ = f.grant()
    assert (
        f.service.mutate(f.host.manager, f.intent("full", grant_id=uid("full"))).reason
        == "capacity"
    )
    assert f.revoke(intent).outcome == "committed"
    quota = f.service.quota(f.host.manager)
    assert quota.grants == 1 and quota.original_keys == 2 and quota.tombstones == 1
    assert len(f.store.load("owner-a").receipts) == 2


def test_per_store_receipt_rejects_omitted_stores_or_unproved_physical_claim():
    with pytest.raises(ValidationError):
        StoreVerification(
            store="backups", topology="unobserved_external", status="physical_verified"
        )
    with pytest.raises(ValidationError):
        DeletionPropagationReceipt(operation_id=uid("delete"), owner_epoch=1, stores=())


def test_policy_intersects_current_owner_source_and_recipient_even_with_old_receipt():
    f = Fixture()
    intent, _ = f.grant()
    record = f.store.load("owner-a").grants[0]
    for changes in (
        {"owner_epoch": 1},
        {"source_epoch": 1},
        {"target_epoch": 1},
        {"owner_active": False},
        {"reconciled": False},
        {"source_allowed": False},
        {"target_allowed": False},
        {"classification": "unknown"},
        {"verification": "unverified"},
        {"origin": "import"},
    ):
        assert not effective(record, replace(f.host.state, **changes), f.host.now).allowed
    assert f.observe(intent).allowed


def test_plans_are_pure_and_forged_executable_plan_is_rejected(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("plan attempted side effect")

    import socket
    import subprocess

    f = Fixture()
    intent, _ = f.grant()
    before = f.snapshot()
    monkeypatch.setattr(Path, "write_text", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(f.store, "save", forbidden)
    for operation in ("canary", "rollback"):
        plan = operator_plan(OperatorRequest(operation=operation, evidence_digest="0" * 64))
        assert not plan["executable"]
    assert f.snapshot() == before
    with pytest.raises(ValidationError):
        OperatorRequest(operation="canary", evidence_digest="0" * 64, executable=True)
    assert f.observe(intent).allowed


def test_complete_report_retains_failed_attempts_and_rejects_tamper(monkeypatch):
    original = campaign.exercise

    def fault(case):
        if case["id"] == CASES[0]["id"]:
            raise OSError("synthetic_failure")
        return original(case)

    monkeypatch.setattr(campaign, "exercise", fault)
    report = campaign.evaluate()
    assert report["case_count"] == len(CASES)
    assert report["rows"][0]["outcome"] == "failed"
    assert report["matched"] == len(CASES) - 1
    report["rows"].pop()
    with pytest.raises(ValueError, match="report_tamper"):
        campaign.verify(report)


def test_semantic_replay_is_complete_and_source_drift_denies():
    report = campaign.evaluate()
    assert campaign.verify(report) == report["semantic_sha256"]
    assert campaign.verify(json.loads(json.dumps(report))) == report["semantic_sha256"]
    report["source_hashes"]["memory/governance/policy.py"] = "0" * 64
    with pytest.raises(ValueError, match="source_drift"):
        campaign.verify(report)


def test_default_service_has_no_issuer_dispatcher_or_runtime_registration():
    assert GovernanceService.__init__.__kwdefaults__["limits"] is None
    root = Path(__file__).parents[1] / "src" / "personal_ai"
    # Registration cannot occur through a new route, settings switch or application import.
    for path in [root / "settings.py", root / "main.py", *(root / "api").rglob("*.py")]:
        assert "memory.governance" not in path.read_text()


def test_two_owners_with_live_records_share_store_without_cross_tenant_grants():
    first, second = Fixture(), Fixture(owner="owner-b")
    second.store = first.store
    second.host.store = first.store
    second.service.repository = first.store
    left, _ = first.grant()
    right, receipt = second.grant()
    assert receipt.outcome == "committed"
    assert first.observe(left).allowed and second.observe(right).allowed
    assert not first.service.observe(second.host.consumer, left.grant_id).allowed
    assert not second.service.observe(first.host.consumer, right.grant_id).allowed
    assert first.revoke(left).outcome == "committed"
    assert second.observe(right).allowed


def test_scope_pairs_bind_eight_distinct_canonical_source_observations():
    sources = []
    for case in CASES:
        if case.get("variant") == "positive":
            _, _, fixture = campaign.exercise(case)
            sources.append(fixture.host.source.version)
    assert len(set(sources)) == 8


def test_source_epoch_change_during_token_count_cannot_escape_shared_packer():
    from personal_ai.context.contracts import ContextError
    from personal_ai.context.tokens import FakeTokenCounter

    f = Fixture()
    intent, _ = f.grant()
    selected = f.observe(intent)

    class ChangeDuringCount(FakeTokenCounter):
        changed = False

        def count(self, messages):
            if not self.changed and any(
                f.host.record.proposal.claim in m.content for m in messages
            ):
                self.changed = True
                f.host.change(source_epoch=1)
            return super().count(messages)

    counter = ChangeDuringCount()
    with pytest.raises(ContextError):
        f.pack(intent, selected, counter=counter)
    assert counter.changed
    assert not f.observe(intent).allowed


def test_fabricated_source_version_cannot_replace_canonical_identity():
    f = Fixture()
    forged_source = f.host.source.model_copy(update={"version": "invented-version"})
    f.host.change(source=forged_source, source_epoch=1)
    intent = f.intent(source=forged_source)
    assert f.service.mutate(f.host.manager, intent).outcome == "denied"


def test_deletion_inventory_models_dependency_paths_and_rejects_restore_cycles():
    from personal_ai.memory.governance.operations import retention_inventory

    receipt = retention_inventory(uid("erase"), 1, suppressed=True)
    by_store = {s.store: s for s in receipt.stores}
    assert by_store["source_edges"].depends_on == ("canonical",)
    assert by_store["indexes"].depends_on == ("memories",)
    assert "memories" in by_store["external_copies"].depends_on
    body = receipt.model_dump()
    body["stores"][0]["depends_on"] = ("caches",)
    with pytest.raises(ValidationError, match="cyclic_deletion_dependencies"):
        DeletionPropagationReceipt.model_validate(body)
