"""Isolated source-level probe for the pinned Travel/private-plan contract.

Requires Python 3.12, FastAPI, HTTPX, Pydantic and cryptography. The two repository apps are
not imported. This uses the existing PAS Travel adapter and runs selected
pinned definitions with explicit I/O substitutes for blocker reproduction.
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import base64
import hashlib
import json
import runpy
import sqlite3
import subprocess
import sys
import time
from collections.abc import Mapping
from contextlib import closing
from datetime import UTC, date, datetime
from functools import partial
from importlib import import_module
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Annotated, Literal
from uuid import UUID

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.datastructures import Headers

PAS = "f5f60fb6f871dad9d59071f2ebf91ecb8e1c69f1"
TRAVEL = "61a708b257cb9862bc415ce8a7151201489d3472"
CONTEXT_PATH = "/v1/integrations/personal-ai/context"
OWNER = "fabricated-owner"
FIELDS = ("trip_title", "trip_revision")
FIXTURES = (
    (UUID(int=1), UUID(int=11), "Fabricated trip A", 4),
    (UUID(int=2), UUID(int=22), "Fabricated trip B", 9),
)


def pinned_ast(repo, revision, path):
    code = subprocess.check_output(
        ["git", "-C", str(repo), "show", f"{revision}:{path}"], text=True
    )
    return ast.parse(code, filename=path)


def execute(name, nodes, **bindings):
    module = ModuleType(name)
    sys.modules[name] = module
    scope = vars(module)
    scope.update(bindings)
    future = ast.parse("from __future__ import annotations").body
    code = ast.fix_missing_locations(ast.Module(body=[*future, *nodes], type_ignores=[]))
    # Execute selected definitions from the explicitly supplied local checkout.
    exec(compile(code, name, "exec"), scope)  # noqa: S102
    return module


def definitions(tree, *names):
    found = {}
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            found[node.name] = node
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            found[node.targets[0].id] = node
    return [found[name] for name in names]


def travel_app(repo, db, reads):
    path = "backend/src/personal_travel"
    schema = execute(
        "pinned_travel_schema",
        definitions(
            pinned_ast(repo, TRAVEL, f"{path}/api/schemas/personal_ai_context.py"),
            "ContextEntityReference", "ContextSourceReference", "ContextPermissionDependency",
            "ContextFieldSensitivity", "ContextReadRequest", "ContextSelectionBinding",
            "ContextReadRecord", "ContextReadResponse",
        ),
        BaseModel=BaseModel, ConfigDict=ConfigDict, Field=Field, Literal=Literal,
        model_validator=model_validator,
    )
    domain = execute(
        "pinned_travel_domain_errors",
        definitions(
            pinned_ast(repo, TRAVEL, f"{path}/services/errors.py"), "DomainError", "not_found",
        ),
    )

    class SqliteTripLookup:
        """Substitutes only for the unavailable SQLAlchemy repository."""

        def __init__(self, session):
            self.session = session

        def get(self, *, owner_id, trip_id):
            reads.append((owner_id, trip_id))
            row = self.session.execute(
                "SELECT title, revision FROM trips WHERE id = ? AND owner = ?",
                (str(trip_id), owner_id),
            ).fetchone()
            if row:
                return SimpleNamespace(
                    id=trip_id, title=row[0], revision=row[1], days=[],
                    updated_at=datetime(2026, 11, 22, tzinfo=UTC), timezone="UTC",
                    start_date=date(2026, 11, 22), end_date=date(2026, 11, 23),
                )
            return None

    service = definitions(pinned_ast(repo, TRAVEL, f"{path}/services/trips.py"), "TripService")[0]
    service.body = definitions(service, "__init__", "get")
    domain_service = execute(
        "pinned_travel_trip_service", [service],
        SqlAlchemyTripRepository=SqliteTripLookup, not_found=domain.not_found,
    )
    router = APIRouter(prefix="/v1")

    async def fixture_session():
        return db

    async def fixture_settings():
        return SimpleNamespace(personal_ai_context_enabled=True)

    async def fixture_owner(request: Request) -> str:
        # Stand-in for Travel middleware. The real reverse ingress is not wired here.
        return request.headers.get("x-fixture-owner", OWNER)

    execute(
        "pinned_travel_context_route",
        definitions(
            pinned_ast(repo, TRAVEL, f"{path}/api/routes/personal_ai_context.py"),
            "ContextPayloadValue", "ContextPayload", "TRIP_FIELDS", "ENTITY_FIELDS",
            "_opaque", "_fingerprint", "_project", "_trip_permission", "_trip_export_permission",
            "_record", "_trip_overview", "_selected_trip", "_context_records", "_require_enabled",
            "read_personal_ai_context",
        ),
        **{key: value for key, value in vars(schema).items() if key.startswith("Context")},
        router=router, HTTPException=HTTPException, Request=Request, Depends=Depends,
        UUID=UUID, datetime=datetime, UTC=UTC, hashlib=hashlib, json=json, Literal=Literal,
        Mapping=Mapping, Annotated=Annotated, Settings=object,
        TripService=domain_service.TripService,
        SessionDependency=Annotated[object, Depends(fixture_session)],
        OwnerDependency=Annotated[str, Depends(fixture_owner)],
        get_settings=fixture_settings,
    )
    app = FastAPI()
    app.include_router(router)

    @app.exception_handler(domain.DomainError)
    async def domain_error(_request, error):
        return JSONResponse({"error": error.code}, status_code=error.status_code)

    return app


def plan_version_guard(repo):
    path = "backend/src/personal_ai/services/external_turns/application_plan.py"
    tree = pinned_ast(repo, PAS, path)
    service = definitions(tree, "ApplicationPlanService")[0]
    preview = definitions(service, "preview")[0]
    checks = [
        node for node in ast.walk(preview)
        if isinstance(node, ast.If) and "shared-source:application-plan:" in ast.unparse(node.test)
    ]
    assert len(checks) == 1
    guard = ast.parse("def check(snapshots): pass").body[0]
    guard.body = checks

    class GuardRejection(Exception):
        pass

    module = execute(
        "pinned_pas_version_guard",
        [*definitions(tree, "NO_AI"), guard],
        ContextPreparationError=GuardRejection,
    )
    return module.check, GuardRejection


async def private_parser_probe(repo):
    path = "backend/src/personal_ai"
    plan = execute(
        "pinned_pas_plan_intent",
        definitions(
            pinned_ast(repo, PAS, f"{path}/services/external_turns/application_plan.py"),
            "PlanChoice", "PlanContinuation",
        ),
        BaseModel=BaseModel, ConfigDict=ConfigDict, Field=Field, Literal=Literal, UUID=UUID,
    )
    route = execute(
        "pinned_pas_plan_route",
        definitions(pinned_ast(repo, PAS, f"{path}/api/private_application_plan.py"),
                    "_unique_object", "_intent"),
        json=json, HTTPException=HTTPException, PlanContinuation=plan.PlanContinuation,
    )

    async def parse(payload):
        async def receive():
            return {"type": "http.request", "body": json.dumps(payload).encode()}

        scope = {"type": "http", "headers": [(b"content-type", b"application/json")],
                 "path": "/preview", "query_string": b""}
        return await route._intent(Request(scope, receive), confirmed=False)

    body = {"content": "Summarize my trip.", "idempotency_key": str(UUID(int=31)),
            "choice": {"mode": "user_owned_plan"}}
    assert (await parse(body)).idempotency_key == UUID(int=31)
    for forged in (
        {"entity_refs": [{"entity_type": "trip", "entity_id": str(FIXTURES[1][1])}]},
        {"launch_context": {"workspace_id": str(FIXTURES[1][1])}},
        {"workspace_id": str(FIXTURES[1][1])},
    ):
        try:
            await parse(body | forged)
        except HTTPException as error:
            assert error.status_code == 422
        else:
            raise AssertionError("Private preview accepted a client-selected trip or launch field")
    print("The pinned private PAS parser rejected entity_refs, launch_context and workspace_id.")


async def reverse_ingress_probe(repo):
    path = "backend/src/personal_travel"
    relative = f"{path}/clients/task_wire.py"
    # The generated wire helper is dependency-independent. Only execute it after
    # comparing the checkout bytes with the pinned source.
    wire_path = repo / relative
    pinned = await asyncio.to_thread(
        subprocess.check_output, ["git", "-C", str(repo), "show", f"{TRAVEL}:{relative}"]
    )
    assert wire_path.read_bytes() == pinned
    wire = runpy.run_path(str(wire_path))
    auth = execute(
        "pinned_travel_task_ingress",
        definitions(pinned_ast(repo, TRAVEL, f"{path}/auth/task_ingress.py"),
                    "authenticate_task_ingress"),
        asyncio=asyncio, json=json, HTTPException=HTTPException, base64=base64, time=time,
        partial=partial, Ed25519PublicKey=Ed25519PublicKey,
    )
    private_key = Ed25519PrivateKey.generate()
    issuer, subject = "https://accounts.google.com", "fabricated-subject"
    signer, audience, key_id = "fabricated-pas", "https://travel.invalid", "fabricated-key"
    now = int(time.time())
    requested = trip_request(FIXTURES[0][1])
    assertion = wire["sign_delegated_user"](
        user_issuer=issuer, user_subject=subject, authenticated_at=now,
        private_key=private_key, issuer=signer, audience=audience, key_id=key_id,
        request_body=requested, now=now, lifetime_seconds=20,
    )
    options = {
        "public_key": private_key.public_key(), "issuer": signer, "audience": audience,
        "key_id": key_id, "allowed_user_issuers": frozenset({issuer}),
    }
    check = wire["verify_delegated_user"]
    assert check(assertion, requested, now=now, **options).subject == subject
    for body, at, bindings in (
        (requested, now + 20, options),
        (trip_request(FIXTURES[1][1]), now, options),
        (requested, now, options | {"audience": "https://unregistered.invalid"}),
    ):
        try:
            check(assertion, body, now=at, **bindings)
        except ValueError:
            continue
        raise AssertionError("Delegation verifier accepted expired or mismatched claims")

    calls = []

    def service_verifier(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Legacy purpose denial should precede service verification")

    async def receive():
        return {"type": "http.request", "body": json.dumps(requested).encode()}

    headers = Headers({
        "Authorization": "Bearer fabricated-service", "X-User-Delegation": assertion,
    })
    try:
        await auth.authenticate_task_ingress(
            headers, receive, SimpleNamespace(task_control=object()), None,
            SimpleNamespace(task_service_verifier=service_verifier), command_read=False,
        )
    except HTTPException as error:
        assert (error.status_code, error.detail) == (401, "task_identity_denied")
    else:
        raise AssertionError("Legacy Travel task ingress accepted private preview purpose")
    assert not calls
    print("Legacy Travel ingress denied a valid signed assertion before IAM.")
    print("Signed wire verifier denied expiration, changed trip body and wrong audience.")


def trip_request(trip, *, operation="current", fields=FIELDS):
    return {
        "schema_version": "travel-context-read-v2", "application_id": "travel",
        "workspace_id": None, "purpose": "personal_ai_context", "operation": operation,
        "entity_refs": [{"entity_type": "trip", "entity_id": str(trip),
                         "application_id": "travel", "workspace_id": None}],
        "fields": fields, "max_results": 1, "max_bytes": 4096,
    }


def travel_adapter(pas):
    # Only import the dependency-light PAS Travel adapter and typed context
    # contracts. Reject local edits to the imported production source trees.
    subprocess.check_call([
        "git", "-C", str(pas), "diff", "--exit-code", PAS, "--",
        "backend/src", "reference-apps/src",
    ])
    sys.path[:0] = [str(pas / "backend/src"), str(pas / "reference-apps/src")]
    module = import_module("personal_ai_reference_apps.context.travel")
    providers = import_module("personal_ai.context.providers")
    planner = import_module("personal_ai.context.planner")
    apps = import_module("personal_ai.applications.contracts")
    scope = module.RequestScope(
        owner_id=OWNER, application_id="travel", request_id="fabricated-request",
    )
    spec = module.TravelContextProvider.spec
    context = apps.ApplicationContextRequest(
        scope=scope,
        definition=apps.ApplicationDefinition(
            application_id="travel", memory_namespace="travel", display_name="Travel",
            context_provider_ids=(spec.provider_id,),
        ),
    )
    plan = planner.ContextPlanner(
        module.travel_context_planning_rules(), include_default_rules=False,
    )
    capabilities = {
        spec.provider_id: planner.ContextPlanningCapability(status="available", spec=spec),
    }
    intent = "Summarize my trip."
    empty = plan.plan(intent, context, capabilities, input_token_budget=4096)
    assert not empty.selections
    assert empty.decisions[0].reason == "entity_reference_required"
    trip_ref = module.ContextEntityReference(
        application_id="travel", entity_type="trip", entity_id=str(FIXTURES[0][1]),
    )
    selected, = plan.plan(
        intent, context, capabilities, input_token_budget=4096, candidate_entities=(trip_ref,),
    ).selections
    assert (selected.max_results, selected.max_bytes) == (4, 24_576)
    print("The existing planner omits Travel without a trip ref; with one it asks for 4/24,576B.")

    def normalize(raw, requested):
        request = module.TravelContextReadRequest.model_validate(requested)
        result = module.TravelContextReadResponse.model_validate_json(raw)

        class CapturedReply:
            def read(self, incoming, *, deadline):
                assert incoming == request
                assert deadline > time.monotonic()
                return result

        provider = module.TravelContextProvider(CapturedReply())
        selection = module.ContextSelection(
            provider_id=provider.spec.provider_id, operation=request.operation,
            fields=request.fields, entity_refs=request.entity_refs,
            max_results=request.max_results, max_bytes=request.max_bytes,
        )
        provider.validate_selection(selection, providers.ContextProviderInputs(scope=scope))
        item, = provider.fetch(selection, scope, deadline=time.monotonic() + 1)
        return item

    return normalize


async def probe(pas, travel):
    normalize = travel_adapter(pas)
    await private_parser_probe(pas)
    await reverse_ingress_probe(travel)
    reads = []
    with closing(sqlite3.connect(":memory:")) as db:
        db.execute("CREATE TABLE trips(id TEXT PRIMARY KEY, owner TEXT, title TEXT, revision INT)")
        db.executemany(
            "INSERT INTO trips VALUES (?, ?, ?, ?)",
            [(str(trip), OWNER, title, version) for _, trip, title, version in FIXTURES],
        )
        app = travel_app(travel, db, reads)
        guard, rejection = plan_version_guard(pas)
        # This marker isolates the source guard. No PAS memory repository was opened.
        memory = SimpleNamespace(
            provider_id="ai_memory", source_version="application-plan-memory:v1",
        )
        observed = []
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://travel.invalid"
        ) as client:
            for index in (0, 1, 0, 1):
                conversation, trip, title, version = FIXTURES[index]
                response = await client.post(CONTEXT_PATH, json=trip_request(trip))
                assert response.status_code == 200, response.text
                assert len(response.content) <= 4096
                record, = response.json()["items"]
                assert record["entity_id"] == str(trip)
                assert record["payload"] == {"trip_title": title, "trip_revision": version}
                assert record["source_version"] == str(version)
                assert record["observed_at"] == "2026-11-22T00:00:00+00:00"
                assert record["expires_at"] is None
                assert record["sensitivity"] == "sensitive"
                assert {item["field"] for item in record["field_sensitivity"]} == set(FIELDS)
                assert all(
                    field["sensitivity"] == "sensitive" for field in record["field_sensitivity"]
                )
                source, = record["source_refs"]
                opaque_id = hashlib.sha256(f"trip\0{trip}".encode()).hexdigest()
                assert source["reference_id"] == f"travel-record:{opaque_id}"
                assert record["source_id"] == f"travel:{opaque_id}"
                payload = json.dumps(record["payload"], sort_keys=True, separators=(",", ":"))
                assert source["fingerprint"] == hashlib.sha256(payload.encode()).hexdigest()
                dependency, = record["permission_dependencies"]
                assert dependency["permission_id"] == f"travel_context_read:{trip}"
                assert dependency["version"] == str(version)
                item = normalize(response.content, trip_request(trip))
                assert item.payload.model_dump(exclude_none=True) == record["payload"]
                assert item.source_version == record["source_version"]
                assert item.source_id == record["source_id"]
                assert item.observed_at.isoformat() == record["observed_at"]
                assert item.expires_at is record["expires_at"]
                assert item.sensitivity == record["sensitivity"]
                assert not item.entity_refs
                source_snapshot = item.authority_snapshot()
                assert source_snapshot.permission_dependencies[0].version == str(version)
                assert source_snapshot.source_refs[0].fingerprint == source["fingerprint"]
                try:
                    guard((memory, source_snapshot))
                except rejection as error:
                    assert str(error) == "context_no_ai_route"
                else:
                    raise AssertionError("PAS accepted an unchanged v2 source version")
                observed.append((conversation.int, trip.int, version))

            _, other_trip, other_title, _ = FIXTURES[1]
            # There is no conversation in the public wire. The same owner can select B
            # even if the caller has associated CA with A outside this route.
            conflicting = await client.post(CONTEXT_PATH, json=trip_request(other_trip))
            assert conflicting.status_code == 200
            assert conflicting.json()["items"][0]["payload"]["trip_title"] == other_title
            foreign_owner = await client.post(
                CONTEXT_PATH, json=trip_request(other_trip),
                headers={"x-fixture-owner": "fabricated-other-owner"},
            )
            assert foreign_owner.status_code == 404 and other_title not in foreign_owner.text
            verify_body = trip_request(other_trip, operation="verify", fields=("trip_revision",))
            db.execute("UPDATE trips SET revision = 10 WHERE id = ?", (str(other_trip),))
            stale = await client.post(CONTEXT_PATH, json=verify_body)
            assert stale.status_code == 200
            assert stale.json()["items"][0]["source_version"] == "10"
            db.execute("UPDATE trips SET owner = 'other-owner' WHERE id = ?", (str(other_trip),))
            revoked = await client.post(CONTEXT_PATH, json=verify_body)
            assert revoked.status_code == 404 and other_title not in revoked.text
            assert len(reads) == 8

    print(f"PAS {PAS}; Travel {TRAVEL}")
    print(f"Interleaved fixture reads (conversation label, trip, revision): {observed}")
    print("Unchanged PAS source-version guard denied each projected v2 revision.")
    print("The existing Travel read accepted the same-owner alternate selector.")
    print("The revised projection reported version 10; the changed owner was denied.")
    print(f"Trip ACL stand-in queries: {len(reads)}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--travel", type=Path, required=True, help="Travel checkout with the pinned commit",
    )
    args = parser.parse_args()

    network_attempts = []

    def deny_network(event, _args):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg"}:
            network_attempts.append(event)
            raise AssertionError(f"Unexpected network operation: {event}")

    if not __debug__:
        parser.error("Run without Python optimization so assertions are evaluated.")
    sys.addaudithook(deny_network)
    asyncio.run(probe(Path(__file__).resolve().parents[2], args.travel))
    if network_attempts:
        raise SystemExit(f"Blocked network attempts: {network_attempts}")
    print("Audited outbound socket attempts: 0; runtime/physical provider paths absent.")
