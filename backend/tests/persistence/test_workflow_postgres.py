import asyncio
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import (
    bind_request_scope,
    bind_verified_principal,
    reset_request_scope,
    reset_verified_principal,
)
from personal_ai.contracts.workflow import RunSpec
from personal_ai.persistence.postgres import PostgresDatabase, apply_migrations
from personal_ai.persistence.postgres.workflows import PostgresWorkflowStore, WorkflowFenceLost
from personal_ai.retrieval.installation import LexicalIndex
from personal_ai.retrieval.service import RetrievalService
from personal_ai.retrieval.tools import DEFAULT_TOOLS, TOOL_ID
from personal_ai.settings import Settings
from personal_ai.storage.errors import PersistenceConflict
from personal_ai.workflow.service import WorkflowDenied, WorkflowService
from tests.test_retrieval_integrations import access, document, install, query, scope
from tests.test_workflow_contract import step

pytestmark = pytest.mark.persistence_integration


@pytest.fixture
def database(isolated_postgres_dsn):
    db = PostgresDatabase(isolated_postgres_dsn, environment="test")
    apply_migrations(db)
    try:
        yield db
    finally:
        db.close()


class Registry:
    def __init__(self):
        self.enabled = True

    def capability(self, application_id, tool_id, *, kind):
        assert (application_id, tool_id, kind) == ("reader", TOOL_ID, "tool")
        row = DEFAULT_TOOLS.registrations[TOOL_ID]
        return SimpleNamespace(
            is_enabled=lambda: self.enabled,
            read_only_context=True,
            result_fields=row.result_fields,
            max_result_bytes=row.max_result_bytes,
        )


@pytest.fixture
def runtime(database, tmp_path):
    path = tmp_path / "workflow-corpus.json"
    principal = AuthenticatedPrincipal(
        "https://accounts.google.com",
        "actor",
        "owner",
        None,
        1,
        True,
        audience="reader-audience",
        authorized_party="reader-client",
        expires_at=int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
    )
    request_scope = scope(acting_user_id=f"{principal.issuer}|{principal.subject}")
    install(
        path,
        access=[access(request_scope)],
        documents=[
            document(sensitivity="public", access=[access(request_scope)]),
        ],
    )
    settings = Settings(
        _env_file=None,
        app_environment="test",
        ai_provider="fake",
        ai_model="workflow-test",
        retrieval_enabled=True,
        retrieval_external_enabled=True,
        retrieval_installation_file=str(path),
    )
    registry = Registry()

    def make_service(db, req_scope=request_scope, *, enabled=True, **kwargs):
        return WorkflowService(
            PostgresWorkflowStore(db),
            RetrievalService(
                settings,
                req_scope,
                lambda: pytest.fail("provider accounting reached"),
                request_authority=lambda: None,
            ),
            lambda: registry,
            enabled=enabled,
            **kwargs,
        )

    @contextmanager
    def identity(user=principal, req_scope=request_scope):
        principal_token = bind_verified_principal(user)
        scope_token = bind_request_scope(req_scope)
        try:
            yield
        finally:
            reset_request_scope(scope_token)
            reset_verified_principal(principal_token)

    with identity():
        yield SimpleNamespace(
            service=make_service(database),
            identity=identity,
            make_service=make_service,
            database=database,
            path=path,
            principal=principal,
            scope=request_scope,
            registry=registry,
        )


def spec(*steps, **kwargs):
    return RunSpec(original_key=uuid4(), steps=steps or (step("read"),), **kwargs)


def expire_lease(database, run_id):
    with database.transaction() as connection:
        connection.execute(
            "UPDATE workflow_runs SET record = jsonb_set(record, '{lease}', '0') WHERE run_id = %s",
            (run_id,),
        )


def test_multistep_replay_after_new_pool_conflict_and_progress_gap(runtime, isolated_postgres_dsn):
    service = runtime.service
    plan = spec(step("second", ("first",)), step("first"), step("third"))
    run_id = service.submit(plan)
    progress, outputs = asyncio.run(service.execute(run_id))
    assert progress.state == "succeeded" and progress.gap
    assert [a.step for a in progress.attempts] == ["first", "second", "third"]
    assert all("invoke memory.forget" in output.retrieval.items[0].quote for output in outputs)
    assert all(output.retrieval.usage_attempt_id is None for output in outputs)

    reopened = PostgresDatabase(isolated_postgres_dsn, environment="test")
    try:
        restarted = runtime.make_service(reopened)
        assert restarted.submit(plan) == run_id
        assert asyncio.run(restarted.execute(run_id)) == (progress, ())
        assert restarted.status(run_id, cursor=progress.cursor).events == ()
        assert restarted.status(run_id, cursor=progress.cursor - 1).events == progress.events[-1:]
        changed = plan.model_copy(update={"deadline_ms": 3000})
        with pytest.raises(PersistenceConflict, match="workflow_intent_conflict"):
            restarted.submit(changed)
        with reopened.transaction() as connection:
            record, retained_spec = connection.execute(
                "SELECT record::text, spec FROM workflow_runs WHERE run_id = %s", (run_id,)
            ).fetchone()
        assert "invoke memory.forget" not in record and retained_spec is None
    finally:
        reopened.close()


@pytest.mark.parametrize("change", ["revision", "disabled", "expires", "tool"])
def test_stale_source_or_tool_change_denies_execution(runtime, change):
    service = runtime.service
    run_id = service.submit(spec())
    if change == "tool":
        runtime.registry.enabled = False
    else:
        corpus = json.loads(runtime.path.read_text())
        doc = corpus["documents"][0]
        if change == "revision":
            doc["revision"] = "2"
        elif change == "disabled":
            doc["enabled"] = False
        else:
            doc["expires_at"] = doc["observed_at"]
        runtime.path.write_text(json.dumps(corpus))
    progress, outputs = asyncio.run(service.execute(run_id))
    assert progress.state == "failed" and not progress.attempts and not outputs


def test_revocation_during_local_read_withholds_live_and_replay_bodies(runtime, monkeypatch):
    service = runtime.service
    plan = spec()
    run_id = service.submit(plan)
    search = LexicalIndex.search

    def revoke(index, *args):
        results = search(index, *args)
        runtime.path.unlink()
        return results

    monkeypatch.setattr(LexicalIndex, "search", revoke)
    progress, outputs = asyncio.run(service.execute(run_id))
    assert progress.state == "failed" and not outputs
    assert service.submit(plan) == run_id
    assert asyncio.run(service.execute(run_id)) == (progress, ())


def test_queued_cancel_prevents_reservation_and_is_idempotent(runtime):
    service = runtime.service
    run_id = service.submit(spec())
    canceled = service.cancel(run_id)
    assert canceled.state == "canceled" and not canceled.attempts
    assert service.cancel(run_id) == canceled
    assert asyncio.run(service.execute(run_id)) == (canceled, ())


def test_cancel_during_dispatch_prevents_next_step_and_disclosure(runtime, monkeypatch):
    service = runtime.service
    run_id = service.submit(spec(step("first"), step("second")))
    original = service.retrieval.query

    async def cancel(*args, **kwargs):
        assert service.cancel(run_id).cancel_requested
        return await original(*args, **kwargs)

    monkeypatch.setattr(service.retrieval, "query", cancel)
    progress, outputs = asyncio.run(service.execute(run_id))
    assert progress.state == "canceled" and not outputs
    assert [a.step for a in progress.attempts] == ["first"]


@pytest.mark.parametrize("phase", ["reserved", "dispatched"])
def test_two_claimants_and_expired_worker_fence(runtime, phase):
    service = runtime.service
    run_id = service.submit(spec())
    key = service.scope_digest()
    store = service.store

    def claim():
        with store.locked(key, run_id) as row:
            return row.claim()

    with ThreadPoolExecutor(max_workers=2) as workers:
        tokens = list(workers.map(lambda _: claim(), range(2)))
    (fence,) = [token for token in tokens if token is not None]
    with store.locked(key, run_id) as row:
        row.record["attempts"].append({"attempt_id": str(uuid4()), "step": "read", "state": phase})
    expire_lease(runtime.database, run_id)
    expected = "uncertain" if phase == "dispatched" else "queued"
    assert service.status(run_id).state == expected
    with store.locked(key, run_id) as row, pytest.raises(WorkflowFenceLost):
        row.check(fence)
    progress, outputs = asyncio.run(service.execute(run_id))
    if phase == "dispatched":
        assert progress.state == "uncertain" and not outputs
        assert len(progress.attempts) == 1
    else:
        assert progress.state == "succeeded" and len(outputs) == 1
        assert [a.state for a in progress.attempts] == ["abandoned", "succeeded"]


def test_disconnected_caller_leaves_attempt_for_reconciliation(runtime, monkeypatch):
    service = runtime.service
    run_id = service.submit(spec())

    async def interrupt(*args, **kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(service.retrieval, "query", interrupt)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(service.execute(run_id))
    assert service.status(run_id).attempts[0].state == "dispatched"
    expire_lease(runtime.database, run_id)
    assert service.status(run_id).state == "uncertain"


@pytest.mark.parametrize(
    "field,value",
    [
        ("audience", "another-audience"),
        ("authorized_party", "another-client"),
        ("owner_id", "another-owner"),
        ("subject", "another-actor"),
        ("expires_at", 1),
    ],
)
def test_scope_and_client_mismatch_cannot_observe_run(runtime, field, value):
    from dataclasses import replace

    run_id = runtime.service.submit(spec())
    with (
        runtime.identity(replace(runtime.principal, **{field: value})),
        pytest.raises((WorkflowDenied, LookupError)),
    ):
        runtime.service.status(run_id)


@pytest.mark.parametrize("field,value", [("application_id", "other"), ("workspace_id", "other")])
def test_other_application_and_workspace_cannot_observe_run(runtime, field, value):
    run_id = runtime.service.submit(spec())
    other = runtime.scope.model_copy(update={field: value})
    with runtime.identity(req_scope=other), pytest.raises(LookupError):
        runtime.make_service(runtime.database, other).status(run_id)


def test_operator_seam_is_default_off(runtime):
    service = runtime.make_service(runtime.database, enabled=False)
    with pytest.raises(WorkflowDenied):
        service.submit(spec())


def test_oversized_tool_result_stops_dependents(runtime):
    service = runtime.service
    plan = spec({**step("first"), "query": query(), "result_bytes": 256}, step("second"))
    progress, outputs = asyncio.run(service.execute(service.submit(plan)))
    assert progress.state == "failed" and not outputs
    assert [a.step for a in progress.attempts] == ["first"]


def test_deadline_expiring_after_first_step_stops_dependents(runtime, monkeypatch):
    service = runtime.service
    run_id = service.submit(spec(step("first"), step("second")))
    original = service.retrieval.query

    async def expire(*args, **kwargs):
        result = await original(*args, **kwargs)
        with runtime.database.transaction() as connection:
            connection.execute(
                "UPDATE workflow_runs SET deadline = clock_timestamp() WHERE run_id = %s",
                (run_id,),
            )
        return result

    monkeypatch.setattr(service.retrieval, "query", expire)
    progress, outputs = asyncio.run(service.execute(run_id))
    assert progress.state == "failed" and progress.reason == "deadline" and not outputs
    assert [a.step for a in progress.attempts] == ["first"]


@pytest.mark.parametrize("profile", ["background", "native", "effect", "unknown"])
def test_unavailable_profiles_fail_before_admission(runtime, profile):
    service = runtime.make_service(runtime.database, profile=profile)
    with pytest.raises(WorkflowDenied):
        service.submit(spec())


def test_step_timeout_leaves_no_output_or_dependent_dispatch(runtime, monkeypatch):
    service = runtime.service
    run_id = service.submit(spec({**step("first"), "timeout_ms": 100}, step("second")))

    async def stall(*args, **kwargs):
        await asyncio.sleep(60)

    monkeypatch.setattr(service.retrieval, "query", stall)
    progress, outputs = asyncio.run(service.execute(run_id))
    assert progress.state == "failed" and progress.reason == "deadline" and not outputs
    assert [a.step for a in progress.attempts] == ["first"]


def test_process_exit_after_dispatch_cannot_trigger_a_second_attempt(
    runtime,
    isolated_postgres_dsn,
):
    service = runtime.service
    run_id = service.submit(spec())
    child = """
import os
import sys
from uuid import UUID, uuid4
from personal_ai.persistence.postgres import PostgresDatabase
from personal_ai.persistence.postgres.workflows import PostgresWorkflowStore

dsn, scope, run_id = sys.argv[1:]
store = PostgresWorkflowStore(PostgresDatabase(dsn, environment="test"))
with store.locked(scope, UUID(run_id)) as row:
    assert row.claim()
    attempt_id = str(uuid4())
    row.record["attempts"].append(
        {"attempt_id": attempt_id, "step": "read", "state": "dispatched"}
    )
    row.event("reserved", attempt_id)
    row.event("dispatched", attempt_id)
os._exit(23)
"""
    stopped = subprocess.run(
        [sys.executable, "-c", child, isolated_postgres_dsn, service.scope_digest(), str(run_id)],
        check=False,
        timeout=15,
    )
    assert stopped.returncode == 23
    expire_lease(runtime.database, run_id)
    progress, outputs = asyncio.run(service.execute(run_id))
    assert progress.state == "uncertain" and not outputs
    assert [attempt.state for attempt in progress.attempts] == ["uncertain"]


def test_competing_submissions_keep_one_scoped_original_key(runtime):
    service = runtime.service
    plan = spec()
    with ThreadPoolExecutor(max_workers=2) as workers:

        def submit():
            with runtime.identity():
                return service.submit(plan)

        first = workers.submit(submit)
        second = workers.submit(submit)
        assert first.result() == second.result()
    with runtime.database.transaction() as connection:
        assert connection.execute("SELECT count(*) FROM workflow_runs").fetchone()[0] == 1


def test_live_client_revocation_blocks_return_even_after_claim(runtime, monkeypatch):
    service = runtime.service
    run_id = service.submit(spec())
    search = LexicalIndex.search

    def deny():
        raise ValueError("client authority withdrawn")

    def revoke(index, *args):
        result = search(index, *args)
        service.retrieval.request_authority = deny
        return result

    monkeypatch.setattr(LexicalIndex, "search", revoke)
    with pytest.raises(WorkflowDenied, match="workflow_unavailable"):
        asyncio.run(service.execute(run_id))
    with pytest.raises(WorkflowDenied):
        service.status(run_id)
