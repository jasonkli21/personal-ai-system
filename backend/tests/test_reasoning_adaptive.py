"""Adaptive selection under the same scoped workflow and fake transport."""

import asyncio
import json
import shutil
from contextlib import aclosing, contextmanager
from dataclasses import replace
from hashlib import sha256
from threading import Event, Thread
from time import time
from uuid import uuid4, uuid5

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from personal_ai.contracts.delegated_tasks import canonical_bytes
from personal_ai.contracts.reasoning_workflow import ReasoningProgress
from personal_ai.evaluation.reasoning_adaptive import runner
from personal_ai.evaluation.reasoning_adaptive.fixture import (
    FIXTURE_BUILD,
    FIXTURE_PROTOCOL,
    shadow_host,
)
from personal_ai.evaluation.reasoning_grounded.fixture import fixture_service
from personal_ai.evaluation.reasoning_orchestrator.fixture import synthetic_service
from personal_ai.llm.execution import LocalFakeCounter
from personal_ai.llm.fake import FakeLLMClient
from personal_ai.llm.workflow_fixture import fixture_attempt
from personal_ai.persistence.postgres.workflows import WorkflowRow
from personal_ai.reasoning import adaptive
from personal_ai.reasoning.adaptive_control import (
    LocalPolicyControl,
    PolicyPointer,
    PromotionEvidence,
    SignedEvidence,
)
from personal_ai.reasoning.adaptive_plan import AdaptivePlan
from personal_ai.reasoning.adaptive_receipts import AdaptiveProgress
from personal_ai.reasoning.orchestration import HARD_LIMIT, Checkpoint, Request, Stop
from personal_ai.retrieval.service import RetrievalService
from personal_ai.storage.errors import PersistenceConflict
from personal_ai.workflow import service as workflows
from personal_ai.workflow.adaptive import AdaptiveHost, finite_fixture_binding
from personal_ai.workflow.reasoning import ENDPOINT_DIGEST, Fixture
from tests.test_reasoning_grounded import BASE, FOCUSED, SUBJECT
from tests.test_reasoning_grounded import request as grounded_request
from tests.test_reasoning_orchestrator import request

GOOD = '{"values":[3,6]}'
PART = '{"values":[3,0]}'
OTHER = '{"values":[0,6]}'


def signed_sample(scope, *, key=None, **changes):
    """Fabricated gate unit-test input, scoped to a disposable signing key."""
    key = key or Ed25519PrivateKey.generate()
    now = int(time())
    evidence = PromotionEvidence(**({
        "scope_digest": scope, "build_digest": FIXTURE_BUILD, "endpoint_digest": ENDPOINT_DIGEST,
        "policy_digest": adaptive.FINITE.identity, "protocol_digest": FIXTURE_PROTOCOL,
        "result_digest": "a" * 64, "oracle_custody_digest": "b" * 64,
        "family": "independent", "effort": "max", "limits": HARD_LIMIT,
        "matched_pairs": 64, "quality_lower_ppm": 5000, "utility_lower_ppm": 2000,
        "fake_bytes_observed": 20_000, "dispatched_generations": 90, "observed_generations": 90,
        "observed_count_calls": 180, "observed_verifier_calls": 90,
        "issued_at": now, "expires_at": now + 300,
    } | changes))
    signature = key.sign(canonical_bytes(evidence.model_dump(mode="json"))).hex()
    return SignedEvidence(evidence=evidence, approval=signature), key.public_key().public_bytes_raw()


def canary(service, directory, **changes):
    directory = directory.resolve()
    directory.chmod(0o700)
    scope = service.scope_digest()
    approval, key = signed_sample(scope, **changes)
    control = LocalPolicyControl(directory)
    control.update(0, PolicyPointer(
        generation=1, mode="local_fixture_canary", policy_digest=adaptive.FINITE.identity,
        build_digest=FIXTURE_BUILD, issued_at=approval.evidence.issued_at,
        expires_at=approval.evidence.expires_at, approval=approval,
    ), reviewer_key=key)
    bindings = frozenset({
        finite_fixture_binding(request("independent").task, service.reasoning_host.fixture_digest),
    })
    service.adaptive_host = AdaptiveHost(control, scope, FIXTURE_BUILD, FIXTURE_PROTOCOL, key, bindings)
    return control


@pytest.fixture
def witness(monkeypatch):
    calls = {"model": [], "count": [], "retrieval": [], "check": []}
    raw_send, raw_count, raw_query, raw_check = (
        FakeLLMClient.stream_events, LocalFakeCounter.count, RetrievalService.query, workflows.run_check,
    )

    async def send(client, messages, **kwargs):
        calls["model"].append((fixture_attempt.get().child_key, tuple(message.content for message in messages)))
        async with aclosing(raw_send(client, messages, **kwargs)) as events:
            async for event in events:
                yield event

    def count(*args, **kwargs):
        calls["count"].append(fixture_attempt.get().child_key)
        return raw_count(*args, **kwargs)

    async def query(service, query, **kwargs):
        calls["retrieval"].append(query.idempotency_key)
        return await raw_query(service, query, **kwargs)

    def check(step, plan, checkpoints):
        calls["check"].append(step.name)
        return raw_check(step, plan, checkpoints)

    monkeypatch.setattr(FakeLLMClient, "stream_events", send)
    monkeypatch.setattr(LocalFakeCounter, "count", count)
    monkeypatch.setattr(RetrievalService, "query", query)
    monkeypatch.setattr(workflows, "run_check", check)
    return calls


@pytest.mark.parametrize(("first", "second", "outcome", "values", "generations"), [
    (GOOD, '{"values":[0,0]}', "complete", ((0, 3), (1, 6)), 1),
    (PART, OTHER, "complete", ((0, 3), (1, 6)), 2),
    ('{"values":[0,0]}', GOOD, "complete", ((0, 3), (1, 6)), 2),
    ("CANARY invalid", GOOD, "complete", ((0, 3), (1, 6)), 2),
    (PART, PART, "partial", ((0, 3),), 2),
    (PART, '{"values":[3,6],"values":[0,0]}', "partial", ((0, 3),), 2),
    ('{"values":[0,1]}', '{"values":[1,0]}', "unavailable", (), 2),
    ('{"values":[0,1]}', '{"values":[0,1]}', "unavailable", (), 2),
    ("CANARY invalid", "also invalid", "unavailable", (), 2),
])
def test_candidate_comparison_uses_only_objectively_supported_slots(
    tmp_path, witness, first, second, outcome, values, generations,
):
    with synthetic_service(Fixture(answer=first, revision=second)) as service:
        canary(service, tmp_path)
        original = request("independent")
        run_id = service.submit(original)
        progress, output = asyncio.run(service.execute(run_id))
        assert isinstance(progress, AdaptiveProgress) and progress.outcome == outcome and output == values
        assert len(witness["model"]) == len(witness["check"]) == generations and not witness["retrieval"]
        assert len(witness["count"]) == sum(item.resources.count_calls for item in progress.attempts)
        inferred = [item for item in progress.attempts if item.operation_binding.child_key]
        assert len({item.operation_binding.child_digest for item in inferred}) == generations
        assert len({item.operation_binding.child_message_id for item in inferred}) == generations
        assert [item.operation_binding.child_key for item in inferred] == [
            uuid5(run_id, name) for name in ("candidate_first", "candidate_alternative")[:generations]
        ]
        if generations == 2:
            assert any('"prior":[]' in message for message in witness["model"][1][1])
            assert all("CANARY" not in message for message in witness["model"][1][1])
        assert service.submit(original) == run_id
        with pytest.raises(PersistenceConflict):
            service.submit(original.model_copy(update={"effort": "low"}))
        assert asyncio.run(service.execute(run_id)) == (progress, ())
        with service.store.locked(service.scope_digest(), run_id) as row:
            assert row.spec is None and "checkpoints" not in row.record
            assert not any(marker in json.dumps(row.record) for marker in (
                "CANARY", "requirements", '"values"', '"approval"', '"scope_digest"',
            ))


@pytest.mark.parametrize("change", [
    {"model_calls": 1}, {"verifier_calls": 1}, {"count_calls": 8},
    {"count_input_bytes": 8192}, {"input_bytes": 1024}, {"output_bytes": 128},
    {"result_bytes": 128}, {"deadline_ms": 8000},
])
def test_canary_cannot_expand_narrowed_reservation(tmp_path, witness, change):
    limits = HARD_LIMIT.model_copy(update=change)
    with synthetic_service(Fixture(answer=GOOD)) as service:
        canary(service, tmp_path, limits=limits)
        try:
            run_id = service.submit(request("independent", limits=limits))
        except Stop:
            assert not witness["model"] and not service.store.rows
        else:
            assert type(service.status(run_id)) is ReasoningProgress
            progress, _ = asyncio.run(service.execute(run_id))
            assert type(progress) is ReasoningProgress


@pytest.mark.parametrize("mismatch", ["low_effort", "scope", "protocol", "endpoint", "build", "reviewer", "fixture", "stale"])
def test_mismatched_canary_slice_uses_baseline(tmp_path, mismatch, monkeypatch):
    with synthetic_service(Fixture(answer=GOOD)) as service:
        changes = {
            "endpoint": {"endpoint_digest": "c" * 64},
            "protocol": {"protocol_digest": "c" * 64},
        }.get(mismatch, {})
        canary(service, tmp_path, **changes)
        host = service.adaptive_host
        if mismatch in {"scope", "build", "reviewer", "fixture"}:
            service.adaptive_host = replace(host, **{
                "scope": {"scope_digest": "c" * 64}, "build": {"build_digest": "c" * 64},
                "fixture": {"finite_fixtures": frozenset()},
                "reviewer": {"reviewer_key": Ed25519PrivateKey.generate().public_key().public_bytes_raw()},
            }[mismatch])
        if mismatch == "stale":
            monkeypatch.setattr("personal_ai.workflow.adaptive.time", lambda: time() + 301)
        run_id = service.submit(request("independent", effort="low" if mismatch == "low_effort" else "max"))
        assert type(service.status(run_id)) is ReasoningProgress


@pytest.mark.parametrize("change", [
    {"holdout": "author_visible_E1"}, {"tier": "E2"}, {"matched_pairs": 63},
    {"quality_lower_ppm": 0}, {"utility_lower_ppm": -1}, {"safety_vetoes": 1},
    {"subgroup_regressions": 1}, {"unknown_fixture_effects": 1}, {"unnecessary_calls": 1},
    {"observed_generations": 89}, {"real_provider_tokens": 0}, {"oracle_custody_digest": None},
])
def test_promotion_evidence_vetoes(change):
    with pytest.raises(ValidationError):
        signed_sample("a" * 64, **change)


def test_unapproved_pointer_cannot_be_published(tmp_path):
    tmp_path.chmod(0o700)
    control = LocalPolicyControl(tmp_path.resolve())
    signed, key = signed_sample("a" * 64)
    evidence = signed.evidence
    pointer = PolicyPointer(
        generation=1, mode="local_fixture_canary", policy_digest=adaptive.FINITE.identity,
        build_digest=FIXTURE_BUILD, issued_at=evidence.issued_at, expires_at=evidence.expires_at,
        approval=signed.model_copy(update={"approval": "0" * 128}),
    )
    with pytest.raises(ValueError, match="unapproved"):
        control.update(0, pointer, reviewer_key=key)
    assert control.rollback()[0] is False


def test_finite_runtime_abstains_without_independent_pre_generation_cohort(tmp_path):
    with synthetic_service(Fixture(answer=GOOD, synthesis=GOOD)) as service:
        service.adaptive_host = shadow_host(
            service, tmp_path.resolve(), adaptive.FINITE, task=request("independent").task,
        )
        original = request("independent")
        run_id = service.submit(original)
        assert type(service.status(run_id)) is ReasoningProgress
        assert service.status(run_id).strategy_version == "decompose-typed.v1"


def test_valid_signature_without_verified_artifact_cannot_publish_canary(tmp_path):
    tmp_path.chmod(0o700)
    control = LocalPolicyControl(tmp_path.resolve())
    signed, key = signed_sample("a" * 64)
    evidence = signed.evidence
    pointer = PolicyPointer(
        generation=1, mode="local_fixture_canary", policy_digest=adaptive.FINITE.identity,
        build_digest=FIXTURE_BUILD, issued_at=evidence.issued_at, expires_at=evidence.expires_at,
        approval=signed,
    )
    with pytest.raises(ValueError, match="blocked_unverified_independent_evidence"):
        control.update(0, pointer, reviewer_key=key)
    with control.admission() as current:
        assert current.mode == "disabled" and current.generation == 0


@pytest.mark.parametrize("profile", ["finite", "grounded"])
def test_shadow_recommends_without_incremental_physical_work(tmp_path, witness, caplog, profile):
    caplog.set_level("INFO", logger="personal_ai.workflow.adaptive")

    @contextmanager
    def host(path):
        if profile == "finite":
            with synthetic_service(Fixture(answer=GOOD, synthesis=GOOD)) as service:
                yield service, request("independent"), adaptive.FINITE
        else:
            with fixture_service(path / "install.json", SUBJECT, [BASE, FOCUSED]) as service:
                yield service, grounded_request(("capacity", "duration")), adaptive.GROUNDED

    observed = []
    for mode in ("baseline", "shadow"):
        path = tmp_path / mode
        path.mkdir(mode=0o700)
        with host(path) as (service, original, policy):
            if mode == "shadow":
                service.adaptive_host = shadow_host(
                    service, path.resolve(), policy, task=original.task if profile == "finite" else None,
                )
            progress, output = asyncio.run(service.execute(service.submit(original)))
            observed.append((
                progress.outcome, tuple((item.slot, item.value) for item in output) if profile == "grounded" else output,
                tuple((a.step, a.resources.count_calls) for a in progress.attempts),
                tuple(len(calls) for calls in witness.values()),
            ))
            for calls in witness.values():
                calls.clear()
    assert observed[0] == observed[1]
    receipts = [line.message for line in caplog.records if line.message.startswith("adaptive_shadow")]
    assert len(receipts) == 1
    assert "CANARY" not in receipts[0] and SUBJECT not in receipts[0] and "synthetic-owner" not in receipts[0]
    assert adaptive.SelectionDecisionV1.model_validate_json(receipts[0].split(" ", 1)[1]).mode == "shadow"


def test_injected_feature_and_unknown_verifier_cannot_grant_permission():
    original = request("independent")
    body = original.model_dump(mode="json")
    with pytest.raises(ValidationError):
        Request.model_validate_json(json.dumps(body | {"source_available": True, "verifier": "arithmetic.v1"}))
    with pytest.raises(ValidationError):
        adaptive.ReasoningFeaturesV1(
            profile="finite_synthetic", family="independent", requirements=2, ambiguity="resolved",
            verifier="user-verified", source="none", freshness="not_applicable", effort="max", alternative_fits=True,
        )


def test_rollback_linearizes_against_admission_preserves_run_and_rejects_stale_write(tmp_path):
    with synthetic_service(Fixture(answer=PART, revision=OTHER)) as service:
        control = canary(service, tmp_path)
        original = request("independent")
        run_id = service.submit(original)
        pinned = service.status(run_id)
        entered, finished = Event(), Event()
        results = []

        def rollback():
            entered.set()
            results.append(control.rollback())
            finished.set()

        with control.admission() as old:
            thread = Thread(target=rollback)
            thread.start()
            assert entered.wait(2) and not finished.wait(0.05)
        thread.join(2)
        assert results[0][0] and results[0][1].generation == 2
        assert control.rollback() == (False, results[0][1])
        with pytest.raises(ValueError, match="generation_changed"):
            control.update(1, old.model_copy(update={"generation": 2}))
        assert service.submit(original) == run_id and service.status(run_id) == pinned
        new_run = service.submit(original.model_copy(update={"original_key": uuid4()}))
        assert type(service.status(new_run)) is ReasoningProgress
        progress, result = asyncio.run(service.execute(run_id))
        assert progress.plan_digest == pinned.plan_digest and progress.adaptive_decision == pinned.adaptive_decision
        assert result == ((0, 3), (1, 6))


def test_corrupt_v2_plan_and_receipt_are_rejected(tmp_path):
    with synthetic_service(Fixture(answer=GOOD)) as service:
        canary(service, tmp_path)
        run_id = service.submit(request("independent"))
        with service.store.locked(service.scope_digest(), run_id) as row:
            body = row.spec
            for changes in (
                {"strategy": "decompose"}, {"ablation": "no_features"}, {"approval": None},
                {"steps": list(reversed(body["steps"]))},
            ):
                with pytest.raises(ValidationError):
                    AdaptivePlan.model_validate_json(canonical_bytes(body | changes))
            progress = row.progress(0)
            forged = progress.model_dump(mode="json")
            forged["adaptive_decision"]["policy_digest"] = "e" * 64
            with pytest.raises(ValidationError):
                AdaptiveProgress.model_validate_json(canonical_bytes(forged))


@pytest.mark.parametrize("target", ["candidate_first", "check_first", "candidate_alternative", "compare"])
@pytest.mark.parametrize("fault", ["cancel", "deadline"])
def test_cancel_and_deadline_at_every_reservation(tmp_path, monkeypatch, witness, target, fault):
    with synthetic_service(Fixture(answer=PART, revision=OTHER)) as service:
        canary(service, tmp_path)
        run_id = service.submit(request("independent"))
        raw_reserve = WorkflowRow.reserve

        def reserve(row, step, *args, **kwargs):
            attempt = raw_reserve(row, step, *args, **kwargs)
            if step == target:
                if fault == "cancel":
                    row.record["cancel_requested"] = True
                else:
                    row.deadline = row.now
            return attempt

        monkeypatch.setattr(WorkflowRow, "reserve", reserve)
        progress, result = asyncio.run(service.execute(run_id))
        assert not result and progress.reason == ("cancelled" if fault == "cancel" else "budget_exhausted")
        assert len(witness["model"]) == {
            "candidate_first": 0, "check_first": 1, "candidate_alternative": 1, "compare": 2,
        }[target]
        assert asyncio.run(service.execute(run_id)) == (progress, ())


def test_unknown_alternative_preserves_original_key_after_lease_loss_and_rollback(tmp_path, monkeypatch):
    sent = []
    raw = FakeLLMClient.stream_events
    with synthetic_service(Fixture(answer=PART, revision=OTHER)) as service:
        control = canary(service, tmp_path)
        original = request("independent")
        run_id = service.submit(original)

        async def send(client, *args, **kwargs):
            sent.append(fixture_attempt.get().child_key)
            if len(sent) == 2:
                raise SystemExit("fixture worker lost after dispatch")
            async with aclosing(raw(client, *args, **kwargs)) as events:
                async for event in events:
                    yield event

        monkeypatch.setattr(FakeLLMClient, "stream_events", send)
        with pytest.raises(SystemExit):
            asyncio.run(service.execute(run_id))
        with service.store.locked(service.scope_digest(), run_id) as row:
            pending = row.pending.copy()
            assert pending["state"] == "dispatched"
            row.record["lease"] = 0
        control.rollback()
        progress, result = asyncio.run(service.execute(run_id))
        assert progress.state == "uncertain" and not result
        assert str(progress.attempts[-1].attempt_id) == pending["attempt_id"]
        assert progress.attempts[-1].operation_binding.child_key == uuid5(run_id, "candidate_alternative")
        assert progress.attempts[-1].resources.physical_attempts is None
        assert service.submit(original) == run_id and len(sent) == 2


@pytest.mark.parametrize("member", ["cases.json", "split.json", "oracle.json", "scoring.py", "manifest.json", "seal.json"])
def test_sealed_member_tamper(tmp_path, member):
    directory = tmp_path / "lane"
    shutil.copytree(runner.FILES, directory)
    path = directory / member
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="changed"):
        runner.load(directory)
    if member != "seal.json":
        seal_path = directory / "seal.json"
        lock = json.loads(seal_path.read_bytes())
        lock["lane"][member] = sha256(path.read_bytes()).hexdigest()
        seal_path.write_text(json.dumps(lock))
        with pytest.raises(ValueError, match="seal_changed"):
            runner.load(directory)


def test_degenerate_verifier_and_no_benefit_controls(monkeypatch):
    def degenerate(step, plan, checkpoints):
        return Checkpoint(step=step.name, verdict="pass", values=checkpoints[step.dependencies[-1]].values)

    monkeypatch.setattr(workflows, "run_check", degenerate)
    _, cases, split, _ = runner.load()
    control_cases = {
        case_id for case_id in cases if split[case_id]["partition"] == "development"
        and split[case_id]["stratum"] == "simple_no_benefit"
    }
    report, rows = asyncio.run(runner.evaluate(case_ids=control_cases))
    assert report["fixture_verdict"] == "SAFETY_VETO" and report["promotion"] == "NO_PROMOTION"
    assert any(not row["safe"] and row["arm"] == "adaptive" for row in rows)


def test_sealed_evaluation():
    report, rows = asyncio.run(runner.evaluate())
    assert report["rows"] == 924 and report["cases"] == 182
    assert report["safety_vetoes"] == 0 and report["promotion"] == "NO_PROMOTION"
    assert report["fixture_verdict"] == "OFFLINE_SIGNAL_ONLY"
    assert any(row["work_after_pass"] for row in rows if row["arm"] == "no_early_exit")
    assert any(row["paired_work_delta"] > 0 and row["paired_exact_delta"] == 0 for row in rows if row["arm"] == "no_features")
    print(json.dumps({"observations": rows}, sort_keys=True))
    print(json.dumps(report, sort_keys=True))


@pytest.mark.parametrize("fault", ["omitted_conflict", "revoked_after_read", "revoked_at_terminal"])
def test_grounded_shadow_keeps_complete_result_and_rights_checks(tmp_path, monkeypatch, fault):
    directory = tmp_path / "control"
    directory.mkdir(mode=0o700)
    live = True
    raw_query, raw_terminal = RetrievalService.query, WorkflowRow.terminal

    async def query(service, request, **kwargs):
        nonlocal live
        result = await raw_query(service, request, **kwargs)
        if fault == "revoked_after_read":
            live = False
        if fault == "omitted_conflict":
            items = result.items[:1]
            assert len(result.items) == 2
            return result.model_copy(update={
                "items": items, "quote_bytes": sum(len(item.quote.encode()) for item in items),
                "token_upper_bound": sum(len(item.model_dump_json().encode()) for item in items),
            })
        return result

    def terminal(row, state, *args, **kwargs):
        nonlocal live
        if state == "succeeded" and fault == "revoked_at_terminal":
            live = False
        return raw_terminal(row, state, *args, **kwargs)

    monkeypatch.setattr(RetrievalService, "query", query)
    monkeypatch.setattr(WorkflowRow, "terminal", terminal)
    sources = [BASE, {**BASE, "facts": {"capacity": 4}}] if fault == "omitted_conflict" else [BASE]
    with fixture_service(tmp_path / "source.json", SUBJECT, sources, fixture_rights=lambda: live) as service:
        service.adaptive_host = shadow_host(service, directory.resolve(), adaptive.GROUNDED)
        run_id = service.submit(grounded_request())
        progress, result = asyncio.run(service.execute(run_id))
        assert not result and asyncio.run(service.execute(run_id)) == (progress, ())
        if fault != "revoked_at_terminal":
            assert [item.step for item in progress.attempts] == ["initial"]
        else:
            assert progress.state == "succeeded"


@pytest.mark.parametrize("invalid", ["duplicate", "symlink", "permissions"])
def test_invalid_local_pointer_never_enables_selection_or_replaces_file(tmp_path, invalid):
    from personal_ai.reasoning.adaptive_control import POINTER

    with synthetic_service(Fixture(answer=GOOD)) as service:
        control = canary(service, tmp_path)
        pointer = tmp_path / POINTER
        before = pointer.read_text()
        if invalid == "duplicate":
            pointer.write_text(before[:-1] + ',"mode":"disabled"}')
        elif invalid == "symlink":
            original = pointer.with_suffix(".saved")
            pointer.rename(original)
            pointer.symlink_to(original)
        else:
            pointer.chmod(0o644)
        run_id = service.submit(request("independent"))
        assert type(service.status(run_id)) is ReasoningProgress
        with pytest.raises((ValueError, OSError)):
            control.rollback()


def test_fixture_execution_inputs_exclude_partition_or_oracle(tmp_path, monkeypatch):
    original = runner.observe
    inputs = []

    async def observe(key, case, arm, directory):
        from uuid import UUID

        assert type(key) is UUID
        assert set(case) == {"task", "fixture", "profile", "fault"}
        inputs.append(arm)
        return await original(key, case, arm, directory)

    monkeypatch.setattr(runner, "observe", observe)
    _, cases, split, _ = runner.load()
    case_id = next(case_id for case_id, case in cases.items() if (
        case["profile"] == "finite" and split[case_id]["partition"] == "development"
    ))
    report, _ = asyncio.run(runner.evaluate(case_ids={case_id}))
    assert report["safety_vetoes"] == 0 and len(inputs) == 6


def test_grounded_shadow_disagreement_does_not_suppress_a_permitted_focus(tmp_path, caplog, witness):
    caplog.set_level("INFO", logger="personal_ai.workflow.adaptive")
    directory = tmp_path / "control"
    directory.mkdir(mode=0o700)
    with fixture_service(tmp_path / "source.json", SUBJECT, [BASE, FOCUSED]) as service:
        service.adaptive_host = shadow_host(service, directory.resolve(), adaptive.GROUNDED)
        request = grounded_request(("capacity", "duration", "quantity"))
        progress, result = asyncio.run(service.execute(service.submit(request)))
    assert [attempt.step for attempt in progress.attempts] == ["initial", "focused", "synthesis", "check"]
    assert tuple(claim.value for claim in result) == (3, 9)
    assert len(witness["retrieval"]) == 2 and len(witness["model"]) == 1
    messages = [line.message for line in caplog.records if line.message.startswith("adaptive_shadow")]
    receipt = adaptive.SelectionDecisionV1.model_validate_json(messages[0].split(" ", 1)[1])
    assert receipt.baseline_action == "focused" and receipt.recommendation == "one_shot"


def test_offline_ablation_has_no_admission_authority_in_the_normal_host(witness):
    from personal_ai.evaluation.reasoning_adaptive.fixture import offline_submit

    with synthetic_service(Fixture(answer=GOOD)) as service:
        with pytest.raises(Stop, match="policy_denied"):
            offline_submit(service, request("independent"), "no_early_exit")
        assert not service.store.rows and not any(witness.values())
