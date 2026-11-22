"""Create and preview against the isolated PAS host and migrated Travel source."""

# ruff: noqa: F811 - pytest imports fixtures by name

import base64
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from selectors import EVENT_READ, DefaultSelector
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from personal_ai_reference_apps.applications import application_contribution
from personal_ai_reference_apps.context.travel_plan import (
    CURRENT_FIELDS,
    TravelPlanSource,
    TravelPlanSourceClient,
)

from personal_ai.api import dependencies as deps
from personal_ai.api.private_application_plan import PROFILE_PREFIX, RECEIPT_HEADER
from personal_ai.applications.registry import ApplicationContributionCatalog
from personal_ai.auth import verification
from personal_ai.auth.application_clients import client_binding_namespace
from personal_ai.context.repositories import InMemorySummaryRepository
from personal_ai.context.runtime import ContextRuntimeContributionCatalog
from personal_ai.context.traces import InMemoryContextTraceRepository
from personal_ai.contracts.context_references import ApplicationPlanSourceGrant
from personal_ai.main import create_app
from personal_ai.persistence.postgres.auth import PostgresPrincipalDirectory
from personal_ai.persistence.postgres.lifecycle import PostgresMemoryLifecycleRepository
from personal_ai.persistence.postgres.memory import PostgresMemoryRepository
from personal_ai.settings import Settings, get_settings
from personal_ai.storage.fake import InMemoryConversationRepository, InMemoryMessageRepository
from tests.app_context_support.application_plan import ApplicationPlanFixture, plan_request
from tests.persistence.conftest import isolated_postgres_dsn  # noqa: F401 - pytest fixture
from tests.persistence.test_local_persistence import _SourceGuard
from tests.persistence.test_shared_application_service_postgres import (
    shared_db,  # noqa: F401 - pytest fixture
)

TRIPS = (str(UUID(int=201)), str(UUID(int=202)))
TITLES = ("Fabricated native trip A", "Fabricated native trip B · Ålesund")
REVISIONS = (0, 9)
MEMORY = "I prefer concise itinerary summaries."
PROMPT = "Summarize my trip using my saved preference."
ISSUER = "https://accounts.google.com"
AUDIENCE = "fabricated-travel-client"
EMAIL = "fabricated@example.invalid"
ORIGIN = "https://travel.invalid"
REQUIRED_ENV = (
    "TRAVEL_BACKEND",
    "TRAVEL_TEST_PYTHON",
    "TEST_DATABASE_URL",
    "PERSISTENCE_TEST_POSTGRES_DSN",
)

pytestmark = pytest.mark.skipif(
    not all(os.environ.get(name) for name in REQUIRED_ENV),
    reason="requires a locked Travel checkout and disposable PostgreSQL DSNs",
)


@contextmanager
def travel_worker(config):
    runner = Path(__file__).parent / "app_context_support/travel_plan_worker.py"
    travel_backend = Path(os.environ["TRAVEL_BACKEND"]).resolve()
    if (travel_backend / ".env").exists():
        raise ValueError("Use a Travel backend checkout without a local .env file.")
    child_env = {name: os.environ[name] for name in ("PATH", "TEST_DATABASE_URL")}
    with (
        subprocess.Popen(
            [os.environ["TRAVEL_TEST_PYTHON"], "-IB", str(runner.resolve())],
            cwd=travel_backend,
            env=child_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        ) as process,
        DefaultSelector() as reader,
    ):
        reader.register(process.stdout, EVENT_READ)
        pas_handler = None

        def set_pas_handler(handler):
            nonlocal pas_handler
            pas_handler = handler

        def send(payload):
            process.stdin.write(json.dumps(payload) + "\n")
            process.stdin.flush()

        def exchange(payload):
            send(payload)
            while reader.select(timeout=10):
                reply = process.stdout.readline()
                if not reply:
                    raise RuntimeError("Travel fixture stopped before sending a response")
                result = json.loads(reply)
                if "pas_request" not in result:
                    return result
                # PAS can make one nested reverse-source call before replying to
                # the Travel HTTP request. The worker services that call on this pipe.
                response = pas_handler(**result["pas_request"])
                send(
                    [
                        "pas_response",
                        {
                            "status_code": response.status_code,
                            "headers": dict(response.headers),
                            "content": response.text,
                        },
                    ]
                )
            raise TimeoutError("Travel fixture did not respond")

        try:
            assert exchange(config) == {"ready": True}
            yield (lambda method, **values: exchange([method, values])), set_pas_handler
        finally:
            process.stdin.close()
            try:
                assert process.wait(timeout=10) == 0
            except subprocess.TimeoutExpired:
                process.kill()
                raise


def make_pas_settings(tmp_path, now):
    policy = tmp_path / "clients.json"
    policy.write_text(
        json.dumps(
            {
                "schema_version": "application-client-policy-v1",
                "bindings": [
                    {
                        "audience": AUDIENCE,
                        "authorized_party": AUDIENCE,
                        "application_id": "travel",
                        "expires_at": int(now.timestamp()) + 300,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return Settings(
        _env_file=None,
        app_environment="test",
        ai_provider="fake",
        ai_model="fabricated",
        auth_mode="google_oidc",
        auth_required=True,
        auth_audience="owner-control",
        auth_allowed_emails=(EMAIL,),
        auth_hosted_domain="example.invalid",
        auth_application_clients_file=str(policy),
        travel_context_enabled=True,
        travel_context_base_url=ORIGIN,
        travel_context_service_audience=ORIGIN,
        travel_context_service_account="fabricated-pas@example.invalid",
        memory_enabled=True,
    )


def bearer_factory(monkeypatch, now):
    key = Ed25519PrivateKey.generate()

    def verify(token, audiences):
        try:
            return jwt.decode(
                token, key.public_key(), algorithms=["EdDSA"], audience=audiences, issuer=ISSUER
            )
        except jwt.PyJWTError as error:
            raise verification.InvalidIdentityToken from error

    def bearer(audience=AUDIENCE, *, subject="fabricated-human", **overrides):
        issued = int(now.timestamp())
        return jwt.encode(
            {
                "iss": ISSUER,
                "sub": subject,
                "aud": audience,
                "azp": audience,
                "email": EMAIL,
                "email_verified": True,
                "hd": "example.invalid",
                "iat": issued,
                "auth_time": issued,
                "exp": issued + 300,
            }
            | overrides,
            key,
            algorithm="EdDSA",
        )

    monkeypatch.setattr(verification, "_verified_claims", verify)
    return bearer


def setup_pas(tmp_path, settings, now, source, principal, namespace, bearer, database, receipt_key):
    catalog = ApplicationContributionCatalog(
        (("travel", lambda: application_contribution("travel")),)
    )
    runtime = ContextRuntimeContributionCatalog((("travel", lambda _: source.contribution()),))
    app = create_app(
        application_catalog=catalog,
        context_runtime_catalog=runtime,
        selected_contributions=("travel",),
    )
    app.state.isolate_external_conversations = True
    app.state.external_conversation_access = lambda scope, client: (
        (scope.owner_id, scope.application_id, scope.workspace_id, client)
        == (principal.owner_id, "travel", None, namespace)
    )
    directory = PostgresPrincipalDirectory(database)
    app.state.principal_directory = directory
    conversations = InMemoryConversationRepository()
    messages = InMemoryMessageRepository(conversations)
    overrides = {
        get_settings: settings,
        deps.get_conversation_repository: conversations,
        deps.get_message_repository: messages,
        deps.get_context_trace_repository: InMemoryContextTraceRepository(),
        deps.get_global_profile_repository: None,
        deps.get_summary_repository: InMemorySummaryRepository(),
        deps.get_provider_usage_accounting: None,
        deps.get_memory_adapter: None,
    }

    def provide(value):
        return lambda: value

    app.dependency_overrides.update(
        {dependency: provide(value) for dependency, value in overrides.items()}
    )
    host = SimpleNamespace(
        app=app,
        settings=settings,
        now=now,
        conversations=conversations,
        messages=messages,
        directory=directory,
        controls=SimpleNamespace(is_member=lambda *_: True),
        permissions=source,
        identify=lambda token: verification.principal_from_google_token(token, settings),
    )
    directory.recovery_current = lambda: True

    def memory_repositories(messages):
        memories = PostgresMemoryRepository(database, _SourceGuard(principal.owner_id))
        return memories, PostgresMemoryLifecycleRepository(memories, messages, jobs=None)

    fixture = ApplicationPlanFixture(
        host,
        tmp_path,
        memory_repositories=memory_repositories,
        travel_receipt_key=receipt_key,
    )
    target = fixture.onboard(
        SimpleNamespace(
            principal=principal,
            app=SimpleNamespace(app="travel", source=source.spec.provider_id),
            token=bearer(),
            control=bearer("owner-control"),
            workspace=None,
        ),
        memory_content=MEMORY,
        source_grants=False,
    )
    target.plan = replace(
        target.plan, preview_source=source.selection("isolated-pas-preview", max_tokens=1536)
    )
    fixture.targets[principal.owner_id, "travel", None, namespace] = target.plan
    return app, fixture, target


def test_native_travel_create_bind_preview_and_release_denial(tmp_path, monkeypatch, shared_db):
    now = datetime.now(UTC)
    settings = make_pas_settings(tmp_path, now)
    bearer = bearer_factory(monkeypatch, now)
    principal = verification.principal_from_google_token(bearer(), settings)
    namespace = client_binding_namespace(principal, "travel")
    delegation_key = Ed25519PrivateKey.generate()
    service_key = Ed25519PrivateKey.generate()
    receipt_key = Ed25519PrivateKey.generate()
    trust = {
        "target_id": "isolated-pas-preview",
        "client_namespace": namespace,
        "service_audience": ORIGIN,
        "service_account": "fabricated-pas@example.invalid",
        "delegation_issuer": "fabricated-preview-host",
        "delegation_key_id": "private-preview",
        "delegation_public_key": delegation_key.public_key().public_bytes_raw().hex(),
    }
    service_body = json.dumps({"aud": ORIGIN, "account": trust["service_account"]}).encode()
    service_token = ".".join(
        base64.urlsafe_b64encode(value).decode()
        for value in (service_body, service_key.sign(service_body))
    )
    service_config = {
        "trust": trust,
        "receipt_public_key": receipt_key.public_key().public_bytes_raw().hex(),
        "service_public_key": service_key.public_key().public_bytes_raw().hex(),
        "identity": {
            name: getattr(principal, name) for name in ("owner_id", "issuer", "subject", "email")
        },
        "trips": [
            {"id": trip, "title": title, "revision": revision}
            for trip, title, revision in zip(TRIPS, TITLES, REVISIONS, strict=True)
        ],
    }
    outbound = []
    active = True

    def audit(event, _):
        if active and event in {
            "socket.connect",
            "socket.getaddrinfo",
            "socket.sendto",
            "socket.sendmsg",
        }:
            outbound.append(event)
            raise PermissionError("PAS test networking disabled")

    sys.addaudithook(audit)
    try:
        with travel_worker(service_config) as (travel, set_pas_handler):
            verify_pair(
                tmp_path,
                settings,
                now,
                bearer,
                principal,
                namespace,
                delegation_key,
                service_token,
                trust,
                travel,
                set_pas_handler,
                shared_db,
                receipt_key,
            )
    finally:
        active = False
    assert not outbound, outbound


def verify_pair(
    tmp_path,
    settings,
    now,
    bearer,
    principal,
    namespace,
    key,
    service_token,
    trust,
    travel,
    set_pas_handler,
    database,
    receipt_key,
):
    calls = []
    grants = {}

    def transport(request):
        body = json.loads(request.content)
        result = travel("source", json=body, headers=dict(request.headers))["result"]
        calls.append((body, result))
        return httpx.Response(result["status"], headers=result["headers"], text=result["body"])

    def grant(binding, *, purpose, **_):
        return grants.get((binding.conversation_id, purpose))

    source = TravelPlanSource(
        TravelPlanSourceClient(
            base_url=ORIGIN,
            audience=ORIGIN,
            issuer=trust["delegation_issuer"],
            key_id=trust["delegation_key_id"],
            signing_key=key,
            service_token=lambda **_: service_token,
            transport=httpx.MockTransport(transport),
        ),
        grant,
        grant,
        grant,
    )
    app, fixture, target = setup_pas(
        tmp_path, settings, now, source, principal, namespace, bearer, database, receipt_key
    )
    headers = {
        "authorization": f"Bearer {bearer()}",
        "x-application-id": "travel",
        "content-type": "application/json",
    }
    default = create_app()
    default.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        app_environment="test",
        auth_mode="development",
        auth_required=False,
        ai_provider="fake",
        ai_model="fabricated",
    )
    with TestClient(default) as ordinary, TestClient(app) as pas:
        assert ordinary.get("/health").status_code == 200
        assert (
            ordinary.post(f"{PROFILE_PREFIX}/{uuid4()}/context-preview", json={}).status_code == 404
        )
        assert ordinary.post(PROFILE_PREFIX, json={}).status_code == 404
        destination = {
            "application": "travel",
            "provider": "ChatGPT",
            "model": target.plan.model,
            "runtime": target.plan.scope.local_recipient,
            "recipient": target.plan.scope.model_recipient,
        }
        assert travel("register_destination", **destination) == {"result": None}
        outbound = []

        def pas_transport(path, method, headers, content):
            response = pas.request(method, path, headers=headers, content=content)
            outbound.append((path, content, response))
            return response

        set_pas_handler(pas_transport)

        def signed_probe(operation, conversation, request, response, *, revision=None, **overrides):
            raw = canonical(response)
            statement = {
                "schema_version": "travel-application-plan-receipt-v1",
                "operation": operation,
                "target_id": trust["target_id"],
                "client_namespace": namespace,
                "application_id": "travel",
                "workspace_id": None,
                "owner_id": principal.owner_id,
                "issuer": principal.issuer,
                "subject": principal.subject,
                "conversation_id": conversation,
                "request_digest": sha256(request.encode()).hexdigest(),
                "response_digest": sha256(raw.encode()).hexdigest(),
                "source_revision": str(revision) if revision is not None else None,
            } | overrides
            return [raw, receipt_key.sign(canonical(statement).encode()).hex()]

        candidates = create_and_bind(
            pas, travel, headers, bearer, set_pas_handler, pas_transport, signed_probe
        )
        receipts = {}

        def preview(index, caller=headers, **extra):
            candidate = candidates[index]
            return pas.post(
                f"{PROFILE_PREFIX}/{candidate['conversation_id']}/context-preview",
                content=canonical(plan_request(candidate["original_key"], content=PROMPT) | extra),
                headers=caller,
            )

        for candidate in candidates:
            cid = UUID(candidate["conversation_id"])
            binding = target.plan.preview_binding(principal, cid)
            for purpose, recipient in (
                ("source-read", binding.target_id),
                ("runtime-handoff", binding.runtime_recipient),
                ("inference-disclosure", binding.model_recipient),
            ):
                grants[cid, purpose] = ApplicationPlanSourceGrant(
                    binding=binding,
                    purpose=purpose,
                    recipient=recipient,
                    fields=CURRENT_FIELDS,
                    version="1",
                    expires_at=now + timedelta(seconds=110),
                )

        for index in (0, 1, 0, 1):
            response = preview(index)
            assert response.status_code == 200, response.text
            assert response.headers["cache-control"] == "no-store"
            assert len(response.content) <= 8192
            value = response.json()
            assert value["destination"]["application"] == "travel"
            assert value["destination"]["model"] == target.plan.model
            assert value["destination"]["runtime"] == target.plan.scope.local_recipient
            assert value["destination"]["recipient"] == target.plan.scope.model_recipient
            assert all(item not in response.text for item in (*TITLES, MEMORY))
            cid = UUID(candidates[index]["conversation_id"])
            frozen = fixture.service._previews[
                target.plan.scope, cid, UUID(candidates[index]["original_key"])
            ]
            package = frozen.package.canonical().decode()
            assert (
                TITLES[index] in package and TITLES[1 - index] not in package and MEMORY in package
            )
            snapshot = next(
                item for item in frozen.snapshots if item.provider_id == source.spec.provider_id
            )
            assert snapshot.source_version == str(REVISIONS[index])
            assert snapshot.application_plan_authority.binding.conversation_id == cid
            raw = next(
                json.loads(result["body"])["items"][0]
                for body, result in reversed(calls)
                if body["operation"] == "current"
            )
            assert raw["entity_id"] == TRIPS[index]
            assert raw["source_refs"][0]["fingerprint"] == snapshot.content_fingerprint
            assert raw["source_id"] == snapshot.source_id
            assert (
                raw["permission_dependencies"][0]["version"]
                == snapshot.permission_dependencies[0].version
            )
            assert (
                datetime.fromisoformat(raw["observed_at"])
                == snapshot.application_plan_authority.observed_at
            )
            receipts[index] = response

        current = [body["conversation_id"] for body, _ in calls if body["operation"] == "current"]
        assert current == [candidates[index]["conversation_id"] for index in (0, 1, 0, 1)]
        assert all(0 < len(result["body"].encode()) <= 4096 for _, result in calls)
        first, second = candidates
        assert travel("reserve_preview", **second, content=PROMPT) == {"result": "reserved"}
        genuine = receipts[1]
        raw = genuine.json()
        request = canonical(plan_request(second["original_key"], content=PROMPT))
        reconstructed_receipts = (
            signed_probe(
                "preview",
                second["conversation_id"],
                request,
                raw | {"expires_at": (now - timedelta(seconds=1)).isoformat()},
                revision=REVISIONS[1],
            ),
            signed_probe(
                "preview",
                second["conversation_id"],
                request,
                raw | {"destination": destination | {"recipient": "wrong-account"}},
                revision=REVISIONS[1],
            ),
            signed_probe(
                "preview",
                second["conversation_id"],
                request,
                raw,
                revision=REVISIONS[0],
            ),
            signed_probe(
                "preview",
                second["conversation_id"],
                canonical(plan_request(second["original_key"], content=PROMPT + " changed")),
                raw,
                revision=REVISIONS[1],
            ),
        )
        forged = (
            [genuine.text, "a" * 128],
            receipt_wire(receipts[0]),
            [json.dumps(raw | {"confirmation": "0" * 64}), genuine.headers[RECEIPT_HEADER]],
            [
                json.dumps(raw | {"expires_at": (now + timedelta(seconds=5)).isoformat()}),
                genuine.headers[RECEIPT_HEADER],
            ],
            [
                json.dumps(raw | {"destination": destination | {"recipient": "wrong-account"}}),
                genuine.headers[RECEIPT_HEADER],
            ],
            *reconstructed_receipts,
        )
        for receipt in forged:
            assert travel("record_preview", **second, receipt=receipt) == {"error": 404}
            assert travel("intent_state", original_key=second["original_key"]) == {
                "result": "preview_pending"
            }

        positive = travel("preview", **first, content=PROMPT, bearer=bearer())
        assert "result" in positive, positive
        confirmed_preview = positive["result"]
        assert confirmed_preview == outbound[-1][2].json()
        assert travel("intent_state", original_key=first["original_key"]) == {
            "result": "preview_ready"
        }
        assert travel("record_preview_unknown", **second) == {"result": None}
        assert travel("original_status", **second) == {
            "result": {
                "conversation_id": second["conversation_id"],
                "original_key": second["original_key"],
            }
        }
        assert travel("original_status", **(second | {"original_key": str(uuid4())})) == {
            "result": None
        }
        assert travel("reserve_preview", **second, content=PROMPT + " changed") == {"error": 409}
        status_options = {"bearer": bearer()}
        assert travel("inspect_original_status", **second, **status_options) == {
            "result": "not_found"
        }
        assert outbound[-1][0] == (
            f"/v1/conversations/{second['conversation_id']}/continuations/{second['original_key']}"
        )
        sent = len(outbound)
        wrong_request = second | {"original_key": str(uuid4())}
        assert travel("inspect_original_status", **wrong_request, **status_options) == {
            "result": None
        }
        assert len(outbound) == sent

        count = len(calls)
        cid = UUID(first["conversation_id"])
        for purpose in ("source-read", "runtime-handoff", "inference-disclosure"):
            saved = grants.pop((cid, purpose))
            assert preview(0).status_code == 422
            grants[cid, purpose] = grants[UUID(second["conversation_id"]), purpose]
            assert preview(0).status_code == 422
            grants[cid, purpose] = saved.model_copy(
                update={"expires_at": now - timedelta(seconds=1)}
            )
            assert preview(0).status_code == 422
            grants[cid, purpose] = saved
        memory = fixture.disclosures[target.plan.scope]
        fixture.disclosures[target.plan.scope] = (
            memory[0],
            replace(memory[1], recipient="other-model"),
        )
        assert preview(0).status_code == 422
        fixture.disclosures[target.plan.scope] = memory
        assert (
            preview(
                0, headers | {"authorization": f"Bearer {bearer(azp='unregistered')}"}
            ).status_code
            == 403
        )
        assert (
            preview(
                0, headers | {"authorization": f"Bearer {bearer(subject='other-human')}"}
            ).status_code
            == 403
        )
        assert preview(0, headers | {"x-user-id-token": bearer()}).status_code == 401
        assert len(calls) == count

        denied = pas.post(
            f"{PROFILE_PREFIX}/{first['conversation_id']}/continue",
            headers=headers,
            json=plan_request(
                first["original_key"], confirmed_preview["confirmation"], content=PROMPT
            ),
        )
        assert denied.status_code == 422 and len(calls) == count
        conversation = f"/v1/conversations/{first['conversation_id']}"
        status = pas.get(f"{conversation}/continuations/{first['original_key']}", headers=headers)
        assert status.status_code == 200 and status.json()["state"] == "not_found"
        detail = pas.get(conversation, headers=headers)
        assert detail.status_code == 200 and detail.json()["messages"] == []
        assert target.local_payloads == target.provider.sends() == []
        assert travel("change_trip", trip_id=TRIPS[0], owner_id="fabricated-revoked-owner") == {
            "result": None
        }
        assert preview(0).status_code in (422, 503)
        assert calls[-1][1]["status"] == 404
        assert travel("inspect_original_status", **first, **status_options) == {"error": 404}
        assert travel("remove_anchor", conversation_id=second["conversation_id"]) == {
            "result": None
        }
        assert travel("inspect_original_status", **second, **status_options) == {"error": 404}
        assert len(outbound) == sent


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def receipt_wire(response):
    return [response.text, response.headers[RECEIPT_HEADER]]


def create_and_bind(pas, travel, headers, bearer, set_pas_handler, pas_transport, signed_probe):
    title = "Fabricated private conversation"
    keys = [str(uuid4()) for _ in TRIPS]
    bodies = [canonical({"title": title, "idempotency_key": key}) for key in keys]
    created = []

    def lose_first_create_response(path, method, headers, content):
        response = pas_transport(path, method, headers, content)
        assert response.status_code == 201, response.text
        created.append(response)
        return httpx.Response(503)

    options = {"bearer": bearer()}
    set_pas_handler(lose_first_create_response)
    assert travel("create", trip_id=TRIPS[0], create_key=keys[0], title=title, **options) == {
        "error": "receipt_unavailable"
    }
    created.append(pas.post(PROFILE_PREFIX, headers=headers, content=bodies[1]))
    for response in created:
        assert response.status_code == 201, response.text
    assert travel("reserve_create", trip_id=TRIPS[1], create_key=keys[1], title=title) == {
        "result": {"newly_reserved": True, "conversation_id": None}
    }

    for index, trip in enumerate(TRIPS):
        arguments = {"trip_id": trip, "create_key": keys[index], "title": title}
        set_pas_handler(lambda response=created[1 - index], **_: response)
        assert travel("create", **arguments, **options) == {"error": 404}
        set_pas_handler(
            lambda response=created[index], **_: httpx.Response(
                201, json=response.json(), headers={"cache-control": "no-store"}
            )
        )
        assert travel("create", **arguments, **options) == {"error": "receipt_unavailable"}
        own_create = created[index]
        other_cid = created[1 - index].json()["conversation_id"]
        other_detail = pas.get(f"/v1/conversations/{other_cid}", headers=headers)
        assert other_detail.status_code == 200
        cid = own_create.json()["conversation_id"]
        forged = (
            [own_create.text, "f" * 128],
            [other_detail.text, own_create.headers[RECEIPT_HEADER]],
            *(
                signed_probe("create", cid, bodies[index], own_create.json(), **foreign)
                for foreign in (
                    {"target_id": "foreign-target"},
                    {"client_namespace": "b" * 64},
                    {"owner_id": "foreign-owner"},
                    {"subject": "foreign-subject"},
                )
            ),
        )
        for receipt in forged:
            assert travel(
                "bind_created_conversation",
                trip_id=trip,
                create_key=keys[index],
                receipt=receipt,
            ) == {"error": 404}
        assert travel("reserve_create", **arguments) == {
            "result": {"newly_reserved": False, "conversation_id": None}
        }

    set_pas_handler(pas_transport)
    candidates = []
    for trip, key, response in zip(TRIPS, keys, created, strict=True):
        cid = response.json()["conversation_id"]
        assert travel("create", trip_id=trip, create_key=key, title=title, **options) == {
            "result": cid
        }
        replay = pas.post(PROFILE_PREFIX, headers=headers, content=bodies[TRIPS.index(trip)])
        assert replay.status_code == 201 and receipt_wire(replay) == receipt_wire(response)
        detail = pas.get(f"/v1/conversations/{cid}", headers=headers)
        assert detail.status_code == 200 and detail.json()["conversation"]["id"] == cid
        candidates.append({"trip_id": trip, "conversation_id": cid, "original_key": str(uuid4())})
    return candidates
