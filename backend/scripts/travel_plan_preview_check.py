"""Run a paired private preview with explicitly reduced, offline app compositions."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import UUID

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI

from personal_ai.auth.application_clients import client_binding_namespace
from personal_ai.auth.scope import ApplicationScope
from personal_ai.context import ContextAssembler
from personal_ai.context.adapters import MemoryContextProviderFactory
from personal_ai.context.authority import source_snapshot_authority_complete, source_snapshots_current
from personal_ai.context.contracts import fingerprint
from personal_ai.context.history import conversation_context_messages
from personal_ai.context.providers import ContextProviderCoordinator
from personal_ai.context.runtime import ContextPermissionRevalidatorRegistry, compose_context_runtime
from personal_ai.contracts.context_references import ApplicationPlanSourceGrant, ContextSourceSnapshot
from personal_ai.entities import Conversation, Message
from personal_ai.llm.external import CHATGPT_PLAN_PROFILE
from personal_ai_reference_apps.context.travel_plan import CURRENT_FIELDS, TravelPlanSource
from personal_ai_reference_apps.context.travel_plan import TravelPlanSourceClient

from travel_plan_contract_probe import travel_app
from travel_plan_paired_diagnostics import http_probe, source_with_overrides

TRIPS = (UUID(int=201), UUID(int=202))
TITLES = ("Fabricated trip A", "Fabricated trip B · Ålesund")
REVISIONS = (0, 9)
MEMORY = "I prefer concise itinerary summaries."


def canonical_memory_modules():
    """Replace unused cloud dependencies of the in-memory canonical memory stack."""
    try:
        import google.cloud.pubsub_v1  # noqa: F401
    except ModuleNotFoundError:
        names = ("google", "google.api_core", "google.api_core.exceptions",
                 "google.cloud", "google.cloud.pubsub_v1")
        stubs = {name: ModuleType(name) for name in names}
        stubs["google.api_core.exceptions"].GoogleAPICallError = type("UnusedRPCError", (Exception,), {})
        stubs["google.api_core.exceptions"].RetryError = type("UnusedRetryError", (Exception,), {})
        stubs["google.cloud"].pubsub_v1 = stubs["google.cloud.pubsub_v1"]
        sys.modules.update(stubs)


def build_memory(chat, service, settings, principal):
    canonical_memory_modules()
    from personal_ai.memory.contracts import Memory, MemoryCandidate, identity, normalize
    from personal_ai.memory.dependencies import MemoryPermissionRevalidator
    from personal_ai.memory.lifecycle.repositories import InMemoryMemoryLifecycleRepository
    from personal_ai.memory.repositories import InMemoryMemoryRepository
    from personal_ai.services.external_turns.plan_memory import ApplicationPlanMemory, MemoryDisclosure

    now = datetime.now(UTC)
    conversations, messages = chat._conversations, chat._messages
    memories = InMemoryMemoryRepository(messages)
    lifecycle = InMemoryMemoryLifecycleRepository(memories, messages)
    origin = ApplicationScope(application_id="travel", workspace_id=None)
    fields = {"owner_id": principal.owner_id, **origin.model_dump()}
    conversations.create(Conversation(
        id=UUID(int=21), title="Fabricated memory origin", created_at=now, updated_at=now, **fields,
    ))
    user = messages.create(Message(
        id=UUID(int=22), conversation_id=UUID(int=21), role="user",
        content=MEMORY, status="completed", created_at=now, **fields,
    ))
    assistant = messages.create(Message(
        id=UUID(int=23), conversation_id=UUID(int=21), role="assistant",
        parent_message_id=user.id, content="Recorded.", status="completed", created_at=now, **fields,
    ))
    candidate = MemoryCandidate(
        memory_type="preference", content=MEMORY, source_message_ids=(user.id,), confidence=1,
        effective_at=now, rationale_code="user_preference",
    )
    source = fingerprint([user])
    dimensions = settings.memory_embedding_dimensions
    record, _ = memories.create(Memory(
        id=identity(principal.owner_id, source, candidate, application_id="travel"),
        normalized_content=normalize(MEMORY), source_fingerprint=source,
        source_turn_id=assistant.id, source_conversation_id=UUID(int=21), observed_at=now,
        effective_at=now, created_at=now, embedding=(1.0,) + (0.0,) * (dimensions - 1),
        embedding_model=settings.memory_embedding_model, embedding_dimensions=dimensions,
        **candidate.model_dump(exclude={"effective_at"}), **fields,
    ))
    disclosures = {}
    reader = MemoryPermissionRevalidator(settings, memories, messages, lifecycle)
    memory = ApplicationPlanMemory(
        reader, current_scope=lambda: service.current_target().scope,
        current_disclosures=lambda scope: disclosures.get(scope, ()),
        source_rights=lambda scope, source_scope: scope.owner_id == principal.owner_id and source_scope == origin,
    )
    return memory, record, disclosures, MemoryDisclosure


def build_travel_source(db, travel_checkout, principal, signing_key, calls):
    from personal_travel.api.schemas.private_plan import (
        PRIVATE_PLAN_SOURCE_MAX_BYTES, PRIVATE_PLAN_SOURCE_PATH, PrivatePlanSourceRequest,
    )
    from personal_travel.auth.private_plan import PrivatePlanTrust, authenticate_private_plan_source
    from personal_travel.services.errors import DomainError, not_found

    trust = PrivatePlanTrust(
        target_id="synthetic-pas", client_namespace=client_binding_namespace(principal, "travel"),
        service_audience="https://travel.invalid", service_account="pas-service@example.invalid",
        delegation_issuer="synthetic-pas-delegation", delegation_key_id="synthetic-key",
        delegation_public_key=signing_key.public_key(),
    )
    service_key = Ed25519PrivateKey.generate()
    service_token = jwt.encode(
        {"iss": "synthetic-service", "aud": trust.service_audience,
         "sub": trust.service_account, "exp": principal.expires_at},
        service_key, algorithm="EdDSA",
    )

    def verify_service(token, *, audience, expected_service_account):
        try:
            claims = jwt.decode(token, service_key.public_key(), algorithms=["EdDSA"],
                                audience=audience, issuer="synthetic-service")
        except jwt.PyJWTError as exc:
            raise ValueError("invalid synthetic service bearer") from exc
        if claims["sub"] != expected_service_account:
            raise ValueError("wrong service account")

    db.executescript("""
        CREATE TABLE trips(id PRIMARY KEY, owner, title, revision);
        CREATE TABLE bindings(conversation PRIMARY KEY, trip, owner, issuer, subject, target,
                              client, lane);
    """)
    for n, trip, title, revision in zip((101, 102), TRIPS, TITLES, REVISIONS, strict=True):
        db.execute("INSERT INTO trips VALUES (?,?,?,?)", (str(trip), principal.owner_id, title, revision))
        db.execute("INSERT INTO bindings VALUES (?,?,?,?,?,?,?,'user_owned_plan')", (
            str(UUID(int=n)), str(trip), principal.owner_id, principal.issuer, principal.subject,
            trust.target_id, trust.client_namespace,
        ))
    db.commit()
    travel_app(travel_checkout, db, [])
    projector = sys.modules["pinned_travel_context_route"]

    def active_identity(_session, *, issuer, subject):
        if (issuer, subject) != (principal.issuer, principal.subject):
            raise not_found("private plan")
        return principal

    def resolve_trip(session, *, identity, trust, conversation_id):
        result = session.execute("""
            SELECT t.id, t.title, t.revision FROM bindings b
            JOIN trips t ON t.id=b.trip AND t.owner=b.owner
            WHERE b.conversation=? AND b.owner=? AND b.issuer=? AND b.subject=?
            AND b.target=? AND b.client=? AND b.lane='user_owned_plan'
        """, (str(conversation_id), identity.owner_id, identity.issuer, identity.subject,
              trust.target_id, trust.client_namespace)).fetchone()
        if result is None:
            raise not_found("private plan")
        return None, SimpleNamespace(
            id=UUID(result[0]), title=result[1], revision=result[2], days=[], updated_at=datetime(2026, 11, 22, tzinfo=UTC),
            timezone="UTC", start_date=date(2026, 11, 22), end_date=date(2026, 11, 23),
        )

    from fastapi import HTTPException, Request, Response
    from starlette.requests import ClientDisconnect

    async def inline_worker(function, *, abandon_on_cancel):
        return function()

    route = source_with_overrides(
        travel_checkout / "backend/src/personal_travel/api/routes/private_plan.py",
        {
            "FastAPI": FastAPI, "Request": Request, "Response": Response, "HTTPException": HTTPException,
            "ClientDisconnect": ClientDisconnect, "run_sync": inline_worker,
            "_context_records": projector._context_records, "DomainError": DomainError,
            "PrivatePlanSourceRequest": PrivatePlanSourceRequest,
            "PRIVATE_PLAN_SOURCE_MAX_BYTES": PRIVATE_PLAN_SOURCE_MAX_BYTES,
            "PRIVATE_PLAN_SOURCE_PATH": PRIVATE_PLAN_SOURCE_PATH,
            "ContextEntityReference": projector.ContextEntityReference,
            "ContextReadRequest": projector.ContextReadRequest, "ContextReadResponse": projector.ContextReadResponse,
            "authenticate_private_plan_source": authenticate_private_plan_source,
            "active_plan_identity": active_identity, "resolve_plan_trip": resolve_trip,
            "SQLAlchemyError": type("UnusedSQLError", (Exception,), {}),
            "IdentityProviderUnavailable": type("UnusedIdentityError", (Exception,), {}),
        },
        {"anyio.to_thread", "fastapi", "sqlalchemy.exc", "sqlalchemy.orm", "starlette.requests",
         "personal_travel.api.routes.personal_ai_context", "personal_travel.api.schemas.personal_ai_context",
         "personal_travel.api.schemas.private_plan", "personal_travel.auth.google_oidc",
         "personal_travel.auth.private_plan", "personal_travel.config",
         "personal_travel.services.errors", "personal_travel.services.private_plan"},
        delayed_annotations=True,
    )
    app = FastAPI()
    route["mount_private_plan_source"](
        app, settings=SimpleNamespace(deployment_mode="local", personal_ai_plan_enabled=True),
        trust=trust, sessions=lambda: db, verify_service=verify_service,
    )

    def transport(request):
        async def send():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client:
                return await client.send(request)

        body = json.loads(request.content)
        assert request.url.path == PRIVATE_PLAN_SOURCE_PATH
        assert body.keys() == ({"schema_version", "purpose", "destination_application_id", "workspace_id",
                               "lane", "target_id", "client_namespace", "conversation_id", "operation"}
                              | ({"expected_source_version"} if body["operation"] == "verify" else set()))
        with ThreadPoolExecutor(max_workers=1) as executor:
            result = executor.submit(asyncio.run, send()).result(timeout=3)
        calls.append((body, result))
        return httpx.Response(result.status_code, headers=result.headers, content=result.content)

    return trust.target_id, TravelPlanSourceClient(
        base_url=trust.service_audience, audience=trust.service_audience,
        issuer=trust.delegation_issuer, key_id=trust.delegation_key_id, signing_key=signing_key,
        service_token=lambda **_: service_token, transport=httpx.MockTransport(transport),
    )


def configured_pair(db, travel_checkout):
    def configure(principal, service, baseline, chat):
        calls, released, grants = [], [], {}
        target_id, client = build_travel_source(db, travel_checkout, principal, Ed25519PrivateKey.generate(), calls)

        def grant_reader(purpose):
            store = grants.setdefault(purpose, {})
            return lambda binding, **_: store.get(binding.conversation_id)

        purposes = ("source-read", "runtime-handoff", "inference-disclosure")
        source = TravelPlanSource(client, *(grant_reader(purpose) for purpose in purposes))
        runtime = compose_context_runtime(source.contribution())
        target = service.target_for_request(None, None)
        settings = baseline.settings.model_copy(update={
            "max_context_tokens": 10240, "memory_max_context_tokens": 1536,
        })
        memory, record, disclosures, memory_grant_type = build_memory(chat, service, settings, principal)
        target = replace(
            target, profile=CHATGPT_PLAN_PROFILE, preview_source=source.selection(target_id, max_tokens=1536),
            serialize_payload=lambda package: package.canonical(),
        )
        service.target_for_request = lambda *_: target
        service.memory = memory
        expiry = datetime.now(UTC) + timedelta(minutes=2)
        origin = ApplicationScope(application_id="travel")
        disclosures[target.scope] = tuple(
            memory_grant_type(target.scope, origin, record.id, recipient, 1, expiry)
            for recipient in (target.scope.local_recipient, target.scope.model_recipient)
        )
        coordinator = ContextProviderCoordinator(
            {**runtime.provider_factories, "ai_memory": MemoryContextProviderFactory(settings)},
            feature_flags={"travel_context_enabled": True, "memory_enabled": True},
        )
        permissions = ContextPermissionRevalidatorRegistry((*runtime.permission_revalidators, memory))
        assembler = ContextAssembler(
            settings, baseline.counter, context_provider_coordinator=coordinator,
            context_planner=baseline.context_planner, permission_revalidator=permissions,
        )
        chat._context = assembler

        for n in (101, 102):
            selected = target.preview_binding(principal, UUID(int=n))
            for purpose, recipient in (
                ("source-read", selected.target_id),
                ("runtime-handoff", selected.runtime_recipient),
                ("inference-disclosure", selected.model_recipient),
            ):
                grants[purpose][selected.conversation_id] = ApplicationPlanSourceGrant(
                    binding=selected, purpose=purpose, recipient=recipient,
                    fields=CURRENT_FIELDS, version="version-1", expires_at=expiry,
                )

        def reject_delivery(*_args):
            released.append(True)
            raise AssertionError("unexpected runtime delivery")

        target.runtime.deliver = reject_delivery

        async def verify_previews(preview):
            for index in (0, 1, 0, 1):
                result = await preview(101 + index)
                assert result.status_code == 200, (result.status_code, result.text)
                assert result.headers["cache-control"] == "no-store"
                assert TITLES[0] not in result.text and TITLES[1] not in result.text
                assert MEMORY not in result.text and result.json()["selected_context"] == [
                    {"category": "conversation_history", "turns": 0},
                    {"category": "ai_memory", "fields": ["content"]},
                    {"category": "domain_current", "fields": ["trip_revision", "trip_title"]},
                ], result.json()
                prepared = next(p for p in service._previews.values()
                                if p.package.conversation_id == UUID(int=101 + index))
                serialized = prepared.package.canonical().decode()
                assert TITLES[index] in serialized and TITLES[1 - index] not in serialized
                assert MEMORY in serialized
                snapshot = next(s for s in prepared.snapshots if s.provider_id == source.spec.provider_id)
                restored = ContextSourceSnapshot.model_validate_json(snapshot.model_dump_json())
                assert restored == snapshot and source_snapshot_authority_complete(restored)
                for change in ({"application_plan_authority": None}, {"content_fingerprint": "0" * 64}):
                    assert not source_snapshot_authority_complete(restored.model_copy(update=change))
                assert not source_snapshots_current((restored,), permissions, now=datetime.now(UTC))
                assert restored.application_plan_authority.binding.conversation_id == UUID(int=101 + index)
                assert restored.source_version == str(REVISIONS[index]) and restored.expires_at is None
                body, travel_response = [call for call in calls if call[0]["operation"] == "current"][-1]
                raw = travel_response.json()["items"][0]
                assert body["conversation_id"] == str(UUID(int=101 + index))
                assert raw["entity_id"] == str(TRIPS[index])
                assert restored.source_id == raw["source_id"]
                assert restored.content_fingerprint == raw["source_refs"][0]["fingerprint"]
                assert restored.permission_dependencies[0].version == raw["permission_dependencies"][0]["version"]
                assert restored.application_plan_authority.observed_at == datetime.fromisoformat(raw["observed_at"])
                assert restored.application_plan_authority.source_sensitivity == raw["sensitivity"]
                assert dict(restored.application_plan_authority.field_sensitivities) == {
                    field["field"]: field["sensitivity"] for field in raw["field_sensitivity"]
                }

            currents = [b["conversation_id"] for b, _ in calls if b["operation"] == "current"]
            assert currents == [str(UUID(int=n)) for n in (101, 102, 101, 102)]
            assert all(r.status_code == 200 and r.headers["cache-control"] == "no-store" for _, r in calls)
            verifies = [(body, result) for body, result in calls if body["operation"] == "verify"]
            assert len(verifies) == 16
            assert all(result.json()["items"][0]["payload"] == {
                "trip_revision": int(body["expected_source_version"]),
            } for body, result in verifies)

            # The source-recipient edges are independent. Removal of any edge denies before Travel.
            conversation_a, conversation_b = UUID(int=101), UUID(int=102)
            for purpose in purposes:
                saved = grants[purpose].pop(conversation_a)
                before = len(calls)
                assert (await preview(101)).status_code == 422 and len(calls) == before
                grants[purpose][conversation_a] = grants[purpose][conversation_b]
                assert (await preview(101)).status_code == 422 and len(calls) == before
                grants[purpose][conversation_a] = saved

            saved_memory = disclosures[target.scope]
            disclosures[target.scope] = saved_memory[:1]
            before = len(calls)
            assert (await preview(101)).status_code == 422 and len(calls) == before
            disclosures[target.scope] = saved_memory

            original_transport = client._transport.handler

            def mutate_current(request):
                response = original_transport(request)
                return httpx.Response(200, headers=response.headers, json=response.json() | {
                    "items": [response.json()["items"][0] | {"source_version": "wrong"}],
                })

            client._transport.handler = mutate_current
            assert (await preview(101)).status_code == 503
            client._transport.handler = original_transport

            def change_revision(request):
                if json.loads(request.content)["operation"] == "verify":
                    db.execute("UPDATE trips SET revision=1 WHERE id=?", (str(TRIPS[0]),))
                    db.commit()
                return original_transport(request)

            client._transport.handler = change_revision
            assert (await preview(101)).status_code == 422
            assert calls[-1][0]["operation"] == "verify" and calls[-1][1].status_code == 409
            db.execute("UPDATE trips SET revision=0 WHERE id=?", (str(TRIPS[0]),))
            db.commit()

            # Existing source disappears after current but before verify.
            def revoke_on_verify(request):
                if json.loads(request.content)["operation"] == "verify":
                    db.execute("UPDATE trips SET owner='revoked' WHERE id=?", (str(TRIPS[0]),))
                    db.commit()
                return original_transport(request)
            source.client._transport.handler = revoke_on_verify
            assert (await preview(101)).status_code == 422
            assert calls[-1][0]["operation"] == "verify" and calls[-1][1].status_code == 404
            allowed = await preview(102)
            assert allowed.status_code == 200

            count = len(calls)
            assert (await preview(999)).status_code == 404 and len(calls) == count
            continuation = await preview(
                102, action="continue", extra={"choice": {
                    "mode": "user_owned_plan", "confirmation": allowed.json()["confirmation"],
                }},
            )
            assert continuation.status_code == 422 and len(calls) == count and not released

            saved = next(p for p in service._previews.values() if p.package.conversation_id == conversation_b)
            snapshot = next(s for s in saved.snapshots if s.provider_id == source.spec.provider_id)
            user = Message(id=UUID(int=88), role="user", content="Old user", status="completed",
                           conversation_id=UUID(int=102), application_id="travel",
                           owner_id=principal.owner_id, created_at=datetime.now(UTC))
            answer = user.model_copy(update={
                "id": UUID(int=89), "role": type(user.role).ASSISTANT, "parent_message_id": user.id,
                "prepared_source_snapshots": (snapshot,), "content": "Old source data",
            })
            reuse = chat._application_context.definition.context_policy.sidecar.manual_import_reuse
            assert not conversation_context_messages((user, answer), manual_import_reuse=reuse)
            assert not chat._history_for_new_recipient((user, answer))
            print("Paired reduced preview passed A/B/A/B, recipient and memory denials,"
                  " malformed revision, stale and revoked Travel authority, and no continuation.")

        return assembler, verify_previews

    return configure


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("Run without Python optimization so assertions are evaluated.")
    attempts = []

    def deny_network(event, _):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg"}:
            attempts.append(event)
            raise AssertionError(event)

    sys.addaudithook(deny_network)
    checkout = Path(sys.argv[1]).resolve()
    with closing(sqlite3.connect(":memory:", check_same_thread=False)) as db:
        asyncio.run(http_probe(configured_pair(db, checkout)))
    assert not attempts
    print("Audited outbound socket attempts: 0.")
