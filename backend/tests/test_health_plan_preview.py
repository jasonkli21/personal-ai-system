"""The Health candidate uses real private PAS handlers with synthetic authorities."""

import json
import os
import subprocess
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from selectors import EVENT_READ, DefaultSelector
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from personal_ai.api import dependencies as deps
from personal_ai.api.private_application_plan import PROFILE_PREFIX, RECEIPT_HEADER
from personal_ai.applications.contracts import (
    ApplicationContextPolicy,
    ApplicationDefinition,
    CapabilityRegistration,
    ContextFieldPolicy,
    ContextOperationPolicy,
    ContextProviderPolicy,
)
from personal_ai.applications.registry import (
    ApplicationContribution,
    ApplicationContributionCatalog,
)
from personal_ai.auth import verification
from personal_ai.auth.application_clients import client_binding_namespace
from personal_ai.auth.directory import IdentityMappingConflict
from personal_ai.auth.scope import ApplicationScope, application_scope_context
from personal_ai.context.contracts import fingerprint
from personal_ai.context.repositories import InMemorySummaryRepository
from personal_ai.context.runtime import ContextRuntimeContributionCatalog
from personal_ai.context.traces import InMemoryContextTraceRepository
from personal_ai.contracts.context_references import ApplicationPlanSourceGrant
from personal_ai.entities import Message
from personal_ai.main import create_app
from personal_ai.memory.dependencies import memory_dependency
from personal_ai.persistence.postgres.auth import PostgresPrincipalDirectory
from personal_ai.persistence.postgres.lifecycle import PostgresMemoryLifecycleRepository
from personal_ai.persistence.postgres.memory import PostgresMemoryRepository
from personal_ai.services.chat.service import ChatTurnService
from personal_ai.settings import Settings, get_settings
from personal_ai.storage.fake import InMemoryConversationRepository, InMemoryMessageRepository
from tests.app_context_support.application_plan import ApplicationPlanFixture, plan_request
from tests.app_context_support.health_preview import (
    FIELDS,
    PROVIDER,
    SCHEMA,
    HealthSource,
    HealthSourceClient,
    ProfilePayload,
    Selection,
    canonical,
    digest,
)
from tests.app_context_support.health_receipts import (
    KEY_ID,
    LIFETIME,
    NONCE_HEADER,
    TITLE,
    Enrollment,
    Operation,
    ReceiptAuthority,
    decode,
    encode,
    receipt_fields,
    verify_receipt,
)
from tests.persistence.test_local_persistence import _SourceGuard
from tests.test_travel_plan_paired import EMAIL, bearer_factory

APP = "health"
AUDIENCE = "fabricated-health-client"
POLICY_EPOCH = "health-synthetic-preview-policy-v1"
MEMORY = "I prefer reminders with one topic at a time."
HISTORY = ("How should we organize this example?", "We can start with a short outline.")
RECORD = {
    "kind": "preference",
    "category": "preferences",
    "key": "r5_synthetic_presentation_format",
    "label": "Synthetic presentation format",
    "value": {"type": "text", "value": "bullets"},
}


class ExistingOwners:
    """Directory dependency for this isolated host. Lookup never bootstraps."""

    def __init__(self, principal):
        self.active = {principal.owner_id: (principal.issuer, principal.subject)}
        self.lookup_count = 0
        self.recovery_current = lambda: True

    def ensure_active(self, principal, *, correlation_id):
        self.require_existing(principal)

    def require_existing(self, principal):
        self.lookup_count += 1
        if self.active.get(principal.owner_id) != (principal.issuer, principal.subject):
            raise IdentityMappingConflict


def settings_for(tmp_path, now):
    policy = tmp_path / "registered-clients.json"
    policy.write_text(
        json.dumps(
            {
                "schema_version": "application-client-policy-v1",
                "bindings": [
                    {
                        "audience": AUDIENCE,
                        "authorized_party": AUDIENCE,
                        "application_id": APP,
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
        memory_enabled=True,
    )


def application(*, allow_restricted=True):
    shared = ApplicationContextPolicy()
    sensitivity = "restricted" if allow_restricted else "sensitive"
    policy = ApplicationContextPolicy(
        version=POLICY_EPOCH,
        maximum_model_sensitivity=sensitivity,
        provider_policies=(
            *shared.provider_policies,
            ContextProviderPolicy(
                provider_id=PROVIDER,
                operations=(
                    ContextOperationPolicy(
                        operation="current",
                        sensitivity="restricted",
                        fields=(ContextFieldPolicy(field="record", sensitivity="restricted"),),
                    ),
                ),
            ),
        ),
    )
    return ApplicationContribution(
        definitions=(
            ApplicationDefinition(
                application_id=APP,
                display_name="Synthetic Health",
                workspace_kind="unsupported",
                memory_namespace=APP,
                context_provider_ids=("conversation_history", "ai_memory", PROVIDER),
                context_policy=policy,
            ),
        ),
        capabilities=(
            CapabilityRegistration(
                capability_id=PROVIDER,
                kind="context_provider",
                available=True,
            ),
        ),
    )


class HealthFixture:
    """A mock reverse source with the exact Health Step 2 synthetic record shape."""

    def __init__(self, now, selected):
        self.now = now
        self.selected = selected
        self.source_id = uuid4()
        self.calls = []
        self.adverse = None
        self.after_read = lambda: None

    def handle(self, request):
        read = json.loads(request.content)
        operation = read.get("operation")
        assert request.method == "POST" and request.url.path == "/source"
        assert read == self.selected.request(operation)
        self.calls.append(operation)
        claims = {
            "schema_version": SCHEMA,
            "application_id": APP,
            "workspace_id": None,
            "operation": operation,
            "truncated": False,
            "categories": [],
            "items": [],
            "permission_versions": [],
        }
        if operation == "verify":
            claims["permission_versions"] = [
                {
                    "object_id": str(self.selected.object_id),
                    "version": self.selected.version if self.adverse != "verify" else "revoked",
                }
            ]
        else:
            payload = ProfilePayload.model_validate(
                {
                    "record": RECORD,
                    "category": "profile_preferences",
                    "object_type": "profile_item",
                }
            ).model_dump(mode="json")
            item = {
                "object_id": str(self.selected.object_id),
                "object_type": "profile_item",
                "object_revision": self.selected.revision,
                "schema_version": 1,
                "source_id": str(self.source_id),
                "source_version": f"health-object-v1:r{self.selected.revision}:schema-1",
                "source_kind": "manual",
                "confirmation_status": "user_confirmed",
                "authority": "authoritative",
                "observed_at": self.now.isoformat(),
                "active_state": "active",
                "sensitivity": "restricted",
                "field_sensitivity": [{"field": "record", "sensitivity": "restricted"}],
                "permission_dependencies": [
                    {
                        "permission_id": self.selected.dependency,
                        "purpose": "personal_ai_context",
                        "version": self.selected.version,
                    }
                ],
                "source_refs": [
                    {"kind": kind, "reference_id": str(ref), "fingerprint": digest(payload)}
                    for kind, ref in (
                        ("record", self.selected.object_id),
                        ("source", self.source_id),
                    )
                ],
                "payload": payload,
            }
            if self.adverse == "record":
                item["object_id"] = str(uuid4())
            if self.adverse == "revision":
                item["object_revision"] += 1
            if self.adverse == "sensitivity":
                item["field_sensitivity"][0]["sensitivity"] = "sensitive"
            if self.adverse == "nested field":
                item["payload"]["record"]["value"]["notes"] = "outside the allowed shape"
            if self.adverse == "notes":
                item["payload"]["notes"] = "fixture notes"
            if self.adverse == "fingerprint":
                item["source_refs"][0]["fingerprint"] = "0" * 64
            if self.adverse == "expired":
                item["expires_at"] = (self.now - timedelta(seconds=1)).isoformat()
            claims["items"] = [] if self.adverse == "absent" else [item]
            claims["truncated"] = self.adverse == "truncated"
            self.after_read()
        if self.adverse == "oversized":
            return httpx.Response(
                200, headers={"content-type": "application/json"}, content=b" " * 4097
            )
        if self.adverse == "duplicate":
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                content=canonical(claims)[:-1] + b',"application_id":"health"}',
            )
        return httpx.Response(200, json=claims)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    def build(
        *, allow_restricted=True, reverse_transport=None, health_binding=None,
        database=None, subject="fabricated-human", verify_transaction=None, bearer_override=None,
        runtime_options=None,
    ):
        now = datetime.now(UTC)
        fixture_dir = tmp_path / uuid4().hex
        fixture_dir.mkdir()
        settings = settings_for(fixture_dir, now)
        bearer = bearer_override or bearer_factory(monkeypatch, now)
        token = bearer(AUDIENCE, subject=subject)
        principal = verification.principal_from_google_token(token, settings)
        namespace = client_binding_namespace(principal, APP)
        if health_binding is None:
            health_binding = {
                "owner": str(uuid4()),
                "enrollment_id": str(uuid4()),
                "installation_id": str(uuid4()),
                "object_id": str(uuid4()),
                "revision": 3,
            }
        selected = Selection(UUID(health_binding["object_id"]), health_binding["revision"])
        enrollment = Enrollment(
            UUID(health_binding["enrollment_id"]),
            1,
            UUID(health_binding["installation_id"]),
            UUID(health_binding["owner"]),
            principal.owner_id,
            f"{principal.issuer}|{principal.subject}",
            namespace,
            selected,
            "synthetic-source-epoch-1",
            POLICY_EPOCH,
        )
        current = {enrollment.enrollment_id: enrollment}
        signing_key = Ed25519PrivateKey.generate()
        conversations = InMemoryConversationRepository()
        messages = InMemoryMessageRepository(conversations)

        def current_branch(owner, conversation):
            return fingerprint(
                messages.list_active(owner_id=owner, conversation_id=conversation),
                include_state=True,
            )

        def active_enrollment(enrollment_id):
            enrolled = current.get(enrollment_id)
            if enrolled is None:
                return None
            try:
                directory.require_existing(principal)
            except IdentityMappingConflict:
                return None
            if getattr(directory, "owner_is_fenced", lambda _: False)(principal.owner_id):
                return None
            return enrolled

        authority = ReceiptAuthority(
            signing_key, active_enrollment, current_branch, verify_transaction=verify_transaction
        )
        reverse = HealthFixture(now, selected)
        grants = {}
        source = HealthSource(
            HealthSourceClient(httpx.MockTransport(reverse_transport or reverse.handle)),
            lambda binding: (
                enrollment.selected
                if active_enrollment(enrollment.enrollment_id) == enrollment
                and binding.target_id == enrollment.target_id
                else None
            ),
            lambda binding, purpose: grants.get((binding.conversation_id, purpose)),
        )
        catalog = ApplicationContributionCatalog(
            ((APP, lambda: application(allow_restricted=allow_restricted)),),
        )
        runtime = ContextRuntimeContributionCatalog(((APP, lambda _: source.contribution()),))
        app = create_app(
            application_catalog=catalog,
            context_runtime_catalog=runtime,
            selected_contributions=(APP,),
        )
        memory_repositories = None
        if database is None:
            directory = ExistingOwners(principal)
        else:
            directory = PostgresPrincipalDirectory(database)
            directory.ensure_active(principal, correlation_id="synthetic-existing-owner")
            directory.recovery_current = lambda: True

            def memory_repositories(messages):
                memories = PostgresMemoryRepository(database, _SourceGuard(principal.owner_id))
                return memories, PostgresMemoryLifecycleRepository(memories, messages, jobs=None)
        app.state.isolate_external_conversations = True
        app.state.external_conversation_access = lambda scope, client: (
            (scope.owner_id, scope.application_id, scope.workspace_id, client)
            == (principal.owner_id, APP, None, namespace)
        )
        app.state.principal_directory = directory
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
        fixture = ApplicationPlanFixture(
            host, fixture_dir, bound_receipts=authority, memory_repositories=memory_repositories
        )
        target = fixture.onboard(
            SimpleNamespace(
                principal=principal,
                app=SimpleNamespace(app=APP, source=PROVIDER),
                token=token,
                control=bearer("owner-control", subject=subject),
                workspace=None,
            ),
            memory_content=MEMORY,
            source_grants=False,
            memory_application_id="personal_ai",
            **(runtime_options or {}),
        )
        target.plan = replace(
            target.plan, preview_source=source.selection(enrollment.target_id, selected)
        )
        fixture.targets[principal.owner_id, APP, None, namespace] = target.plan
        headers = {
            "authorization": f"Bearer {token}",
            "x-application-id": APP,
            "content-type": "application/json",
        }
        return SimpleNamespace(
            app=app,
            target=target,
            fixture=fixture,
            reverse=reverse,
            grants=grants,
            authority=authority,
            current=current,
            enrollment=enrollment,
            headers=headers,
            principal=principal,
            namespace=namespace,
            bearer=bearer,
            now=now,
            messages=messages,
            verify_keys={KEY_ID: signing_key.public_key()},
            directory=directory,
        )

    return build


def prepare(host, payload, *, cid=None, create_key=None, branch=None, **changes):
    binding = host.target.plan.preview_binding(host.principal, cid or UUID(int=0))
    operation = Operation(
        enrollment=host.enrollment,
        key=UUID(payload["idempotency_key"]),
        create_key=create_key or UUID(payload["idempotency_key"]),
        request_digest=digest(payload),
        conversation_id=cid,
        frozen_target=binding.target_fingerprint,
        branch_digest=branch,
        expires=int(datetime.now(UTC).timestamp()) + LIFETIME,
    )
    operation = replace(operation, **changes)
    nonce = str(uuid4())
    host.authority.pending[nonce] = operation
    return operation, {**host.headers, NONCE_HEADER: nonce}


def create(host, client, key):
    body = {"title": TITLE, "idempotency_key": str(key)}
    operation, headers = prepare(host, body)
    result = client.post(PROFILE_PREFIX, headers=headers, content=canonical(body))
    assert result.status_code == 201, result.text
    return result, operation, headers


def configure_preview(host, cid, *, branch_id=None):
    user_id = uuid4()
    with application_scope_context(ApplicationScope(application_id=APP)):
        for role, msg, parent in (
            ("user", HISTORY[0], None),
            ("assistant", HISTORY[1], user_id),
        ):
            host.messages.create(
                Message(
                    id=user_id if parent is None else branch_id or uuid4(),
                    conversation_id=cid,
                    application_id=APP,
                    owner_id=host.principal.owner_id,
                    role=role,
                    content=msg,
                    status="completed",
                    parent_message_id=parent,
                    created_at=host.now + (timedelta(microseconds=1) if parent else timedelta()),
                )
            )
        active = host.messages.list_active(owner_id=host.principal.owner_id, conversation_id=cid)
    binding = host.target.plan.preview_binding(host.principal, cid)
    for purpose, recipient in (
        ("source-read", binding.target_id),
        ("runtime-handoff", binding.runtime_recipient),
        ("inference-disclosure", binding.model_recipient),
    ):
        host.grants[cid, purpose] = ApplicationPlanSourceGrant(
            binding=binding,
            purpose=purpose,
            recipient=recipient,
            fields=FIELDS,
            version=f"{purpose}-1",
            expires_at=host.now + timedelta(minutes=2),
        )
    return fingerprint(active, include_state=True)


def receive(host, response, expected, *, header=None, body=None, now=None):
    expected = {
        key: value
        for key, value in expected.items()
        if key not in {"iat", "exp", "response_digest"}
    }
    return verify_receipt(
        header if header is not None else response.headers[RECEIPT_HEADER],
        keys=host.verify_keys,
        expected=expected,
        response=response.content if body is None else body,
        now=int(datetime.now(UTC).timestamp()) if now is None else now,
    )


def preview(host, client, cid, create_key, branch, *, key=None, **changes):
    body = plan_request(key)
    operation, headers = prepare(
        host,
        body,
        cid=cid,
        create_key=create_key,
        branch=branch,
        **changes,
    )
    return client.post(operation.path, headers=headers, content=canonical(body)), operation


def test_receipts_original_keys_exact_inventory_and_dispatch_guard(setup, monkeypatch):
    host = setup()
    replay_attempts = []

    def reject_replay(*args, **kwargs):
        replay_attempts.append((args, kwargs))
        raise AssertionError("bound continuation must terminate before replay")

    monkeypatch.setattr(ChatTurnService, "replay_bound_turn", reject_replay)
    key = uuid4()
    with TestClient(host.app) as client:
        initial, operation, headers = create(host, client, key)
        cid = UUID(initial.json()["conversation_id"])
        expected = receipt_fields(operation, cid, initial.content, 0)
        create_claims = receive(host, initial, expected)
        assert initial.headers["cache-control"] == "no-store"
        same_nonce = client.post(
            PROFILE_PREFIX,
            headers=headers,
            json={"idempotency_key": str(key), "title": TITLE},
        )
        assert same_nonce.status_code == 422
        retry, retry_operation, _ = create(host, client, key)
        assert retry.content == initial.content
        receive(host, retry, receipt_fields(retry_operation, cid, retry.content, 0))
        with application_scope_context(ApplicationScope(application_id=APP)):
            assert [
                row.id
                for row in host.fixture.host.conversations.list_for_external_client(
                    owner_id=host.principal.owner_id,
                    client_namespace=host.namespace,
                )
            ] == [cid]

        branch = configure_preview(host, cid)
        result, op = preview(host, client, cid, key, branch)
        assert result.status_code == 200, (result.text, host.reverse.calls)
        meta = result.json()
        assert meta["selected_context"] == [
            {"category": "conversation_history", "turns": 1},
            {"category": "ai_memory", "fields": ["content"]},
            {"category": "domain_current", "fields": ["record"]},
        ]
        assert result.headers["cache-control"] == "no-store"
        assert all(
            secret not in result.text
            for secret in (
                MEMORY,
                *HISTORY,
                "bullets",
                str(host.enrollment.selected.object_id),
            )
        )
        source_calls = tuple(host.reverse.calls)
        assert len(source_calls) >= 4
        assert all(
            pair == ("profile", "verify")
            for pair in zip(source_calls[::2], source_calls[1::2], strict=True)
        )
        with application_scope_context(ApplicationScope(application_id="personal_ai")):
            memory_state = host.fixture.lifecycle.get_state(
                owner_id=host.principal.owner_id,
                memory_id=host.target.memory.id,
            )
        canonical_memory = memory_dependency(
            host.target.memory,
            memory_state,
            acting_user_id=host.enrollment.actor,
        )
        mem_purposes = ("runtime-handoff", "inference-disclosure")
        expected = receipt_fields(op, cid, result.content, 0) | {
            "branch_digest": branch,
            "actual_revision": host.enrollment.selected.revision,
            "permission_version": host.enrollment.selected.version,
            "source_sensitivity": "restricted",
            "source_grants": {
                purpose: grant.version for (_, purpose), grant in host.grants.items()
            },
            "memory_grants": {"approved-pas-memory-origin": canonical_memory.version}
            | {
                purpose: grant.dependency(canonical_memory, purpose).version
                for purpose, grant in zip(
                    mem_purposes,
                    host.fixture.disclosures[host.target.plan.scope],
                    strict=True,
                )
            },
            "inventory_digest": digest(meta["selected_context"]),
            "confirmation": meta["confirmation"],
            "destination": {
                "application": APP,
                "provider": "ChatGPT",
                "model": host.target.plan.model,
                "runtime": host.target.plan.scope.local_recipient,
                "recipient": host.target.plan.scope.model_recipient,
            },
        }
        receipt = receive(host, result, expected)
        assert receipt["exp"] - receipt["iat"] <= LIFETIME
        assert create_claims["original_key"] == receipt["original_create_key"]
        other = expected | {"selection": expected["selection"] | {"object_id": str(uuid4())}}
        wrong_revision = expected | {
            "actual_revision": host.enrollment.selected.revision + 1,
        }
        wrong_destination = expected | {
            "destination": expected["destination"] | {"recipient": "other"},
        }
        for altered in (other, wrong_revision, wrong_destination):
            with pytest.raises(ValueError):
                receive(host, result, altered)
        with pytest.raises(ValueError):
            receive(host, result, expected, body=result.content + b" ")
        with pytest.raises(ValueError):
            receive(host, result, expected, now=receipt["exp"])
        with pytest.raises(ValueError):
            receive(host, result, expected, header=initial.headers[RECEIPT_HEADER])
        statement, signature = result.headers[RECEIPT_HEADER].split(".")
        bad_signature = bytearray(decode(signature))
        bad_signature[0] ^= 1
        with pytest.raises(ValueError):
            receive(host, result, expected, header=f"{statement}.{encode(bad_signature)}")
        for label in ("kid", "aud"):
            forged = dict(receipt, **{label: "fixture-untrusted"})
            altered_bytes = canonical(forged)
            fake = encode(host.authority.key.sign(altered_bytes))
            with pytest.raises(ValueError):
                receive(host, result, expected, header=f"{encode(altered_bytes)}.{fake}")

        payload = plan_request(op.key, meta["confirmation"])
        for _ in range(2):
            denied = client.post(
                f"{PROFILE_PREFIX}/{cid}/continue",
                headers=host.headers,
                json=payload,
            )
            assert denied.status_code == 422
            assert denied.json()["error"]["code"] == "context_no_ai_route"

    assert replay_attempts == []
    assert tuple(host.reverse.calls) == source_calls
    assert sum(len(payload) for payload in host.target.local_payloads) == 0
    assert host.target.provider.sends() == []
    print("HEALTH_PRIVATE_CONTINUE_HTTP=422,422 RUNTIME_HANDOFF_BYTES=0 FAKE_PROVIDER_POSTS=0")


def test_default_off_and_lookup_only_direct_actor(setup):
    host = setup()
    ordinary = create_app()
    ordinary.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        app_environment="test",
        auth_mode="development",
        auth_required=False,
        ai_provider="fake",
        ai_model="fabricated",
    )
    with TestClient(ordinary) as open_api:
        assert open_api.post(PROFILE_PREFIX, json={}).status_code == 404
    payload = {"idempotency_key": str(uuid4()), "title": TITLE}
    _, headers = prepare(host, payload)
    with TestClient(host.app) as client:
        for update, status in (
            ({"authorization": f"Bearer {host.bearer(AUDIENCE, subject='unknown')}"}, 403),
            ({"authorization": f"Bearer {host.bearer('owner-control')}"}, 403),
            ({"authorization": f"Bearer {host.bearer(AUDIENCE, azp='other-client')}"}, 403),
            ({"authorization": f"Bearer {host.bearer(AUDIENCE, auth_time=0)}"}, 422),
            ({"x-user-id-token": "fake Firebase token"}, 401),
            ({NONCE_HEADER: str(uuid4())}, 422),
        ):
            denied = client.post(PROFILE_PREFIX, headers=headers | update, json=payload)
            assert denied.status_code == status, denied.text
        changed = client.post(PROFILE_PREFIX, headers=headers, json=payload | {"title": "changed"})
        assert changed.status_code == 422
        host.directory.active.clear()
        disabled = client.post(PROFILE_PREFIX, headers=headers, json=payload)
        assert disabled.status_code == 403
        assert not host.directory.active and not host.authority.creates and not host.reverse.calls


@pytest.mark.parametrize(
    "adverse",
    [
        "record",
        "revision",
        "notes",
        "nested field",
        "verify",
        "sensitivity",
        "fingerprint",
        "absent",
        "expired",
        "truncated",
        "oversized",
        "duplicate",
    ],
)
def test_rejects_nonexact_health_source(setup, adverse):
    host = setup()
    host.reverse.adverse = adverse
    with TestClient(host.app) as client:
        key = uuid4()
        created, _, _ = create(host, client, key)
        cid = UUID(created.json()["conversation_id"])
        branch = configure_preview(host, cid)
        denied, _ = preview(host, client, cid, key, branch)
    assert denied.status_code == 422 and RECEIPT_HEADER not in denied.headers
    assert not host.fixture.service._previews
    assert not host.target.local_payloads and not host.target.provider.sends()


@pytest.mark.parametrize(
    "permission",
    [
        "source-read",
        "runtime-handoff",
        "inference-disclosure",
        "wrong_model_recipient",
        "grant_epoch",
        "source_epoch",
        "enrollment",
        "application_policy",
        "memory",
        "branch",
        "branch_change",
        "destination",
    ],
)
def test_independent_current_permissions_precede_publication(setup, permission):
    host = setup(allow_restricted=permission != "application_policy")
    with TestClient(host.app) as client:
        key = uuid4()
        created, _, _ = create(host, client, key)
        cid = UUID(created.json()["conversation_id"])
        branch = configure_preview(host, cid)
        args = {}
        if permission in {"source-read", "runtime-handoff", "inference-disclosure"}:
            host.grants.pop((cid, permission))
        if permission == "wrong_model_recipient":
            grant = host.grants[cid, "inference-disclosure"]
            host.grants[cid, "inference-disclosure"] = grant.model_copy(
                update={"recipient": "other"}
            )
        if permission == "grant_epoch":
            grant = host.grants[cid, "inference-disclosure"]
            host.reverse.after_read = lambda: host.grants.update(
                {
                    (cid, "inference-disclosure"): grant.model_copy(
                        update={"version": "new-grant"}
                    ),
                }
            )
        if permission == "memory":
            host.reverse.after_read = lambda: host.fixture.disclosures.clear()
        if permission == "enrollment":
            host.reverse.after_read = lambda: host.current.update(
                {
                    host.enrollment.enrollment_id: replace(host.enrollment, generation=2),
                }
            )
        if permission == "source_epoch":
            host.reverse.after_read = lambda: host.current.update(
                {
                    host.enrollment.enrollment_id: replace(host.enrollment, source_epoch="changed"),
                }
            )
        if permission == "branch":
            branch = "0" * 64
        if permission == "branch_change":

            def new_message():
                host.reverse.after_read = lambda: None
                with application_scope_context(ApplicationScope(application_id=APP)):
                    active = host.messages.list_active(
                        owner_id=host.principal.owner_id,
                        conversation_id=cid,
                    )
                    host.messages.create(
                        Message(
                            id=uuid4(),
                            conversation_id=cid,
                            application_id=APP,
                            owner_id=host.principal.owner_id,
                            role="user",
                            content="New branch head.",
                            status="completed",
                            parent_message_id=active[-1].id,
                            created_at=datetime.now(UTC),
                        )
                    )

            host.reverse.after_read = new_message
        if permission == "destination":
            args["frozen_target"] = "0" * 64
        denied, _ = preview(host, client, cid, key, branch, **args)
    assert denied.status_code == 422 and RECEIPT_HEADER not in denied.headers
    assert not host.fixture.service._previews
    assert not host.target.local_payloads and not host.target.provider.sends()
    if permission in {
        "source-read",
        "runtime-handoff",
        "inference-disclosure",
        "wrong_model_recipient",
        "application_policy",
        "destination",
    }:
        assert host.reverse.calls == []


@pytest.mark.skipif(
    not all(
        os.environ.get(name)
        for name in (
            "R5_HEALTH_CHECKOUT",
            "R5_HEALTH_PYTHON",
            "R5_HEALTH_SOCKET_DSN",
        )
    ),
    reason="requires the Step 2 checkout, its locked interpreter and an already migrated test DB",
)
def test_native_health_reservation_keys_and_projection_reach_candidate_pas(setup):
    checkout = Path(os.environ["R5_HEALTH_CHECKOUT"]).resolve()
    assert subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=checkout, text=True
    ).strip() == ("049e88a6189e6d8955736318ac6a610de41feaa8")
    assert not (checkout / ".env").exists() and not (checkout / "services/api/.env").exists()
    runner = Path(__file__).parent / "app_context_support/health_step2_worker.py"
    child_env = {key: os.environ[key] for key in ("PATH", "R5_HEALTH_SOCKET_DSN")}
    child_env["PYTHONPATH"] = str(checkout / "services/api/src")
    with (
        subprocess.Popen(
            [os.environ["R5_HEALTH_PYTHON"], "-sB", str(runner)],
            cwd=checkout,
            env=child_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        ) as worker,
        DefaultSelector() as reader,
    ):
        reader.register(worker.stdout, EVENT_READ)

        def read():
            assert reader.select(timeout=5), "Health fixture response timeout"
            return json.loads(worker.stdout.readline())

        def call(operation, values):
            worker.stdin.write(json.dumps([operation, values]) + "\n")
            worker.stdin.flush()
            return read()

        try:
            health_binding = read()

            def transport(request):
                raw = request.content.decode()
                operation = json.loads(raw)["operation"]
                result = call("source", {"raw": raw, "operation": operation})
                return httpx.Response(
                    200,
                    content=result["body"],
                    headers={"content-type": "application/json"},
                )

            host = setup(reverse_transport=transport, health_binding=health_binding)
            branch_id = uuid4()
            target = host.target.plan.preview_binding(host.principal, UUID(int=0))
            reservation = {
                # The Health draft UUID type cannot represent the real PAS usr_* ID.
                # This explicitly synthetic value never authorizes the PAS request.
                "synthetic_pas_owner_uuid": str(uuid4()),
                "client_id": str(uuid4()),
                "branch_id": str(branch_id),
                "destination_digest": target.target_fingerprint,
                # Step 2 generates the original key after receiving the local digest.
                "local_digest": digest({"title": TITLE, "fixture": "pre-key Health local intent"}),
                "profile_request": canonical(host.enrollment.selected.request("profile")).decode(),
            }
            keys = call("reserve", reservation)
            assert keys["create"] != keys["preview"]
            with TestClient(host.app) as client:
                key = UUID(keys["create"])
                response, operation, _ = create(host, client, key)
                cid = UUID(response.json()["conversation_id"])
                receive(host, response, receipt_fields(operation, cid, response.content, 0))
                assert call("reserve", reservation) == keys
                retry, _, _ = create(host, client, key)
                assert retry.content == response.content
                branch = configure_preview(host, cid, branch_id=branch_id)
                result, op = preview(host, client, cid, key, branch, key=UUID(keys["preview"]))
                assert result.status_code == 200, result.text
                statement, signature = result.headers[RECEIPT_HEADER].split(".")
                host.verify_keys[KEY_ID].verify(decode(signature), decode(statement))
                claims = json.loads(decode(statement))
                assert claims["original_create_key"] == keys["create"]
                assert claims["original_key"] == keys["preview"]
                assert claims["actual_revision"] == health_binding["revision"]
                assert claims["selection"]["object_id"] == health_binding["object_id"]
                assert claims["response_digest"] == sha256(result.content).hexdigest()
                denied = client.post(
                    f"{PROFILE_PREFIX}/{cid}/continue",
                    headers=host.headers,
                    json=plan_request(op.key, result.json()["confirmation"]),
                )
                assert denied.status_code == 422
            assert not host.target.local_payloads and not host.target.provider.sends()
            assert call("stop", {}) == {"forbidden_network_attempts": []}
            assert worker.wait(timeout=5) == 0
        finally:
            if worker.poll() is None:
                worker.kill()
    print(
        "HEALTH_STEP2_PG_KEYS=2 PRIVATE_CONTINUE_HTTP=422 RUNTIME_HANDOFF_BYTES=0 FAKE_PROVIDER_POSTS=0"
    )
