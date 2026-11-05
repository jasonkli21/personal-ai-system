"""Native JSON round-trip and process-loss behavior for adaptive attempts."""

import asyncio
import multiprocessing
import os
from contextlib import aclosing
from pathlib import Path
from uuid import UUID, uuid5

import pytest

from personal_ai.evaluation.reasoning_adaptive.fixture import FIXTURE_BUILD, FIXTURE_PROTOCOL
from personal_ai.evaluation.reasoning_orchestrator.fixture import synthetic_service
from personal_ai.llm.fake import FakeLLMClient
from personal_ai.llm.workflow_fixture import fixture_attempt
from personal_ai.persistence.postgres import PostgresDatabase
from personal_ai.persistence.postgres.workflows import PostgresWorkflowStore, WorkflowRow
from personal_ai.reasoning.adaptive_control import LocalPolicyControl
from personal_ai.workflow.adaptive import AdaptiveHost, finite_fixture_binding
from personal_ai.workflow.reasoning import Fixture
from tests.persistence import test_workflow_postgres as workflow_tests
from tests.persistence.test_workflow_postgres import expire_lease
from tests.test_reasoning_adaptive import OTHER, PART, canary
from tests.test_reasoning_orchestrator import request

pytestmark = pytest.mark.persistence_integration
database = workflow_tests.database
FIXTURE = Fixture(answer=PART, revision=OTHER)


def record_send(path, child_key):
    with Path(path).open("a") as witness:
        witness.write(f"{child_key}\n")


def crash_worker(dsn, run_id, phase, directory, public_key, sent):
    db = PostgresDatabase(dsn, environment="test")
    raw_send, raw_reserve = FakeLLMClient.stream_events, WorkflowRow.reserve

    async def send(client, *args, **kwargs):
        child_key = fixture_attempt.get().child_key
        record_send(sent, child_key)
        if phase == "after_dispatch" and child_key == uuid5(UUID(run_id), "candidate_alternative"):
            os._exit(23)
        async with aclosing(raw_send(client, *args, **kwargs)) as events:
            async for event in events:
                yield event

    def reserve(row, name, *args, **kwargs):
        if phase == "before_reserve" and name == "candidate_alternative":
            os._exit(23)
        return raw_reserve(row, name, *args, **kwargs)

    FakeLLMClient.stream_events = send
    WorkflowRow.reserve = reserve
    with synthetic_service(FIXTURE, store=PostgresWorkflowStore(db)) as service:
        binding = finite_fixture_binding(request("independent").task, service.reasoning_host.fixture_digest)
        service.adaptive_host = AdaptiveHost(
            LocalPolicyControl(Path(directory)), service.scope_digest(),
            FIXTURE_BUILD, FIXTURE_PROTOCOL, public_key, frozenset({binding}),
        )
        asyncio.run(service.execute(UUID(run_id)))
    db.close()


@pytest.mark.parametrize("phase", ["before_reserve", "after_dispatch"])
def test_native_adaptive_recovery_and_rollback(database, isolated_postgres_dsn, tmp_path, phase, monkeypatch):
    directory = tmp_path / "control"
    directory.mkdir(mode=0o700)
    sent = tmp_path / "sent"
    raw_send = FakeLLMClient.stream_events

    async def send(client, *args, **kwargs):
        record_send(sent, fixture_attempt.get().child_key)
        async with aclosing(raw_send(client, *args, **kwargs)) as events:
            async for event in events:
                yield event

    monkeypatch.setattr(FakeLLMClient, "stream_events", send)
    with synthetic_service(FIXTURE, store=PostgresWorkflowStore(database)) as service:
        control = canary(service, directory)
        original = request("independent")
        run_id = service.submit(original)
        pinned = service.status(run_id)
        worker = multiprocessing.get_context("spawn").Process(target=crash_worker, args=(
            isolated_postgres_dsn, str(run_id), phase, str(directory.resolve()),
            service.adaptive_host.reviewer_key, str(sent),
        ))
        worker.start()
        try:
            worker.join(20)
            assert worker.exitcode == 23
        finally:
            if worker.is_alive():
                worker.kill()
                worker.join(5)
            worker.close()
        control.rollback()
        expire_lease(database, run_id)
        progress, result = asyncio.run(service.execute(run_id))
        assert progress.plan_digest == pinned.plan_digest
        assert progress.adaptive_decision == pinned.adaptive_decision
        assert service.submit(original) == run_id
        assert asyncio.run(service.execute(run_id)) == (progress, ())
        assert sent.read_text().splitlines() == [
            str(uuid5(run_id, "candidate_first")), str(uuid5(run_id, "candidate_alternative")),
        ]
        if phase == "before_reserve":
            assert progress.state == "succeeded" and result == ((0, 3), (1, 6))
        else:
            assert progress.state == "uncertain" and not result
            assert progress.attempts[-1].resources.physical_attempts is None
        with service.store.locked(service.scope_digest(), run_id) as row:
            assert row.spec is None and "checkpoints" not in row.record
