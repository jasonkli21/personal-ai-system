"""Run reduced, offline PAS preview and Travel reverse-authentication diagnostics.

This script mounts PAS route and middleware source with explicit test substitutes
for unavailable dependencies. It does not publish a preview or establish paired
conformance. See the dated paired preview evidence for scope and reproduction.
"""

import __future__

import ast
import asyncio
import json
import sys
import time
from contextlib import nullcontext
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from uuid import UUID

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from personal_ai_reference_apps.applications import _reference_metadata
from personal_ai_reference_apps.context.travel import (
    TRAVEL_CONTEXT_PROVIDER_ID,
    TravelContextProvider,
    travel_context_planning_rules,
)
from personal_ai_reference_apps.domains.travel.module import TravelModule

from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.applications.registry import ApplicationRegistry
from personal_ai.auth.application_clients import bind_client_authority, client_binding_namespace
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.dispatch_grants import ApplicationPlanScope
from personal_ai.auth.scope import RequestScope, bind_request_scope
from personal_ai.context import ContextAssembler
from personal_ai.context.adapters import MemoryContextProviderFactory
from personal_ai.context.contracts import ContextError
from personal_ai.context.planner import ContextPlanner, ContextPlanningRule
from personal_ai.context.providers import ContextPreparationError, ContextProviderCoordinator
from personal_ai.context.tokens import EstimatedTokenCounter
from personal_ai.entities import Conversation
from personal_ai.local_bridge.application_plan import PairedApplicationRuntime
from personal_ai.services.chat.service import ChatTurnService
from personal_ai.services.external_turns.application_plan import (
    ApplicationPlanService,
    PlanContinuation,
    PlanTarget,
)
from personal_ai.settings import Settings, get_settings
from personal_ai.storage.errors import ResourceNotFoundError
from personal_ai.storage.fake import InMemoryConversationRepository, InMemoryMessageRepository


def run():
    def unexpected(*_args, **_kwargs):
        raise AssertionError("read/release reached")
    now = int(time.time())
    principal = AuthenticatedPrincipal(
        "https://accounts.google.com", "fabricated-subject", "fabricated-owner",
        "fabricated@example.invalid", now, True, authenticated_at=now,
        audience="synthetic-travel-aud", authorized_party="synthetic-travel-azp",
        expires_at=now + 300,
    )
    client = client_binding_namespace(principal, "travel")
    scope = RequestScope(
        owner_id=principal.owner_id, application_id="travel", workspace_id=None,
        request_id="fabricated-preview", acting_user_id=f"{principal.issuer}|{principal.subject}",
    )
    bind_request_scope(scope)
    bind_client_authority(lambda: None, client)
    definitions, capabilities = _reference_metadata()
    definition = next(d for d in definitions if d.application_id == "travel")
    declared = {*definition.context_provider_ids, *definition.tool_ids}
    registry = ApplicationRegistry((definition,), (c for c in capabilities if c.capability_id in declared), comparison_modules={"travel": TravelModule()})
    registered = registry.registration("travel")
    context = ApplicationContextRequest(
        definition=registered.definition, scope=scope,
        context_provider_capabilities=registered.context_providers,
    )
    settings = Settings(_env_file=None, app_environment="test", ai_provider="fake", ai_model="fabricated", memory_enabled=True)
    coordinator = ContextProviderCoordinator({
        TRAVEL_CONTEXT_PROVIDER_ID: TravelContextProvider(SimpleNamespace(read=unexpected)),
        "ai_memory": MemoryContextProviderFactory(settings),
    }, feature_flags={"travel_context_enabled": True, "memory_enabled": True})
    planner = ContextPlanner((
        *travel_context_planning_rules(),
        ContextPlanningRule(
            rule_id="application-plan-memory:v1", category="personal_recall",
            phrases=("saved preference",), provider_id="ai_memory", operation="search",
            fields=("content",), max_results=1, max_bytes=4096, max_tokens=1536,
            required=True, explanation="Read a consented memory.",
        ),
    ), max_total_tokens=3072)
    assembler = ContextAssembler(
        settings, EstimatedTokenCounter(),
        context_provider_coordinator=coordinator, context_planner=planner,
    )
    conversations = InMemoryConversationRepository()
    messages = InMemoryMessageRepository(conversations)
    for cid in (UUID(int=101), UUID(int=102)):
        conversations.create(Conversation(
            id=cid, owner_id=scope.owner_id, external_client_namespace=client,
            application_id="travel", workspace_id=None, title="Fabricated conversation",
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
    target_scope = ApplicationPlanScope(
        application_id="travel", workspace_id=None, owner_id=scope.owner_id,
        actor_id=scope.acting_user_id, client_namespace=client, runtime_id=UUID(int=10),
        registration_binding="a" * 64, local_recipient=f"local:{UUID(int=10)}",
        model_recipient="openai-responses:" + "a" * 64,
    )
    runtime = object.__new__(PairedApplicationRuntime)
    target = PlanTarget(
        target_scope, runtime, UUID(int=11), UUID(int=12), 1, None, "chatgpt",
        unexpected, "fabricated-model", TRAVEL_CONTEXT_PROVIDER_ID,
    )
    service = ApplicationPlanService(
        signer=None, target_for_request=lambda *_: target,
        memory=SimpleNamespace(retrieve=unexpected),
        attempts=SimpleNamespace(recovery_current=lambda: True),
    )
    chat = ChatTurnService(
        conversations, messages, None, owner_id=scope.owner_id, model="fabricated-model",
        application_context=context, context_assembler=assembler,
    )
    prompt = "Summarize my trip using my saved preference."
    plan = assembler.plan_context(prompt, context)
    print([(r.provider_id, r.reason) for r in plan.decisions])
    assert any(r.reason == "entity_reference_required" for r in plan.decisions)
    results = []
    for n in (101, 102, 101, 102, 999):
        incoming = PlanContinuation(
            content=prompt, idempotency_key=UUID(int=201),
            choice={"mode": "user_owned_plan"},
        )
        try:
            service.preview(chat, assembler, UUID(int=n), incoming)
        except (ContextPreparationError, ResourceNotFoundError) as exc:
            results.append((n, type(exc).__name__, str(exc)))
        else:
            raise AssertionError("Unexpected preview")
    print(results)
    assert all(row[1:] == ("ContextPreparationError", "context_no_ai_route") for row in results[:4])
    assert results[-1][1] == "ResourceNotFoundError"
    assert not service._previews and not service._reservations
    return principal, registry, service, assembler, chat


def source_with_overrides(path, overrides, removed_imports, *, delayed_annotations=False):
    path = Path(__file__).resolve().parents[1] / "src/personal_ai" / path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    tree.body = [
        statement for statement in tree.body
        if not isinstance(statement, ast.ImportFrom) or statement.module not in removed_imports
    ]
    tree.body = [statement for statement in tree.body if not (
        isinstance(statement, ast.Import) and any(
            alias.name in overrides for alias in statement.names
        )
    )]
    namespace = {"__name__": path.stem, **overrides}
    flags = __future__.annotations.compiler_flag if delayed_annotations else 0
    # Execute selected definitions from the explicitly supplied local checkout.
    exec(compile(tree, str(path), "exec", flags=flags), namespace)  # noqa: S102
    return namespace


async def http_probe(configure=None):
    principal, registry, service, assembler, chat = run()
    if configure is not None:
        assembler, verify_previews = configure(principal, service, assembler, chat)
    token_key = Ed25519PrivateKey.generate()

    class InvalidToken(ValueError):
        pass

    def verify_fabricated_bearer(token, settings):
        try:
            claims = jwt.decode(
                token, token_key.public_key(), algorithms=["EdDSA"],
                issuer=principal.issuer, audience=principal.audience,
                options={"require": ["iss", "sub", "azp", "aud", "exp", "iat", "auth_time"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidToken from exc
        if claims["sub"] != principal.subject:
            raise InvalidToken
        return replace(principal, authorized_party=claims["azp"])

    def unexpected(*_args, **_kwargs):
        raise AssertionError("continue/release reached")

    async def inline_worker(function, *args, **kwargs):
        await asyncio.sleep(0)
        return function(*args, **kwargs)

    async def load_chat():
        return chat

    async def load_assembler():
        return assembler

    route = source_with_overrides(
        "api/private_application_plan.py",
        {
            "deps": SimpleNamespace(get_chat_turn_service=load_chat),
            "sync_call": inline_worker,
            "_request_id": unexpected, "_sse_response": unexpected,
        },
        {"personal_ai.api", "personal_ai.api.routes", "personal_ai.storage.async_io"},
    )
    middleware = source_with_overrides(
        "auth/middleware.py",
        {
            "anyio": SimpleNamespace(to_thread=SimpleNamespace(run_sync=inline_worker)),
            "principal_from_google_token": verify_fabricated_bearer,
            "InvalidIdentityToken": InvalidToken,
            "IdentityProviderUnavailable": type("Unavailable", (RuntimeError,), {}),
        },
        {"personal_ai.auth.verification"},
    )
    app = FastAPI()
    app.state.isolate_external_conversations = True
    app.state.application_registry = registry
    app.state.external_conversation_access = (
        lambda scope, client: (scope.owner_id, scope.workspace_id, client) ==
        (principal.owner_id, None, client_binding_namespace(principal, "travel"))
    )
    app.add_middleware(middleware["AuthenticationMiddleware"])
    route["mount_application_plan"](
        app, service=service, assembler_dependency=load_assembler,
        preview_recipient_scope=lambda _: nullcontext(),
    )

    @app.exception_handler(ContextPreparationError)
    async def preparation_denied(_request, exc):
        return JSONResponse({"code": exc.code}, status_code=422 if exc.code.startswith("context_") else 503)

    @app.exception_handler(ContextError)
    async def assembly_denied(_request, exc):
        return JSONResponse({"code": exc.code}, status_code=422)

    @app.exception_handler(ResourceNotFoundError)
    async def conversation_denied(_request, _exc):
        return JSONResponse({"code": "not_found"}, status_code=404)

    def bearer(azp, audience=principal.audience):
        return jwt.encode(
            {"iss": principal.issuer, "sub": principal.subject, "aud": audience, "azp": azp,
             "iat": principal.issued_at, "auth_time": principal.authenticated_at,
             "exp": principal.expires_at},
            token_key, algorithm="EdDSA",
        )

    with TemporaryDirectory() as temporary:
        policy = Path(temporary) / "clients.json"
        policy.write_text(json.dumps({
            "schema_version": "application-client-policy-v1",
            "bindings": [{
                "audience": principal.audience, "authorized_party": principal.authorized_party,
                "application_id": "travel", "expires_at": principal.expires_at,
            }],
        }), encoding="utf-8")
        settings = Settings(
            _env_file=None, app_environment="test", ai_provider="fake", ai_model="fabricated",
            auth_mode="google_oidc", auth_required=True, auth_audience="operator-control",
            auth_allowed_emails=("fabricated@example.invalid",),
            auth_hosted_domain="example.invalid", auth_application_clients_file=str(policy),
        )
        app.dependency_overrides[get_settings] = lambda: settings
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://pas.invalid"
        ) as client:
            headers = {"x-application-id": "travel",
                       "authorization": "Bearer " + bearer(principal.authorized_party)}
            async def preview(n, *, caller=headers, extra=None, action="context-preview"):
                return await client.post(
                    f"{route['PROFILE_PREFIX']}/{UUID(int=n)}/{action}",
                    headers=caller,
                    json={"content": "Summarize my trip using my saved preference.",
                          "idempotency_key": str(UUID(int=201)),
                          "choice": {"mode": "user_owned_plan"}, **(extra or {})},
                )
            if configure is None:
                results = await asyncio.gather(*(preview(n) for n in (101, 102, 101, 102)))
                assert all(r.status_code == 422 and r.json() == {"code": "context_no_ai_route"}
                           for r in results), [(r.status_code, r.text) for r in results]
            else:
                await verify_previews(preview)
            assert (await preview(999)).status_code == 404
            assert (await preview(101, caller=headers | {
                "authorization": "Bearer " + bearer("wrong-client"),
            })).status_code == 403
            assert (await preview(101, caller=headers | {
                "authorization": "Bearer " + bearer(principal.authorized_party, "wrong-audience"),
            })).status_code == 401
            assert (await preview(101, caller=headers | {"x-user-id-token": "forwarded"})).status_code == 401
            assert (await preview(101, extra={"entity_refs": []})).status_code == 422
    assert not service._reservations
    if configure is None:
        assert not service._previews
        print("Reduced PAS ASGI application reproduced four 422 context_no_ai_route responses.")
    print("Missing conversation 404, wrong azp 403, wrong audience/forwarded bearer 401, extra field 422.")


def reverse_hop():
    from personal_travel.api.schemas.private_plan import PrivatePlanSourceRequest
    from personal_travel.auth.private_plan import PrivatePlanTrust, authenticate_private_plan_source
    from starlette.datastructures import Headers

    from personal_ai.auth.delegation import delegated_user_assertion

    now = int(time.time())
    principal = AuthenticatedPrincipal(
        "https://accounts.google.com", "fabricated-subject", "fabricated-owner",
        "fabricated@example.invalid", now, True, authenticated_at=now,
        audience="synthetic-travel-aud", authorized_party="synthetic-travel-azp",
        expires_at=now + 300,
    )
    service_key = Ed25519PrivateKey.generate()
    human_key = Ed25519PrivateKey.generate()
    trust = PrivatePlanTrust(
        target_id="synthetic-pas", client_namespace=client_binding_namespace(principal, "travel"),
        service_audience="https://travel.invalid", service_account="synthetic-service@example.invalid",
        delegation_issuer="synthetic-pas-delegation", delegation_key_id="synthetic-key",
        delegation_public_key=human_key.public_key(),
    )
    body = {
        "schema_version": "travel-private-plan-source-v1", "purpose": "personal_ai_context",
        "destination_application_id": "travel", "workspace_id": None, "lane": "user_owned_plan",
        "target_id": trust.target_id, "client_namespace": trust.client_namespace,
        "conversation_id": str(UUID(int=101)), "operation": "current",
    }
    service = jwt.encode(
        {"iss": "synthetic-service-issuer", "aud": trust.service_audience,
         "sub": trust.service_account, "exp": now + 60},
        service_key, algorithm="EdDSA",
    )

    def verify_service(token, *, audience, expected_service_account):
        try:
            claims = jwt.decode(
                token, service_key.public_key(), algorithms=["EdDSA"], audience=audience,
                issuer="synthetic-service-issuer", options={"require": ["exp", "aud", "iss", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise ValueError("invalid synthetic service identity") from exc
        if claims["sub"] != expected_service_account:
            raise ValueError("wrong synthetic service account")

    def sign(request, *, age=0):
        return delegated_user_assertion(
            principal=replace(principal, issued_at=now - age, authenticated_at=now - age),
            request_body=request, private_key=human_key, issuer=trust.delegation_issuer,
            audience=trust.service_audience, key_id=trust.delegation_key_id, now=now - age,
        )

    def verify(request, assertion, *, service_token=service):
        fields = {"authorization": "Bearer " + service_token}
        if assertion:
            fields["x-user-delegation"] = assertion
        return authenticate_private_plan_source(
            Headers(fields), request, PrivatePlanSourceRequest.model_validate(request),
            trust, verify_service, clock=lambda: now,
        )

    body_b = body | {"conversation_id": str(UUID(int=102))}
    for current in (body, body_b, body, body_b):
        human = verify(current, sign(current))
        assert (human.issuer, human.subject) == (principal.issuer, principal.subject)

    changed = body | {"operation": "verify", "expected_source_version": "0"}
    assert verify(changed, sign(changed)).subject == principal.subject
    wrong_client = body | {"client_namespace": "b" * 64}
    wrong_target = body | {"target_id": "another-target"}
    forged_trip = body | {"entity_refs": [{"entity_type": "trip", "entity_id": str(UUID(int=202))}]}
    wrong_lane = body | {"lane": "automatic"}
    wrong_workspace = body | {"workspace_id": str(UUID(int=202))}
    for request, assertion, service_bearer in (
        (body_b, sign(body), service),
        (changed, sign(body), service),
        (body, sign(body, age=90), service),
        (wrong_client, sign(wrong_client), service),
        (wrong_target, sign(wrong_target), service),
        (forged_trip, sign(forged_trip), service),
        (wrong_lane, sign(wrong_lane), service),
        (wrong_workspace, sign(wrong_workspace), service),
        (body, None, service),
        (body, sign(body), sign(body)),
    ):
        try:
            verify(request, assertion, service_token=service_bearer)
        except ValueError:
            pass
        else:
            raise AssertionError("Unexpected reverse-hop authorization")
    print("PAS signer and Travel ingress accepted 5 bound assertions and denied 10 invalid combinations.")


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("Run without Python optimization so assertions are evaluated.")

    network_attempts = []

    def deny_network(event, _args):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg"}:
            network_attempts.append(event)
            raise AssertionError(f"Network operation in in-process diagnostic: {event}")

    sys.addaudithook(deny_network)
    asyncio.run(http_probe())
    reverse_hop()
    if network_attempts:
        raise SystemExit(f"Blocked network attempts: {network_attempts}")
    print("Audited outbound socket attempts: 0. No runtime release or provider send path exercised.")
