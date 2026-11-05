"""Opt-in native grounded row projection and original-key recovery."""

import asyncio
import json
import multiprocessing
import os
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from hashlib import sha256
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
from uuid import uuid5

import pytest

from personal_ai.evaluation.reasoning_grounded.fixture import fixture_service
from personal_ai.persistence.postgres import PostgresDatabase
from personal_ai.persistence.postgres.workflows import PostgresWorkflowStore
from personal_ai.retrieval.service import RetrievalService
from tests.persistence import test_workflow_postgres as workflow_tests
from tests.test_reasoning_grounded import BASE, FOCUSED, SUBJECT, request

pytestmark = pytest.mark.persistence_integration
database = workflow_tests.database


def test_native_grounded_receipt_is_redacted_and_replays_original_key(database, tmp_path):
    store = PostgresWorkflowStore(database)
    with fixture_service(tmp_path / "corpus.json", SUBJECT, [BASE, FOCUSED], store=store) as service:
        req = request(("capacity", "duration"))
        run_id = service.submit(req)
        progress, claims = asyncio.run(service.execute(run_id))
        assert [claim.value for claim in claims] == [3, 9]
        assert progress.outcome == "complete" and progress.gap
        assert service.submit(req) == run_id
        assert asyncio.run(service.execute(run_id)) == (progress, ())
        with store.locked(service.scope_digest(), run_id) as row:
            assert row.spec is None and "CANARY" not in json.dumps(row.record)
        with pytest.raises(LookupError, match="workflow_episode_unavailable"):
            store.terminal_evidence(service.scope_digest(), run_id)


def lose_retrieval_ack(dsn, source_path, run_id, journal):
    source = Path(source_path)
    digest = sha256(source.read_bytes()).hexdigest()
    db = PostgresDatabase(dsn, environment="test")

    async def crash(self, query, **kwargs):
        Path(journal).write_text(str(query.idempotency_key))
        os._exit(23)

    with (
        patch("personal_ai.evaluation.reasoning_grounded.fixture.install", return_value=digest),
        patch.object(RetrievalService, "query", crash),
        fixture_service(source, SUBJECT, [], store=PostgresWorkflowStore(db)) as service,
    ):
        asyncio.run(service.execute(run_id))


def test_native_unknown_retrieval_retains_dispatch_after_process_loss(
    database, isolated_postgres_dsn, tmp_path, monkeypatch,
):
    path = tmp_path / "corpus.json"
    journal = tmp_path / "synthetic-child-key.txt"
    store = PostgresWorkflowStore(database)
    with fixture_service(path, SUBJECT, [BASE], store=store) as service:
        req = request()
        run_id = service.submit(req)
        worker = multiprocessing.get_context("spawn").Process(
            target=lose_retrieval_ack, args=(isolated_postgres_dsn, str(path), run_id, str(journal)),
        )
        worker.start()
        try:
            worker.join(15)
            assert worker.exitcode == 23
        finally:
            if worker.is_alive():
                worker.terminate()
                worker.join(5)
        workflow_tests.expire_lease(database, run_id)
        repeated = []

        async def repeat(self, query, **kwargs):
            repeated.append(query.idempotency_key)
            raise AssertionError("dispatched retrieval cannot be replayed")

        monkeypatch.setattr(RetrievalService, "query", repeat)
        progress, claims = asyncio.run(service.execute(run_id))
        assert not claims and progress.reason == "uncertain_effect" and not repeated
        assert service.submit(req) == run_id
        assert asyncio.run(service.execute(run_id)) == (progress, ())
        child = uuid5(run_id, "initial")
        assert journal.read_text() == str(child)
        attempt, = progress.attempts
        assert attempt.state == "uncertain" and attempt.operation_binding.child_key == child
        assert attempt.resources.observed_calls is None


def test_native_competing_claims_dispatch_once(database, tmp_path, monkeypatch):
    store = PostgresWorkflowStore(database)
    with fixture_service(tmp_path / "corpus.json", SUBJECT, [BASE], store=store) as service:
        run_id = service.submit(request())
        gate = Barrier(2)
        calls = []
        original = RetrievalService.query

        async def observe(self, query, **kwargs):
            calls.append(query.idempotency_key)
            return await original(self, query, **kwargs)

        def execute():
            gate.wait(timeout=5)
            return asyncio.run(service.execute(run_id))

        monkeypatch.setattr(RetrievalService, "query", observe)
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = [
                pool.submit(copy_context().run, execute) for _ in range(2)
            ]
            results = [result.result(timeout=20) for result in claims]
        assert sorted(len(answer) for _, answer in results) == [0, 1]
        assert calls == [uuid5(run_id, "initial")]
        assert service.status(run_id).outcome == "complete"
