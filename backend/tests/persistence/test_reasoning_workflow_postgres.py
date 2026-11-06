"""Native process, fence and acknowledgement fault tests for synthetic reasoning."""

import asyncio
import multiprocessing
import os
from contextlib import aclosing, contextmanager
from dataclasses import replace
from uuid import UUID, uuid4, uuid5

import pytest

from personal_ai.contracts.execution import continuation_message_id
from personal_ai.evaluation.reasoning_orchestrator.fixture import synthetic_service
from personal_ai.llm import execution
from personal_ai.llm.fake import FakeLLMClient
from personal_ai.persistence.postgres import PostgresDatabase
from personal_ai.persistence.postgres.workflows import PostgresWorkflowStore, WorkflowRow
from personal_ai.storage.errors import PersistenceConflict
from personal_ai.workflow import service as workflow
from personal_ai.workflow.reasoning import ENDPOINT_DIGEST, Fixture, ReasoningHost
from tests.persistence import test_workflow_postgres as workflow_tests
from tests.persistence.test_workflow_postgres import expire_lease
from tests.test_reasoning_orchestrator import request

pytestmark = pytest.mark.persistence_integration
database = workflow_tests.database
FIXTURE = Fixture(answer='{"values":[3]}')


def _write_receipt(path):
    with open(path, "a") as receipt:
        receipt.write("physical_send\n")


def _witness(original, path):
    async def stream(self, *args, **kwargs):
        _write_receipt(path)
        async with aclosing(original(self, *args, **kwargs)) as events:
            async for event in events:
                yield event
    return stream


def _process(dsn, run_id, phase, sent, ready, go):
    db = PostgresDatabase(dsn, environment="test")
    FakeLLMClient.stream_events = _witness(FakeLLMClient.stream_events, sent)
    if phase in {"before_reserve", "between_steps"}:
        reserve = WorkflowRow.reserve

        def stop(row, step, *args, **kwargs):
            if phase == "before_reserve" or step == "check":
                os._exit(23)
            return reserve(row, step, *args, **kwargs)
        WorkflowRow.reserve = stop
    elif phase in {"before_check", "after_check"}:
        check = workflow.run_check

        def stop(*args):
            if phase == "after_check":
                check(*args)
            os._exit(23)
        workflow.run_check = stop
    elif phase in {"after_reserve", "after_ack"}:
        infer = ReasoningHost.infer

        async def stop(host, *args, **kwargs):
            if phase == "after_ack":
                await infer(host, *args, **kwargs)
            os._exit(23)
        ReasoningHost.infer = stop
    elif phase == "after_dispatch":
        emit = execution.emit

        def stop(event, state, **facts):
            if event == execution.Event.DISPATCH and facts.get("operation") == "streaming":
                os._exit(23)
            return emit(event, state, **facts)
        execution.emit = stop

    store = PostgresWorkflowStore(db)
    if phase == "after_terminal":
        locked = store.locked

        @contextmanager
        def stop(*args):
            with locked(*args) as row:
                yield row
                terminal = row.record["state"] == "succeeded"
            if terminal:
                os._exit(23)

        store.locked = stop
    try:
        with synthetic_service(FIXTURE, store=store) as service:
            ready.put(True)
            if not go.wait(15):
                raise RuntimeError("claim barrier timed out")
            asyncio.run(service.execute(UUID(run_id)))
    finally:
        db.close()


def processes(dsn, run_id, phase, sent, count=1):
    context = multiprocessing.get_context("spawn")
    ready, go = context.Queue(), context.Event()
    workers = [
        context.Process(target=_process, args=(dsn, str(run_id), phase, sent, ready, go))
        for _ in range(count)
    ]
    try:
        for worker in workers:
            worker.start()
        for _ in workers:
            ready.get(timeout=15)
        go.set()
        for worker in workers:
            worker.join(timeout=15)
            assert worker.exitcode == (23 if phase else 0)
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.kill()
                worker.join(timeout=5)
        ready.close()
        ready.join_thread()


@pytest.mark.parametrize("phase,expected_sends", [
    ("before_reserve", 0), ("after_reserve", 0), ("after_dispatch", 0),
    ("after_ack", 1), ("between_steps", 1), ("after_terminal", 1),
])
def test_process_exit_keeps_original_attempt_and_never_resends_dispatched_work(
    database, isolated_postgres_dsn, tmp_path, monkeypatch, phase, expected_sends,
):
    path = tmp_path / "sends"
    path.touch()
    monkeypatch.setattr(FakeLLMClient, "stream_events", _witness(FakeLLMClient.stream_events, path))
    with synthetic_service(FIXTURE, store=PostgresWorkflowStore(database)) as service:
        original = request()
        run_id = service.submit(original)
        processes(isolated_postgres_dsn, run_id, phase, path)
        assert len(path.read_text().splitlines()) == expected_sends
        prior = service.status(run_id)
        expire_lease(database, run_id)
        progress, result = asyncio.run(service.execute(run_id))
        if phase in {"after_ack", "after_dispatch"}:
            assert not result and progress.reason == "uncertain_effect"
            assert progress.attempts[0].state == "uncertain"
            assert progress.attempts[0].resources.physical_attempts is None
            assert progress.attempts[0].attempt_id == prior.attempts[0].attempt_id
            assert len(path.read_text().splitlines()) == expected_sends
        elif phase == "after_terminal":
            assert progress == prior and progress.outcome == "complete" and not result
            assert len(path.read_text().splitlines()) == 1
        else:
            assert result == ((0, 3),) and progress.outcome == "complete"
            assert len(path.read_text().splitlines()) == 1
            if phase == "after_reserve":
                assert progress.attempts[0].state == "abandoned"
                assert progress.attempts[0].operation_binding == progress.attempts[1].operation_binding
        assert service.submit(original) == run_id
        assert asyncio.run(service.execute(run_id)) == (progress, ())
        for attempt in progress.attempts:
            binding = attempt.operation_binding
            if binding.tool_id == "reasoning.inference.v1":
                child = uuid5(run_id, attempt.step)
                assert binding.child_key == child and binding.endpoint_digest == ENDPOINT_DIGEST
                scope = service.retrieval.scope
                assert binding.child_message_id == continuation_message_id(
                    run_id, scope.owner_id, scope, child,
                )


def test_independent_processes_send_once_and_keep_intent_collision(database, isolated_postgres_dsn, tmp_path):
    path = tmp_path / "sends"
    with synthetic_service(FIXTURE, store=PostgresWorkflowStore(database)) as service:
        original = request()
        run_id = service.submit(original)
        processes(isolated_postgres_dsn, run_id, None, path, count=2)
        assert path.read_text().splitlines() == ["physical_send"]
        progress = service.status(run_id)
        assert progress.outcome == "complete"
        assert [attempt.state for attempt in progress.attempts] == ["succeeded", "succeeded"]
        assert [attempt.resources.physical_attempts for attempt in progress.attempts] == [1, 0]
        assert service.submit(original) == run_id
        with pytest.raises(PersistenceConflict, match="workflow_intent_conflict"):
            service.submit(original.model_copy(update={"effort": "low"}))
        with database.transaction() as connection:
            retained_spec, record = connection.execute(
                "SELECT spec, record FROM workflow_runs WHERE run_id=%s", (run_id,),
            ).fetchone()
        assert retained_spec is None and "checkpoints" not in record


@pytest.mark.parametrize("phase", ["before_check", "after_check"])
def test_native_verifier_crash_recomputes_only_with_remaining_budget(
    database, isolated_postgres_dsn, tmp_path, monkeypatch, phase,
):
    path = tmp_path / "sends"
    path.touch()
    monkeypatch.setattr(FakeLLMClient, "stream_events", _witness(FakeLLMClient.stream_events, path))
    with synthetic_service(FIXTURE, store=PostgresWorkflowStore(database)) as service:
        run_id = service.submit(request())
        processes(isolated_postgres_dsn, run_id, phase, path)
        assert path.read_text().splitlines() == ["physical_send"]
        expire_lease(database, run_id)
        progress, result = asyncio.run(service.execute(run_id))
        assert progress.reason == "sufficient" and result == ((0, 3),)
        verifiers = [attempt for attempt in progress.attempts if attempt.operation_binding.tool_id == "reasoning.verify.v1"]
        assert [attempt.resources.verifier_calls for attempt in verifiers] == [1, 1]
        assert len(path.read_text().splitlines()) == 1


@pytest.mark.parametrize("phase", ["queued", "reserved", "dispatched", "checking"])
def test_cancellation_keeps_classification_and_prevents_follow_on_sends(database, monkeypatch, phase):
    actual = FakeLLMClient.stream_events
    physical = 0

    async def witness(self, *args, **kwargs):
        nonlocal physical
        physical += 1
        if phase == "dispatched":
            service.cancel(run_id)
        async for event in actual(self, *args, **kwargs):
            yield event

    infer = ReasoningHost.infer

    async def maybe_cancel(host, *args, **kwargs):
        if phase == "reserved":
            service.cancel(run_id)
        return await infer(host, *args, **kwargs)

    check = workflow.run_check

    def maybe_cancel_check(*args):
        if phase == "checking":
            service.cancel(run_id)
        return check(*args)

    with synthetic_service(FIXTURE, store=PostgresWorkflowStore(database)) as service:
        run_id = service.submit(request("correctable"))
        monkeypatch.setattr(ReasoningHost, "infer", maybe_cancel)
        monkeypatch.setattr(FakeLLMClient, "stream_events", witness)
        monkeypatch.setattr(workflow, "run_check", maybe_cancel_check)
        if phase == "queued":
            service.cancel(run_id)
        progress, result = asyncio.run(service.execute(run_id))
        uncertain = phase == "dispatched"
        assert progress.reason == ("uncertain_effect" if uncertain else "cancelled")
        assert progress.cancel_requested and not result
        assert physical == (0 if phase in {"queued", "reserved"} else 1)
        assert asyncio.run(service.execute(run_id)) == (progress, ())


@pytest.mark.parametrize("binding", ["endpoint", "invocation", "attempt"])
def test_mismatched_canonical_receipt_cannot_complete(database, monkeypatch, binding):
    actual = execution.LocalFakeGeneration.stream_reasoning

    async def corrupt(self, *args, **kwargs):
        async for event in actual(self, *args, **kwargs):
            if event.kind == "terminal":
                metadata = event.metadata
                changes = {
                    "endpoint": {"identity": replace(metadata.identity, model_id="wrong-model")},
                    "invocation": {"invocation_id": str(uuid4())},
                    "attempt": {"attempt_ids": (str(uuid4()),)},
                }
                event = replace(event, metadata=replace(metadata, **changes[binding]))
            yield event

    monkeypatch.setattr(execution.LocalFakeGeneration, "stream_reasoning", corrupt)
    with synthetic_service(FIXTURE, store=PostgresWorkflowStore(database)) as service:
        progress, result = asyncio.run(service.execute(service.submit(request())))
    assert progress.reason == "uncertain_effect" and not result
    assert progress.attempts[0].resources.physical_attempts is None


def test_revocation_after_inference_suppresses_final_disclosure(database, monkeypatch):
    revoked = False
    actual = workflow.run_check

    def authority():
        if revoked:
            raise ValueError("fixture authority withdrawn")

    def revoke(*args):
        nonlocal revoked
        result = actual(*args)
        revoked = True
        return result

    monkeypatch.setattr(workflow, "run_check", revoke)
    with synthetic_service(FIXTURE, store=PostgresWorkflowStore(database), authority=authority) as service:
        run_id = service.submit(request())
        with pytest.raises(workflow.WorkflowDenied):
            asyncio.run(service.execute(run_id))
        with pytest.raises(workflow.WorkflowDenied):
            service.status(run_id)
        revoked = False
        progress, result = asyncio.run(service.execute(run_id))
        assert progress.reason == "uncertain_effect" and not result
        assert progress.attempts[0].resources.physical_attempts == 1


def test_live_deadline_after_reserve_abandons_without_dispatch(database, monkeypatch):
    infer = ReasoningHost.infer

    async def expire(host, *args, **kwargs):
        with database.transaction() as connection:
            connection.execute(
                "UPDATE workflow_runs SET deadline=clock_timestamp() WHERE run_id=%s", (run_id,),
            )
        return await infer(host, *args, **kwargs)

    monkeypatch.setattr(ReasoningHost, "infer", expire)
    with synthetic_service(FIXTURE, store=PostgresWorkflowStore(database)) as service:
        run_id = service.submit(request())
        progress, result = asyncio.run(service.execute(run_id))
        assert not result and progress.reason == "budget_exhausted"
        assert progress.attempts[0].state == "abandoned"
        assert progress.attempts[0].resources.physical_attempts == 0


def test_cancel_after_dispatch_commit_before_send_withholds_physical_attempt(database, monkeypatch):
    store = PostgresWorkflowStore(database)
    lock = store.locked
    cancelled = False

    @contextmanager
    def after_commit(*args):
        nonlocal cancelled
        with lock(*args) as row:
            original = row.pending
            reserved = original is not None and original["state"] == "reserved"
            yield row
            sent = row.pending is not None and row.pending["state"] == "dispatched"
        if reserved and sent and not cancelled:
            cancelled = True
            service.cancel(run_id)

    async def forbidden(*args, **kwargs):
        pytest.fail("physical send occurred after cancellation")
        yield

    monkeypatch.setattr(store, "locked", after_commit)
    monkeypatch.setattr(FakeLLMClient, "stream_events", forbidden)
    with synthetic_service(FIXTURE, store=store) as service:
        run_id = service.submit(request())
        progress, result = asyncio.run(service.execute(run_id))
    assert cancelled and not result
    assert progress.reason == "uncertain_effect"
    assert progress.attempts[0].resources.physical_attempts is None
