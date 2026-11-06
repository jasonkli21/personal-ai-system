"""Explicit single-process loopback preview. The deployed API never mounts it."""

import asyncio
import json
import os
import re
import signal
from contextlib import contextmanager
from secrets import compare_digest
from typing import Literal
from uuid import UUID, uuid4

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from personal_ai.contracts.delegated_tasks import canonical_bytes
from personal_ai.evaluation.reasoning_orchestrator.fixture import FixtureStore, synthetic_service
from personal_ai.reasoning.orchestration import (
    Limits,
    ReasoningRecord,
    Requirement,
    ScopeCeilings,
    Stop,
    Task,
)
from personal_ai.reasoning.orchestration import Request as RunRequest
from personal_ai.reasoning.policy import RequestedEffort
from personal_ai.storage.errors import PersistenceConflict
from personal_ai.workflow.reasoning import Fixture
from personal_ai.workflow.service import WorkflowDenied

CAPABILITY = "reasoning.workflow.synthetic.v1"
PREFIX = "/v1/synthetic-reasoning"
MAX_BODY = 2048
MAX_RUNS = 64
LIMITS = Limits(
    model_calls=1,
    verifier_calls=1,
    count_calls=8,
    count_input_bytes=8192,
    input_bytes=1024,
    output_bytes=128,
    result_bytes=128,
    deadline_ms=6000,
    concurrency=1,
)
CEILINGS = ScopeCeilings(application=LIMITS, workspace=LIMITS, user=LIMITS)
FIXTURES = {"sum": Fixture(answer='{"values":[3]}'), "pair": Fixture(answer='{"values":[3,0]}')}
SLOT = Requirement(operation="add", left=1, right=2)
TASKS = {
    "sum": Task(kind="simple", requirements=(SLOT,)),
    "pair": Task(
        kind="independent", requirements=(SLOT, Requirement(operation="multiply", left=2, right=3))
    ),
}


class Submission(ReasoningRecord):
    capability: Literal["reasoning.workflow.synthetic.v1"]
    original_key: UUID
    task: Literal["sum", "pair"]
    effort: RequestedEffort = "auto"
    limits: Limits | None = None


def _reject(status, code):
    return JSONResponse({"error": {"code": code}}, status_code=status)


def _unique_fields(pairs):
    value = dict(pairs)
    if len(value) != len(pairs):
        raise ValueError("duplicate_field")
    return value


def create_preview(token: str) -> FastAPI:
    if not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", token):
        raise ValueError("synthetic_reasoning_requires_private_random_token")
    credential = ("Bearer " + token).encode()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.admissions_enabled = True
    epoch = uuid4()
    store = FixtureStore()
    active = False

    @app.middleware("http")
    async def authority(request, call_next):
        try:
            check_authority(request)
        except WorkflowDenied:
            return _reject(403, "access_denied")
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    def check_authority(request):
        if (
            request.client is None
            or request.client.host != "127.0.0.1"
            or request.headers.getlist("x-application-id") != ["personal_ai"]
            or request.headers.getlist("x-workspace-id")
            or request.headers.getlist("origin")
        ):
            raise WorkflowDenied("access_denied")
        values = request.headers.getlist("authorization")
        if len(values) != 1 or not compare_digest(values[0].encode(), credential):
            raise WorkflowDenied("access_denied")

    @contextmanager
    def host(request, task="sum"):
        with synthetic_service(
            FIXTURES[task],
            store=store,
            ceilings=CEILINGS,
            authority=lambda: check_authority(request),
        ) as service:
            yield service

    @app.get(PREFIX + "/capability")
    async def capability(request: Request):
        if request.query_params:
            return _reject(422, "validation_error")
        return {
            "capability": CAPABILITY,
            "epoch": epoch,
            "state": "development_only" if app.state.admissions_enabled else "disabled",
            "evidence_tier": "E1",
            "default_enabled": False,
            "strategy": "direct-verified.v1",
            "tasks": list(TASKS),
            "requested_efforts": ["auto", "low", "medium", "high", "max"],
            "effective_effort": "low",
            "limits": LIMITS.model_dump(mode="json"),
            "queue": 0,
            "max_originals": MAX_RUNS,
        }

    @app.post(PREFIX + "/{instance}/runs")
    async def submit(instance: UUID, request: Request):
        nonlocal active
        if instance != epoch:
            return _reject(409, "reasoning_epoch_changed")
        if request.query_params or request.headers.get("content-type") != "application/json":
            return _reject(422, "validation_error")
        if active:
            return _reject(429, "reasoning_busy")
        active = True
        try:
            payload = bytearray()
            try:
                async with asyncio.timeout(2):
                    async for chunk in request.stream():
                        if len(payload) + len(chunk) > MAX_BODY:
                            return _reject(413, "request_body_too_large")
                        payload.extend(chunk)
                fields = json.loads(payload, object_pairs_hook=_unique_fields)
                body = Submission.model_validate_json(canonical_bytes(fields))
                ceilings = LIMITS.model_dump()
                reductions = body.limits.model_dump(exclude_unset=True) if body.limits else {}
                if any(value > ceilings[name] for name, value in reductions.items()):
                    return _reject(422, "validation_error")
                limits = Limits.model_validate(ceilings | reductions)
            except TimeoutError:
                return _reject(408, "request_body_timeout")
            except (ValueError, TypeError, RecursionError):
                return _reject(422, "validation_error")

            with host(request, body.task) as service:
                key = (service.scope_digest(), body.original_key)
                existing = key in store.intents
                if not existing:
                    if not app.state.admissions_enabled:
                        return _reject(403, "reasoning_disabled")
                    if len(store.intents) >= MAX_RUNS:
                        return _reject(429, "reasoning_capacity")
                run = RunRequest(
                    schema_version="reasoning-run-request-v1",
                    original_key=body.original_key,
                    task=TASKS[body.task],
                    effort=body.effort,
                    limits=limits,
                )
                try:
                    run_id = service.submit(run)
                except PersistenceConflict:
                    return _reject(409, "reasoning_intent_conflict")
                except Stop as error:
                    return _reject(422, str(error))
                if existing:
                    return {"progress": service.status(run_id), "result": ()}
                progress, result = await service.execute(run_id)
                return {"progress": progress, "result": result}
        finally:
            active = False

    @app.get(PREFIX + "/{instance}/runs/{key}")
    @app.post(PREFIX + "/{instance}/runs/{key}/cancel")
    async def observe(instance: UUID, key: UUID, request: Request):
        if instance != epoch:
            return _reject(409, "reasoning_epoch_changed")
        params = request.query_params
        cancel = request.method == "POST"
        if cancel:
            if (
                params
                or request.headers.get("content-length", "0") != "0"
                or "transfer-encoding" in request.headers
            ):
                return _reject(422, "validation_error")
            cursor = 0
        else:
            raw_cursor = params.get("cursor", "0")
            if (
                set(params) - {"cursor"}
                or len(params.getlist("cursor")) > 1
                or not re.fullmatch(r"[0-9]{1,8}", raw_cursor)
            ):
                return _reject(422, "validation_error")
            cursor = int(raw_cursor)
        with host(request) as service:
            intent = store.intents.get((service.scope_digest(), key))
            if intent is None:
                return _reject(404, "not_found")
            try:
                progress = (
                    service.cancel(intent[0])
                    if cancel
                    else service.status(intent[0], cursor=cursor)
                )
            except ValueError:
                return _reject(422, "reasoning_cursor_invalid")
        return {"progress": progress}

    @app.exception_handler(WorkflowDenied)
    async def denied(_request, _error):
        return _reject(403, "access_denied")

    @app.exception_handler(RequestValidationError)
    async def invalid(_request, _error):
        return _reject(422, "validation_error")

    return app


def main():
    app = create_preview(os.environ.get("SYNTHETIC_REASONING_TOKEN", ""))

    async def serve():
        asyncio.get_running_loop().add_signal_handler(
            signal.SIGUSR1,
            setattr,
            app.state,
            "admissions_enabled",
            False,
        )
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=8766,
                workers=1,
                proxy_headers=False,
                access_log=False,
                limit_concurrency=16,
                timeout_keep_alive=2,
            )
        )
        await server.serve()

    asyncio.run(serve())


if __name__ == "__main__":
    main()
