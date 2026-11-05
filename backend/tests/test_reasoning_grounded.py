"""Grounded policy, exact wire evidence and canonical recovery boundaries."""

import asyncio
import json
import shutil
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from uuid import uuid4, uuid5

import pytest
from pydantic import ValidationError

from personal_ai.auth.scope import bind_request_scope, reset_request_scope
from personal_ai.evaluation.reasoning_grounded import runner
from personal_ai.evaluation.reasoning_grounded.fixture import CEILINGS, fixture_service
from personal_ai.llm.fake import FakeLLMClient
from personal_ai.persistence.postgres.workflows import WorkflowRow
from personal_ai.reasoning import grounded
from personal_ai.reasoning.orchestration import Stop
from personal_ai.retrieval.service import RetrievalService
from personal_ai.storage.errors import PersistenceConflict
from personal_ai.usage.trace import Trace
from personal_ai.workflow import service as workflows

SUBJECT = "record1"
BASE = {"tags": ["overview"], "facts": {"capacity": 3}, "poison": True}
FOCUSED = {"tags": ["duration"], "facts": {"duration": 9}}


def request(requirements=("capacity",), **changes):
    return grounded.Request(
        schema_version="reasoning-grounded-request-v1", original_key=uuid4(),
        task=grounded.Task(subject=SUBJECT, requirements=requirements),
        **({"limits": grounded.HARD_LIMIT, "effort": "max"} | changes),
    )


def steps(progress):
    return tuple(attempt.step for attempt in progress.attempts)


def execute(service, req=None):
    run = service.submit(req or request())
    return asyncio.run(service.execute(run))


@pytest.mark.parametrize(("sources", "fields", "expected", "expected_steps", "gaps"), [
    ([BASE], ("capacity",), (3,), ("initial", "synthesis", "check"), (None,)),
    ([BASE, FOCUSED], ("capacity", "duration"), (3, 9), ("initial", "focused", "synthesis", "check"), (None, None)),
    ([BASE], ("capacity", "duration"), (3,), ("initial", "focused", "synthesis", "check"), (None, "missing_evidence")),
    ([BASE, {**BASE, "facts": {"capacity": 4}}], ("capacity",), (), ("initial",), ("conflict",)),
    ([{**BASE, "stale": True}, FOCUSED], ("capacity",), (), ("initial", "focused"), ("stale_or_expired",)),
    ([{**BASE, "expired": True}, FOCUSED], ("capacity",), (), ("initial", "focused"), ("missing_evidence",)),
])
def test_workflow_completion_partial_conflict_and_freshness(
    tmp_path, sources, fields, expected, expected_steps, gaps,
):
    with fixture_service(tmp_path / "source.json", SUBJECT, sources) as service:
        progress, claims = execute(service, request(fields))
        assert tuple(claim.value for claim in claims) == expected
        assert steps(progress) == expected_steps
        assert progress.verification.gaps == gaps
        assert progress.gap == (progress.cursor > 8)
        assert service.status(progress.run_id, cursor=progress.cursor).events == ()
        with service.store.locked(service.scope_digest(), progress.run_id) as row:
            assert row.spec is None
            for marker in ("CANARY", "FACT ", '"quote"', '"claims": [', '"subject"', '"rights_reference"'):
                assert marker not in json.dumps(row.record)
        assert asyncio.run(service.execute(progress.run_id)) == (progress, ())
        for attempt in progress.attempts:
            assert attempt.operation_binding.source_digest == progress.source_digest
            assert attempt.operation_binding.child_key == uuid5(progress.run_id, attempt.step)
        if "focused" in steps(progress):
            focused = next(a for a in progress.attempts if a.step == "focused")
            assert focused.operation_binding.focused_slot is not None
            assert focused.operation_binding.focused_gap in {"missing_evidence", "stale_or_expired"}
        if claims:
            evidence = {item.citation_id: item for attempt in progress.attempts for item in attempt.evidence}
            assert all(claim.citation_id in evidence for claim in claims)
            assert progress.attempts[-2].resources.input_bytes > 0
            assert progress.attempts[-2].resources.output_bytes > 0


@pytest.mark.parametrize("changes", [
    {"source_mode": "external"}, {"source_ids": ["grant"]}, {"tool": "shell.v1"},
    {"steps": ["loop"]}, {"source_policy": "grounded-evidence-policy-v2"},
    {"task": {"subject": "https://example.com", "requirements": ["capacity"]}},
    {"task": {"subject": SUBJECT, "requirements": ["quantity", "quantity"]}},
    {"limits": {"retrieval_calls": 3}}, {"limits": {"concurrency": True}},
    {"limits": {"deadline_ms": 30001}}, {"limits": {"quote_bytes": 4097}},
    {"limits": {"provider_cost_usd": "0.01"}},
])
def test_schema_is_closed(changes):
    with pytest.raises(ValidationError):
        grounded.Request.model_validate_json(json.dumps(request().model_dump(mode="json") | changes))


@pytest.mark.parametrize("ceiling", ("user", "application", "workspace", "operator", "endpoint"))
def test_missing_budget_denies_each_authority_dimension(tmp_path, ceiling):
    caps = CEILINGS.model_copy(update={ceiling: grounded.Ceiling()})
    with fixture_service(
        tmp_path / "source.json", SUBJECT, [BASE], current_ceilings=lambda: caps,
    ) as service, pytest.raises(Stop, match="budget_exhausted"):
        service.submit(request())
    assert not service.store.rows


@pytest.mark.parametrize("boundary", ["disabled", "source_grant", "model_grant", "tool", "endpoint", "kill", "scope"])
def test_denied_before_work_or_context(tmp_path, boundary):
    path = tmp_path / "source.json"
    with fixture_service(
        path, SUBJECT, [BASE], enabled=boundary != "disabled", authorized=boundary != "source_grant",
        context_allowed=boundary != "model_grant",
    ) as service:
        if boundary == "tool":
            service.application_registry = lambda: None
        if boundary == "endpoint":
            service.retrieval.settings.inference_cost_mode = "strict_free"
        if boundary == "kill":
            service.retrieval.settings.external_providers_kill_switch_enabled = True
        token = None
        if boundary == "scope":
            token = bind_request_scope(service.retrieval.scope.model_copy(update={"workspace_id": "outside"}))
        try:
            with pytest.raises((workflows.WorkflowDenied, Stop)):
                service.submit(request())
            assert not service.store.rows
        finally:
            if token is not None:
                reset_request_scope(token)


def test_request_replay_conflict_and_restored_old_snapshot(tmp_path):
    path = tmp_path / "source.json"
    with fixture_service(path, SUBJECT, [BASE]) as service:
        req = request()
        run_id = service.submit(req)
        assert service.submit(req) == run_id
        with pytest.raises(PersistenceConflict):
            service.submit(req.model_copy(update={"effort": "low"}))
        scope = service.scope_digest()
        previous = deepcopy(service.store.rows[(scope, run_id)])
        assert asyncio.run(service.execute(run_id))[1]
        service.store.rows[(scope, run_id)] = previous
        current = json.loads(path.read_bytes())
        current["documents"][0]["rights_epoch"] = "epoch-v2"
        path.write_text(json.dumps(current))
        progress, result = asyncio.run(service.execute(run_id))
        assert progress.reason == "source_changed" and not result and not progress.attempts
        assert service.submit(req) == run_id


def test_low_effort_and_tight_budget_avoid_optional_dispatch(tmp_path):
    path = tmp_path / "source.json"
    with fixture_service(path, SUBJECT, [BASE, FOCUSED]) as service:
        one_query = grounded.HARD_LIMIT.model_copy(update={"retrieval_calls": 1, "evidence_items": 1})
        for req in (request(("capacity", "duration"), effort="low"),
                    request(("capacity", "duration"), limits=one_query)):
            progress, claims = execute(service, req)
            assert [claim.value for claim in claims] == [3]
            assert progress.outcome == "partial" and "focused" not in steps(progress)


def test_saturated_query_cannot_hide_a_conflict(tmp_path):
    with fixture_service(
        tmp_path / "source.json", SUBJECT, [BASE, {**BASE, "facts": {"capacity": 4}}],
    ) as service:
        limits = grounded.HARD_LIMIT.model_copy(update={"evidence_items": 1})
        progress, claims = execute(service, request(limits=limits))
        assert not claims and steps(progress) == ("initial",)
        assert progress.verification.gaps == ("verification_inconclusive",)


@pytest.mark.parametrize("fault", ["fingerprint", "span", "revision", "authority", "epoch", "title", "duplicate"])
def test_forged_retrieval_item_is_rejected_before_packing(tmp_path, monkeypatch, fault):
    query = RetrievalService.query

    async def spoof(service, *args, **kwargs):
        from personal_ai.retrieval.contracts import item_from_quote

        result = await query(service, *args, **kwargs)
        item = result.items[0]
        if fault == "duplicate":
            items = (item, item)
        elif fault == "fingerprint":
            items = (item.model_copy(update={"content_fingerprint": "a" * 64}),)
        else:
            fields = item.model_dump(exclude={
                "source_revision", "content_fingerprint", "passage_id", "citation_id", "end",
            })
            fields["revision"] = item.source_revision
            key, value = {
                "span": ("start", 1), "revision": ("revision", "other"),
                "authority": ("rights_authority_id", "local:" + "b" * 64),
                "epoch": ("rights_epoch", "other"), "title": ("title", "forged"),
            }[fault]
            fields[key] = value
            items = (item_from_quote(**fields),)
        return result.model_copy(update={
            "items": items, "quote_bytes": sum(len(i.quote.encode()) for i in items),
            "token_upper_bound": sum(len(i.model_dump_json().encode()) for i in items),
        })

    monkeypatch.setattr(RetrievalService, "query", spoof)
    with fixture_service(tmp_path / "source.json", SUBJECT, [BASE]) as service:
        progress, claims = execute(service)
        assert not claims and steps(progress) == ("initial",)


@pytest.mark.parametrize("fault", [
    "omitted_conflict", "forged_complete", "forged_reasons", "clipped_budget",
    "reordered", "wrong_query",
])
def test_grounded_replay_rejects_incomplete_or_forged_result_envelope(tmp_path, monkeypatch, fault):
    raw_query = RetrievalService.query
    calls = []

    async def alter(service, query, **kwargs):
        calls.append(query.query)
        result = await raw_query(service, query, **kwargs)
        items = result.items
        changes = {}
        if fault in {"omitted_conflict", "forged_complete", "forged_reasons"}:
            items = items[:1]
        if fault == "forged_complete":
            changes["state"] = "complete"
            changes["reasons"] = ()
        elif fault == "forged_reasons":
            changes["state"] = "partial"
            changes["reasons"] = ("budget",)
        elif fault == "clipped_budget":
            changes["state"] = "complete"
            changes["reasons"] = ()
        elif fault == "reordered":
            items = tuple(reversed(items))
        elif fault == "wrong_query":
            other_query = query.model_copy(update={"query": f"{SUBJECT}_duration"})
            other = await raw_query(service, other_query, **kwargs)
            items = other.items
            changes["state"] = other.state
            changes["reasons"] = other.reasons
        changes.update(
            items=items,
            quote_bytes=sum(len(item.quote.encode()) for item in items),
            token_upper_bound=sum(len(item.model_dump_json().encode()) for item in items),
        )
        return result.model_copy(update=changes)

    monkeypatch.setattr(RetrievalService, "query", alter)
    sources = [BASE, {**BASE, "facts": {"capacity": 4}}]
    fields = ("capacity",)
    if fault in {"reordered", "wrong_query"}:
        sources = [BASE, {"tags": ["overview"], "facts": {"duration": 9}}]
        fields = ("capacity", "duration") if fault == "reordered" else ("capacity",)
    elif fault == "clipped_budget":
        sources = [{"tags": ["overview"], "facts": {"capacity": "x" * 1500}}]
    with fixture_service(tmp_path / "source.json", SUBJECT, sources) as service:
        progress, claims = execute(service, request(fields))
        assert not claims
        assert progress.reason == "internal_failure"
        assert calls == [f"{SUBJECT}_overview"]
        assert steps(progress) == ("initial",)


@pytest.mark.parametrize("fault", ["wrong_value", "unknown_id", "duplicate", "freeform", "other_slot"])
def test_candidates_cannot_create_authority(tmp_path, monkeypatch, fault):
    draft = grounded.draft_from_messages

    def replace(messages):
        a, = grounded.Candidate.model_validate_json(draft(messages)).claims
        if fault == "freeform":
            return '{"claims":[],"certain":true,"answer":"uncheckable"}'
        altered = a.model_copy(update={
            "wrong_value": {"value": 42}, "unknown_id": {"citation_id": "f" * 64},
            "duplicate": {}, "other_slot": {"slot": 2},
        }[fault])
        return grounded.Candidate(claims=(altered, a) if fault == "duplicate" else (altered,)).model_dump_json()

    monkeypatch.setattr(grounded, "draft_from_messages", replace)
    with fixture_service(tmp_path / "source.json", SUBJECT, [BASE]) as service:
        progress, claims = execute(service)
        assert not claims and progress.outcome == "unavailable"
        assert progress.verification.gaps == (
            "verification_inconclusive" if fault == "freeform" else "citation_unsupported",
        )


@pytest.mark.parametrize("boundary", ["queued", "reserved", "packing", "before_send", "after_send", "checking", "terminal"])
def test_revocation_never_returns_live_evidence(tmp_path, monkeypatch, boundary):
    path = tmp_path / "source.json"
    live = True
    calls = 0
    stream = FakeLLMClient.stream_events
    reserve = WorkflowRow.reserve
    terminal = WorkflowRow.terminal
    verify = grounded.verify
    dispatch = WorkflowRow.dispatch
    provider_fetch = workflows.grounded.PinnedExcerpts.fetch

    def revoke():
        nonlocal live
        live = False

    def reserve_step(self, step, *args, **kwargs):
        if step == "synthesis" and boundary == "reserved":
            revoke()
        return reserve(self, step, *args, **kwargs)

    def terminal_step(self, state, *args, **kwargs):
        if state == "succeeded" and boundary == "terminal":
            revoke()
        return terminal(self, state, *args, **kwargs)

    async def stream_step(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        async for event in stream(self, *args, **kwargs):
            yield event
            if boundary == "after_send":
                revoke()

    def dispatch_step(row, attempt_id, binding):
        dispatch(row, attempt_id, binding)
        if boundary == "before_send" and binding["tool_id"] == "reasoning.grounded.inference.v1":
            revoke()

    def fetch_step(*args, **kwargs):
        if boundary == "packing":
            revoke()
        return provider_fetch(*args, **kwargs)

    def verify_step(*args, **kwargs):
        result = verify(*args, **kwargs)
        if boundary == "checking":
            revoke()
        return result

    monkeypatch.setattr(WorkflowRow, "reserve", reserve_step)
    monkeypatch.setattr(WorkflowRow, "terminal", terminal_step)
    monkeypatch.setattr(FakeLLMClient, "stream_events", stream_step)
    monkeypatch.setattr(WorkflowRow, "dispatch", dispatch_step)
    monkeypatch.setattr(workflows.grounded.PinnedExcerpts, "fetch", fetch_step)
    monkeypatch.setattr(grounded, "verify", verify_step)
    with fixture_service(path, SUBJECT, [BASE], fixture_rights=lambda: live) as service:
        run_id = service.submit(request())
        if boundary == "queued":
            revoke()
        progress, result = asyncio.run(service.execute(run_id))
        assert not result
        assert progress.state in {"failed", "uncertain"} or boundary == "terminal"
        assert calls == int(boundary in {"after_send", "checking", "terminal"})
        assert asyncio.run(service.execute(run_id)) == (progress, ())


@pytest.mark.parametrize("boundary", ["queued", "retrieve", "focused", "synthesis", "verify"])
def test_cancel_wins_at_live_boundaries(tmp_path, monkeypatch, boundary):
    raw_query = RetrievalService.query
    raw_send = FakeLLMClient.stream_events
    raw_verify = grounded.verify
    with fixture_service(tmp_path / "source.json", SUBJECT, [BASE, FOCUSED]) as service:
        req = request(("capacity", "duration")) if boundary == "focused" else request()
        run_id = service.submit(req)

        async def query(retrieval, spec, **kwargs):
            if boundary == "retrieve" or (boundary == "focused" and spec.query == f"{SUBJECT}_duration"):
                service.cancel(run_id)
            return await raw_query(retrieval, spec, **kwargs)

        async def send(*args, **kwargs):
            if boundary == "synthesis":
                service.cancel(run_id)
            async for event in raw_send(*args, **kwargs):
                yield event

        def verify(*args, **kwargs):
            if boundary == "verify":
                service.cancel(run_id)
            return raw_verify(*args, **kwargs)

        monkeypatch.setattr(RetrievalService, "query", query)
        monkeypatch.setattr(FakeLLMClient, "stream_events", send)
        monkeypatch.setattr(grounded, "verify", verify)
        if boundary == "queued":
            service.cancel(run_id)
        progress, result = asyncio.run(service.execute(run_id))
        assert progress.cancel_requested and not result
        assert progress.state == ("canceled" if boundary in {"queued", "verify"} else "uncertain")
        assert asyncio.run(service.execute(run_id)) == (progress, ())


@pytest.mark.parametrize("boundary", ["retrieve", "synthesis", "between_steps", "reserved", "verify"])
def test_crash_and_stale_lease_preserve_canonical_keys(tmp_path, monkeypatch, boundary):
    calls = []
    with fixture_service(tmp_path / "source.json", SUBJECT, [BASE]) as service:
        run_id = service.submit(request())
        raw_reserve = WorkflowRow.reserve
        query = RetrievalService.query
        raw_infer = workflows.grounded.infer

        async def query_step(self, spec, **kwargs):
            calls.append(spec.idempotency_key)
            if boundary == "retrieve":
                raise SystemExit(23)
            return await query(self, spec, **kwargs)

        async def infer_step(*args, **kwargs):
            if boundary == "reserved":
                raise SystemExit(23)
            return await raw_infer(*args, **kwargs)

        async def send_step(*args, **kwargs):
            raise SystemExit(23)
            yield  # pragma: no cover

        def reserve_step(self, step, *args, **kwargs):
            if step == "synthesis":
                raise SystemExit(23)
            return raw_reserve(self, step, *args, **kwargs)

        with monkeypatch.context() as patcher:
            patcher.setattr(RetrievalService, "query", query_step)
            patcher.setattr(workflows.grounded, "infer", infer_step)
            if boundary == "synthesis":
                patcher.setattr(FakeLLMClient, "stream_events", send_step)
            if boundary == "between_steps":
                patcher.setattr(WorkflowRow, "reserve", reserve_step)
            if boundary == "verify":
                def crash(*args):
                    raise SystemExit(23)
                patcher.setattr(grounded, "verify", crash)
            with pytest.raises(SystemExit):
                asyncio.run(service.execute(run_id))
        scope = service.scope_digest()
        with service.store.locked(scope, run_id) as row:
            row.record["lease"] = 0
        monkeypatch.setattr(RetrievalService, "query", query_step)
        progress, result = asyncio.run(service.execute(run_id))
        assert not result and len(calls) == 1
        assert progress.reason == (
            "uncertain_effect" if boundary in {"retrieve", "synthesis"} else "ephemeral_state_lost"
        )
        if boundary == "verify":
            assert progress.attempts[-1].resources.verifier_calls_charged == 1
            assert progress.attempts[-1].resources.observed_calls is None
        if progress.state == "uncertain":
            active = progress.attempts[-1]
            assert active.state == "uncertain" and active.resources.observed_calls is None
            assert active.operation_binding.child_key == uuid5(run_id, active.step)
        assert asyncio.run(service.execute(run_id)) == (progress, ())


def test_deadline_exhaustion_and_count_quota(tmp_path):
    with fixture_service(tmp_path / "source.json", SUBJECT, [BASE]) as service:
        run_id = service.submit(request())
        with service.store.locked(service.scope_digest(), run_id) as row:
            row.deadline = row.now - timedelta(seconds=1)
        progress, claims = asyncio.run(service.execute(run_id))
        assert not claims and not progress.attempts and progress.reason == "budget_exhausted"
        progress, claims = execute(service, request(limits=grounded.HARD_LIMIT.model_copy(update={"count_calls": 1})))
        assert not claims
        synth = progress.attempts[-1]
        assert synth.resources.observed_calls == 0 and synth.resources.count_calls == 1


def test_synchronized_seal_and_fixture_mutation_is_detected(tmp_path):
    for name in (*runner.SEALED, "seal.json"):
        shutil.copy(runner.FILES / name, tmp_path / name)
    path = tmp_path / "cases.json"
    path.write_bytes(path.read_bytes() + b"\n")
    seal_path = tmp_path / "seal.json"
    seal = json.loads(seal_path.read_bytes())
    seal["cases.json"] = sha256(path.read_bytes()).hexdigest()
    seal_path.write_text(json.dumps(seal))
    with pytest.raises(ValueError, match="external_seal_changed"):
        runner.load(tmp_path)


@pytest.mark.parametrize("control", ["always_pass", "always_inconclusive"])
def test_benchmark_rejects_untrustworthy_verifier(monkeypatch, control):
    def bogus(task, items, raw, gaps):
        if control == "always_inconclusive":
            return (), ("verification_inconclusive",) * len(gaps)
        result = grounded.Candidate.model_validate_json(raw).claims
        slots = {claim.slot for claim in result}
        return result, tuple(None if slot in slots else "missing_evidence" for slot in range(len(gaps)))

    monkeypatch.setattr(grounded, "verify", bogus)
    report, _ = asyncio.run(runner.evaluate(holdout_only=True))
    assert report["verdict"] == "BLOCKED"
    assert bool(report["safety_vetoes"]) == (control == "always_pass")


def test_sealed_evaluation(capsys):
    assert runner.main() == 0
    output = capsys.readouterr().out
    report = json.loads(output.splitlines()[-1])
    assert report["semantic_sha256"] == "29d2f779ea9ee127e134a2c4fd4555a8772f2e3ca77d9fdcf86f71bbf27b9e99"
    print(output, end="")


def test_unregistered_subject_cannot_become_a_durable_query(tmp_path):
    with fixture_service(tmp_path / "source.json", SUBJECT, [BASE]) as service:
        req = request()
        different = req.model_copy(update={"task": req.task.model_copy(update={"subject": "outside"})})
        with pytest.raises(Stop, match="policy_denied"):
            service.submit(different)
        assert not service.store.rows


def test_clipped_source_cannot_hide_conflicting_records(tmp_path):
    path = tmp_path / "source.json"
    with fixture_service(path, SUBJECT, [BASE]) as service:
        original = path.read_bytes()
        installation = json.loads(original)
        document = installation["documents"][0]
        document["text"] += "padding " * 160 + "\nFACT record1 capacity 777;\n"
        document["content_sha256"] = sha256(document["text"].encode()).hexdigest()
        path.write_text(json.dumps(installation))
        from dataclasses import replace

        snapshot_digest = sha256(path.read_bytes()).hexdigest()
        service.grounded_host = replace(
            service.grounded_host, authorize_fixture=lambda scope, purpose, source, endpoint, task: (
                source == snapshot_digest
            ),
        )
        progress, claims = execute(service)
        assert not claims and progress.verification.gaps == ("verification_inconclusive",)


def test_trace_and_debug_logs_omit_ephemeral_content(tmp_path, caplog):
    caplog.set_level("DEBUG")
    trace = Trace()
    with trace.capture(), fixture_service(tmp_path / "source.json", SUBJECT, [BASE]) as service:
        progress, claims = execute(service)
    assert progress.outcome == "complete" and claims
    snapshot, _ = trace.snapshot()
    assert snapshot
    redacted = json.dumps(snapshot) + caplog.text
    for marker in ("CANARY_DO_NOT_RETAIN", "FACT record1", "record1_overview", '"claims": [', '"quote"'):
        assert marker not in redacted


def test_unresolved_task_abstains_before_reservation(tmp_path):
    with fixture_service(tmp_path / "source.json", SUBJECT, [BASE]) as service:
        req = request()
        req = req.model_copy(update={"task": req.task.model_copy(update={"ambiguity": "unresolved"})})
        with pytest.raises(Stop, match="evidence_insufficient"):
            service.submit(req)
        assert not service.store.rows
