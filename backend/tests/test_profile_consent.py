"""PI-4 synthetic authority and deterministic interleaving regression probes."""

import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from personal_ai.api import dependencies as deps
from personal_ai.applications.contracts import ApplicationContextRequest, ApplicationDefinition
from personal_ai.applications.registry import ApplicationContribution, default_application_registry
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import (
    ApplicationScope,
    RequestScope,
    bind_request_scope,
    bind_verified_principal,
    reset_request_scope,
    reset_verified_principal,
)
from personal_ai.context import ContextAssembler
from personal_ai.context.adapters import BuiltInContextPermissionRevalidator
from personal_ai.context.contracts import ContextError
from personal_ai.context.history import (
    conversation_context_messages,
    memory_extraction_context_reason,
)
from personal_ai.context.profile import (
    GlobalProfileContextProviderFactory,
    GlobalProfileFieldUpdate,
    GlobalProfileUpdate,
    InMemoryGlobalProfileRepository,
)
from personal_ai.context.profile_consent import (
    ConsentError,
    ProfileConsentService,
    ProfileShareIntent,
    share_dependency,
    shared_memory_view_status,
)
from personal_ai.context.providers import ContextProviderCoordinator
from personal_ai.context.repositories import InMemorySummaryRepository
from personal_ai.context.tokens import FakeTokenCounter
from personal_ai.entities import Message, MessageRole, MessageStatus
from personal_ai.entities.turn_execution import TurnAttribution
from personal_ai.main import create_app
from personal_ai.settings import Settings, get_settings


def runtime():
    now = datetime.now(UTC)
    clock = [now]
    principal = AuthenticatedPrincipal(
        issuer="https://accounts.google.com", subject="synthetic-owner", owner_id="usr_pi4",
        email="synthetic@gmail.com", issued_at=int(time.time()), authenticated=True,
        authenticated_at=int(time.time()), audience="builtin-ui", authorized_party="builtin-ui",
        expires_at=int(time.time()) + 3600,
    )
    actor = f"{principal.issuer}|{principal.subject}"
    member = SimpleNamespace(allowed=True)

    class Membership:
        def is_member(self, principal, app, workspace):
            return member.allowed and workspace == "shelf" and principal.authenticated

    registry = default_application_registry().with_contributions(ApplicationContribution(
        definitions=(ApplicationDefinition(
            application_id="unrelated_reader", display_name="Unrelated Reader",
            memory_namespace="unrelated_reader", workspace_kind="required",
        ),), workspace_authorizers={"unrelated_reader": Membership()},
    ))
    settings = Settings(
        _env_file=None, ai_provider="fake", ai_model="pi4-fake", profile_sharing_enabled=True,
        app_environment="test", auth_mode="google_oidc", auth_required=True,
        auth_audience="builtin-ui", auth_allowed_emails=("synthetic@gmail.com",),
    )
    repository = InMemoryGlobalProfileRepository(clock=lambda: clock[0])
    repository.update(principal.owner_id, GlobalProfileUpdate(fields=(
        GlobalProfileFieldUpdate(field="preferred_units", value="metric"),
        GlobalProfileFieldUpdate(field="locale", value="en-GB"),
    )))
    scope = RequestScope(
        owner_id=principal.owner_id, acting_user_id=actor, application_id="unrelated_reader",
        workspace_id="shelf", request_id="pi4-synthetic",
    )
    registration = registry.registration(scope.application_id)
    context = ApplicationContextRequest(
        definition=registration.definition, scope=scope,
        context_provider_capabilities=registration.context_providers,
    )
    service = ProfileConsentService(repository, registry, principal)
    intent = ProfileShareIntent(
        operation_id=uuid4(), operation="grant", expected_revision=0,
        expected_profile_revision=1, grant_id=uuid4(), field="preferred_units",
        destination=ApplicationScope(application_id=scope.application_id, workspace_id="shelf"),
        expires_at=now + timedelta(hours=1),
    )
    validator = BuiltInContextPermissionRevalidator(settings, repository, registry, lambda: None)
    counter = FakeTokenCounter()
    factory = GlobalProfileContextProviderFactory(repository, settings, registry, lambda: None)
    assembler = ContextAssembler(
        settings, counter, InMemorySummaryRepository(),
        context_provider_coordinator=ContextProviderCoordinator({"global_profile": factory}),
        permission_revalidator=validator,
    )
    return SimpleNamespace(**locals())


@contextmanager
def bound(r, scope=None):
    token = bind_request_scope(scope or r.scope)
    principal_token = bind_verified_principal(r.principal)
    try:
        yield
    finally:
        reset_verified_principal(principal_token)
        reset_request_scope(token)


def pending(r, content="What units do I prefer?", conversation_id=None):
    return Message(
        id=uuid4(), conversation_id=conversation_id or uuid4(), owner_id=r.scope.owner_id,
        application_id=r.scope.application_id, workspace_id=r.scope.workspace_id, scope_version=2,
        role=MessageRole.USER, content=content, status=MessageStatus.COMPLETED, created_at=r.now,
    )


def assemble(r, history=()):
    plan = r.assembler.plan_context("What units do I prefer?", r.context)
    return r.assembler.assemble(
        history, pending(r), application_context=r.context, context_plan=plan, refresh=False,
    )


def revoke(r):
    state = r.repository.get_consents(r.principal.owner_id)
    return r.service.mutate(r.intent.model_copy(update={
        "operation_id": uuid4(), "operation": "revoke", "expected_revision": state.revision,
    }))


def dependency(r):
    return share_dependency(r.principal.owner_id, r.repository.get_consents(r.principal.owner_id).grants[0])


def test_no_consent_and_kill_switch_deny_even_legacy_allowlist():
    r = runtime()
    with bound(r):
        assert not assemble(r).source_items
        r.service.mutate(r.intent)
        dep = dependency(r)
        assert r.validator.is_current(dep)
        r.settings.profile_sharing_enabled = False
        assert not assemble(r).source_items
        assert not r.validator.is_current(dep)
    with pytest.raises(ValueError, match="requires_consent"):
        r.repository.update(r.principal.owner_id, GlobalProfileUpdate(fields=(
            GlobalProfileFieldUpdate(field="preferred_units", value="metric",
                                     shared_with_applications=(r.scope.application_id,)),
        )))
    assert r.repository.shared_fields(r.principal.owner_id, r.scope.application_id, ("preferred_units",)) == ()


def test_positive_canonical_planner_packer_and_exact_source():
    r = runtime()
    r.service.mutate(r.intent)
    with bound(r):
        result = assemble(r)
        assert result.manifest.injected_item_ids == ("preferred_units",)
        item = result.source_items[0]
        assert item.payload.value == "metric"
        assert item.application_id == "unrelated_reader"
        dep = item.permission_dependencies[0]
        assert dep.source_scope == ApplicationScope()
        assert dep.destination_application_id == "unrelated_reader"
        assert dep.owner_id == r.scope.owner_id and dep.acting_user_id == r.actor
        assert r.validator.is_current(dep)
        assert "metric" in " ".join(m.content for m in result.messages)
        assert "en-GB" not in " ".join(m.content for m in result.messages)


@pytest.mark.parametrize("change", ["actor", "owner", "workspace", "app", "missing_actor"])
def test_exact_recipient_binding(change):
    r = runtime()
    r.service.mutate(r.intent)
    dep = dependency(r)
    update = {"actor": {"acting_user_id": "other"}, "owner": {"owner_id": "other"},
              "workspace": {"workspace_id": "other"}, "app": {"application_id": "personal_ai"},
              "missing_actor": {"acting_user_id": None}}[change]
    with bound(r, r.scope.model_copy(update=update)):
        assert not r.validator.is_current(dep)
        assert not r.repository.authorized_fields(r.scope.model_copy(update=update), ("preferred_units",))


@pytest.mark.parametrize("change", ["value", "revoke", "expiry", "fence", "membership", "flag", "outage", "registration"])
def test_reuse_snapshot_and_assistant_history_denied(change):
    r = runtime()
    r.service.mutate(r.intent)
    with bound(r):
        result = assemble(r)
        snapshot = result.source_items[0].authority_snapshot()
        user = pending(r)
        answer = user.model_copy(update={
            "id": uuid4(), "role": MessageRole.ASSISTANT, "parent_message_id": user.id,
            "content": "Old metric answer", "attribution": TurnAttribution(
                fact_source="server_observed", execution_origin="automatic_managed", recorded_at=r.now,
                provider_id="synthetic", model_id="pi4",
                source_snapshots=(snapshot,),
            ),
        })
        assert memory_extraction_context_reason(answer) == "context_source_not_reusable"
        if change == "value":
            r.repository.update(r.principal.owner_id, GlobalProfileUpdate(fields=(
                GlobalProfileFieldUpdate(field="preferred_units", value="imperial"),
            )))
        elif change == "revoke":
            revoke(r)
        elif change == "expiry":
            r.clock[0] = r.intent.expires_at
        elif change == "fence":
            r.repository.fenced_owners.add(r.principal.owner_id)
        elif change == "membership":
            r.member.allowed = False
        elif change == "flag":
            r.settings.profile_sharing_enabled = False
        elif change == "outage":
            r.repository.authorized_fields = lambda *a, **k: (_ for _ in ()).throw(TimeoutError("private DB"))
        else:
            r.validator.application_registry = default_application_registry()
        assert not r.validator.is_current(snapshot.permission_dependencies[0])
        policy = r.context.definition.context_policy.sidecar.manual_import_reuse
        assert not conversation_context_messages(
            (user, answer), manual_import_reuse=policy, check_source_permissions=True,
            permission_revalidator=r.validator,
        )


def test_value_aba_requires_new_consent_and_old_dependency_never_revives():
    r = runtime()
    receipt = r.service.mutate(r.intent)
    dep = dependency(r)
    for value in ("imperial", "metric"):
        r.repository.update(r.principal.owner_id, GlobalProfileUpdate(fields=(
            GlobalProfileFieldUpdate(field="preferred_units", value=value),
        )))
    assert r.service.mutate(r.intent) == receipt
    with bound(r):
        assert not r.validator.is_current(dep)
        assert not assemble(r).source_items
    fresh = r.intent.model_copy(update={"operation_id": uuid4(), "grant_id": uuid4(),
        "expected_revision": 1, "expected_profile_revision": 3})
    r.service.mutate(fresh)
    with bound(r):
        assert assemble(r).source_items[0].payload.value == "metric"
        assert not r.validator.is_current(dep)


def test_same_key_recovery_changed_intent_and_stale_revoke():
    r = runtime()
    receipt = r.service.mutate(r.intent)  # Simulate lost response after durable commit.
    assert r.service.mutate(r.intent) == receipt
    with pytest.raises(ConsentError, match="conflict"):
        r.service.mutate(r.intent.model_copy(update={"field": "locale"}))
    revoke(r)
    assert r.service.mutate(r.intent) == receipt
    assert r.repository.get_consents(r.principal.owner_id).grants[0].revoked
    with pytest.raises(ConsentError, match="conflict"):
        r.service.mutate(r.intent.model_copy(update={"operation_id": uuid4()}))


def test_concurrent_stale_create_and_revoke_one_cas_winner():
    r = runtime()
    r.service.mutate(r.intent)
    create = r.intent.model_copy(update={"operation_id": uuid4(), "grant_id": uuid4(), "expected_revision": 1})
    rev = r.intent.model_copy(update={"operation_id": uuid4(), "operation": "revoke", "expected_revision": 1})
    def attempt(intent):
        try:
            return r.service.mutate(intent)
        except ConsentError:
            return None
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(attempt, (create, rev)))
    assert sum(x is not None for x in results) == 1
    # Original revoke can always be retried with fresh CAS, never extend old ID.
    if not r.repository.get_consents(r.principal.owner_id).grants[0].revoked:
        revoke(r)
    if results[0] is not None:
        before = r.repository.get_consents(r.principal.owner_id)
        assert r.service.mutate(create) == results[0]
        assert r.repository.get_consents(r.principal.owner_id) == before
    else:
        with pytest.raises(ConsentError):
            r.service.mutate(create)


def test_capacity_does_not_disable_revocation_and_no_receipts_are_pruned():
    r = runtime()
    last = None
    for index in range(32):
        last = r.intent.model_copy(update={
            "grant_id": uuid4() if index else r.intent.grant_id,
            "operation_id": uuid4(), "expected_revision": index,
        })
        r.service.mutate(last)
    with pytest.raises(ConsentError, match="capacity"):
        r.service.mutate(r.intent.model_copy(update={
            "grant_id": uuid4(), "operation_id": uuid4(), "expected_revision": 32,
        }))
    r.intent = last
    revoke(r)
    state = r.repository.get_consents(r.principal.owner_id)
    assert len(state.grants) == 32 and len(state.receipts) == 33


@pytest.mark.parametrize("mutate", ["wrong_purpose", "unknown_field", "naive_time", "extra_authority"])
def test_closed_intent_contract(mutate):
    r = runtime()
    data = r.intent.model_dump()
    data.update({"wrong_purpose": {"purpose": "embedding"}, "unknown_field": {"field": "health"},
                 "naive_time": {"expires_at": datetime.now(UTC).replace(tzinfo=None)}, "extra_authority": {"owner_id": "other"}}[mutate])
    with pytest.raises(ValidationError):
        ProfileShareIntent.model_validate(data)


@pytest.mark.parametrize("delta", [-1, 31 * 86400])
def test_ttl_bounds(delta):
    r = runtime()
    with pytest.raises(ConsentError, match="expiry"):
        r.service.mutate(r.intent.model_copy(update={"expires_at": r.now + timedelta(seconds=delta)}))


def test_unavailable_memory_view_reads_nothing():
    assert shared_memory_view_status() == {"available": False, "reason": "original_source_authority_unavailable"}


def test_revocation_during_count_blocks_next_count():
    r = runtime()
    r.service.mutate(r.intent)
    calls = []
    class Counter(FakeTokenCounter):
        def count(self, messages):
            text = " ".join(m.content for m in messages)
            calls.append(text)
            if "metric" in text:
                revoke(r)
            return super().count(messages)
    r.assembler.counter = Counter()
    with bound(r), pytest.raises(ContextError, match="authority_changed"):
        assemble(r)
    assert sum("metric" in call for call in calls) == 1


def test_revoke_after_fetch_prevents_any_count_of_shared_value():
    r = runtime()
    r.service.mutate(r.intent)
    original = r.repository.authorized_fields
    def fetch(scope, fields, **kwargs):
        rows = original(scope, fields, **kwargs)
        revoke(r)
        r.repository.authorized_fields = original
        return rows
    r.repository.authorized_fields = fetch
    with bound(r):
        result = assemble(r)
    assert "metric" not in " ".join(m.content for m in result.messages)


def test_management_through_actual_middleware_and_legacy_put(monkeypatch, tmp_path):
    r = runtime()
    app = create_app(selected_contributions=())
    app.state.application_registry = r.registry
    app.dependency_overrides.update({get_settings: lambda: r.settings,
        deps.get_global_profile_repository: lambda: r.repository})
    principal = [r.principal]
    monkeypatch.setattr("personal_ai.auth.middleware.principal_from_google_token", lambda *a: principal[0])
    headers = {"Authorization": "Bearer synthetic", "If-Match": '"0"'}
    with TestClient(app) as client:
        assert client.get("/v1/profile/shares").status_code == 401
        response = client.post("/v1/profile/shares", headers=headers, json=r.intent.model_dump(mode="json"))
        assert response.status_code == 200, response.text
        assert client.post("/v1/profile/shares", headers=headers, json=r.intent.model_dump(mode="json")).json() == response.json()
        listing = client.get("/v1/profile/shares", headers=headers).json()
        assert listing["grants"][0]["value"] == "metric"
        assert "cannot be recalled" in listing["warning"]
        assert client.put("/v1/profile", headers=headers, json={"fields": [{
            "field": "preferred_units", "value": "metric", "shared_with_applications": ["personal_ai"]}]}).status_code == 409
        assert client.put("/v1/profile", headers=headers, json={"fields": [{
            "field": "locale", "value": "en-US"}]}).status_code == 200
        principal[0] = replace(r.principal, authenticated_at=int(time.time()) - 86400)
        assert client.get("/v1/profile/shares", headers=headers).status_code == 401
        principal[0] = r.principal
        r.settings.profile_sharing_enabled = False
        assert client.get("/v1/profile/shares", headers=headers).status_code == 404


def chat_runtime(r, model=None):
    from personal_ai.entities import Conversation
    from personal_ai.llm.fake import FakeLLMClient
    from personal_ai.services.chat.service import ChatTurnService
    from personal_ai.storage.fake import InMemoryConversationRepository, InMemoryMessageRepository

    conversations = InMemoryConversationRepository()
    messages = InMemoryMessageRepository(conversations)
    conversation = Conversation(
        id=uuid4(), owner_id=r.scope.owner_id, title="Synthetic PI4",
        application_id=r.scope.application_id, workspace_id=r.scope.workspace_id, scope_version=2,
        created_at=r.now, updated_at=r.now,
    )
    conversations.create(conversation)
    model = model or FakeLLMClient(("metric ", "answer"))
    service = ChatTurnService(
        conversations, messages, model, owner_id=r.scope.owner_id,
        application_context=r.context, model="fake", context_assembler=r.assembler,
    )
    return service, conversation, model, messages


def continuation():
    from personal_ai.contracts.execution import ContinuationRequest

    return ContinuationRequest(
        idempotency_key=uuid4(), content="What units do I prefer?", choice={"mode": "automatic"},
    )


def test_model_path_original_key_replay_and_profile_taint():
    import asyncio

    from personal_ai.services.chat.events import TurnCompleted, TurnDelta, TurnFailed

    r = runtime()
    r.service.mutate(r.intent)
    with bound(r):
        service, conversation, model, _messages = chat_runtime(r)
        request = continuation()
        async def collect(stream):
            return [event async for event in stream]
        events = asyncio.run(collect(service.continue_turn(conversation.id, request)))
        completed = next(e.message for e in events if isinstance(e, TurnCompleted))
        assert completed.attribution.source_snapshots
        assert "metric" in " ".join(m.content for m in model.requests[0])
        assert "en-GB" not in " ".join(m.content for m in model.requests[0])
        revoke(r)
        replay = asyncio.run(collect(service.continue_turn(conversation.id, request)))
        assert len(model.requests) == 1
        assert isinstance(replay[-1], TurnFailed)
        assert not any(isinstance(e, (TurnCompleted, TurnDelta)) for e in replay)
        with pytest.raises(Exception, match="idempotency_input_changed"):
            service.continue_turn(conversation.id, request.model_copy(update={"content": "Changed"}))
        next_events = asyncio.run(collect(service.continue_turn(conversation.id, continuation())))
        assert any(isinstance(e, TurnCompleted) for e in next_events)
        assert "metric" not in " ".join(m.content for m in model.requests[-1])
        assert len(model.requests) == 2


def test_revoke_after_first_delta_suppresses_remaining_output():
    import asyncio

    from personal_ai.auth.application_clients import bind_client_authority, reset_client_authority
    from personal_ai.services.chat.events import TurnCompleted, TurnDelta, TurnFailed

    r = runtime()
    r.service.mutate(r.intent)
    with bound(r):
        service, conversation, model, _messages = chat_runtime(r)
        token = bind_client_authority(lambda: None)
        async def run():
            events = []
            async for event in service.continue_turn(conversation.id, continuation()):
                events.append(event)
                if isinstance(event, TurnDelta):
                    revoke(r)
            return events
        try:
            events = asyncio.run(run())
        finally:
            reset_client_authority(token)
        assert sum(isinstance(e, TurnDelta) for e in events) == 1
        assert isinstance(events[-1], TurnFailed)
        assert not any(isinstance(e, TurnCompleted) for e in events)
        assert len(model.requests) == 1


def test_revoke_before_model_reservation_no_model_send():
    import asyncio

    from personal_ai.services.chat.events import TurnFailed

    r = runtime()
    r.service.mutate(r.intent)
    with bound(r):
        service, conversation, model, _messages = chat_runtime(r)
        stream = service.continue_turn(conversation.id, continuation())
        revoke(r)  # Prepared snapshot is now stale, prior to entering the provider.
        async def collect():
            return [event async for event in stream]
        events = asyncio.run(collect())
        assert isinstance(events[-1], TurnFailed)
        assert not model.requests


def inherited_history(r, snapshot):
    history = []
    conversation_id = uuid4()
    for _ in range(10):
        user = pending(r, "question " * 35, conversation_id)
        assistant = user.model_copy(update={
            "id": uuid4(), "role": MessageRole.ASSISTANT, "parent_message_id": user.id,
            "content": "metric " + "historical " * 35,
            "attribution": TurnAttribution(
                fact_source="server_observed", execution_origin="automatic_managed",
                provider_id="synthetic", model_id="pi4", recorded_at=r.now,
                source_snapshots=(snapshot,),
            ),
        })
        history.extend((user, assistant))
    return history


@pytest.mark.parametrize("stage", ["summary_count", "summary_return"])
def test_revoke_during_summary_preparation_stops_further_disclosure(stage):
    from personal_ai.context.contracts import SummaryDraft

    r = runtime()
    r.service.mutate(r.intent)
    with bound(r):
        snapshot = assemble(r).source_items[0].authority_snapshot()
    r.assembler.settings = r.settings.model_copy(update={
        "max_context_tokens": 300, "max_response_tokens": 40,
        "context_safety_margin_tokens": 20, "max_summary_tokens": 30,
        "summary_trigger_tokens": 80,
    })
    summary_calls = []
    counts_after_revoke = []
    revoked = [False]
    class Counter(FakeTokenCounter):
        def count(self, messages):
            text = " ".join(m.content for m in messages)
            if revoked[0] and "metric" in text:
                counts_after_revoke.append(text)
            if stage == "summary_count" and "Source turns:" in text and not revoked[0]:
                revoke(r)
                revoked[0] = True
            return super().count(messages)
    class Summarizer:
        def summarize(self, source, prior, **kwargs):
            summary_calls.append(source)
            revoke(r)
            revoked[0] = True
            return SummaryDraft("Old metric summary", "synthetic")
    r.assembler.counter = Counter()
    r.assembler.summarizer = Summarizer()
    with bound(r):
        history = inherited_history(r, snapshot)
        with pytest.raises(Exception, match="authority_changed"):
            r.assembler.assemble(history, pending(r), application_context=r.context)
    assert revoked[0]
    assert not counts_after_revoke
    assert len(summary_calls) == (1 if stage == "summary_return" else 0)
    assert not r.assembler.summaries.records


def test_summary_inherits_dependencies_and_cannot_reintroduce_revoked_history():
    from personal_ai.context.contracts import ConversationSummary, fingerprint
    from personal_ai.context.history import summary_authority_snapshot

    r = runtime()
    r.service.mutate(r.intent)
    with bound(r):
        snapshot = assemble(r).source_items[0].authority_snapshot()
        history = inherited_history(r, snapshot)
        summary = ConversationSummary(
            id=uuid4(), conversation_id=history[0].conversation_id, owner_id=r.scope.owner_id,
            application_id=r.scope.application_id, workspace_id=r.scope.workspace_id, scope_version=2,
            content="Old metric summary", source_message_ids=tuple(m.id for m in history),
            source_fingerprint=fingerprint(history), covers_through_message_id=history[-1].id,
            source_token_count=100, summary_token_count=5, model="synthetic", created_at=r.now,
        )
        r.assembler.summaries.create(summary)
        inherited = summary_authority_snapshot(summary, history)
        assert inherited.permission_dependencies == snapshot.permission_dependencies
        revoke(r)
        result = r.assembler.assemble(history, pending(r), application_context=r.context)
        assert result.summary is None
        assert "metric" not in " ".join(m.content for m in result.messages)


def test_missing_or_forged_dependencies_fail_closed():
    from personal_ai.context.authority import source_snapshots_current

    r = runtime()
    r.service.mutate(r.intent)
    with bound(r):
        snapshot = assemble(r).source_items[0].authority_snapshot()
        assert not source_snapshots_current(
            (snapshot.model_copy(update={"permission_dependencies": ()}),), r.validator, now=r.now,
        )
        for update in ({"version": "global-profile-v1"}, {"source_revision": "999"},
                       {"purpose": "embedding"}, {"owner_id": "other"}, {"acting_user_id": None}):
            assert not r.validator.is_current(dependency(r).model_copy(update=update))


def test_current_owner_authority_outage_fails_closed():
    r = runtime()
    r.service.mutate(r.intent)
    with bound(r):
        assert r.validator.is_current(dependency(r))
        r.validator.authority = lambda: (_ for _ in ()).throw(RuntimeError("owner inactive"))
        assert not r.validator.is_current(dependency(r))


def test_shared_turn_never_calls_extractor_or_embedder():
    from personal_ai.memory.services import MemoryExtractionService

    r = runtime()
    r.service.mutate(r.intent)
    with bound(r):
        snapshot = assemble(r).source_items[0].authority_snapshot()
        answer = inherited_history(r, snapshot)[1]
        class NoCalls:
            def __getattr__(self, name):
                raise AssertionError("unexpected memory content access")
        settings = r.settings.model_copy(update={"memory_enabled": True, "memory_extraction_enabled": True})
        extraction = MemoryExtractionService(settings, NoCalls(), NoCalls(), NoCalls(), NoCalls())
        assert extraction.run(answer).reasons == ("context_source_not_reusable",)


def test_replacing_and_revoking_share_never_revives_older_grant():
    r = runtime()
    r.service.mutate(r.intent)
    old = dependency(r)
    replacement = r.intent.model_copy(update={
        "grant_id": uuid4(), "operation_id": uuid4(), "expected_revision": 1,
    })
    r.service.mutate(replacement)
    with bound(r):
        assert not r.validator.is_current(old)
        assert assemble(r).source_items
        r.intent = replacement
        revoke(r)
        assert not r.validator.is_current(old)
        assert not assemble(r).source_items


def test_owner_export_inventory_and_fenced_fake_erasure():
    from personal_ai.auth.owner_data import OWNER_DATA_COLLECTIONS
    from personal_ai.persistence.postgres.auth import EXPORT_IMPLEMENTATION_PATHS

    r = runtime()
    r.service.mutate(r.intent)
    assert "profile_consents" in OWNER_DATA_COLLECTIONS
    assert EXPORT_IMPLEMENTATION_PATHS["profile_consents"] == "postgres.payload-family"
    with pytest.raises(ValueError, match="owner_fence_required"):
        r.repository.purge_owner(r.principal.owner_id)
    r.repository.fenced_owners.add(r.principal.owner_id)
    r.repository.purge_owner(r.principal.owner_id)
    assert r.principal.owner_id not in r.repository.records
    assert r.principal.owner_id not in r.repository.consents
    with pytest.raises(ValueError, match="owner_deletion_fenced"):
        r.service.mutate(r.intent)


@pytest.mark.parametrize("kind", ["unknown_app", "wrong_workspace", "missing_workspace", "disabled", "sensitivity", "field_denied"])
def test_grant_requires_current_destination_membership_and_field_policy(kind):
    from personal_ai.applications.registry import ApplicationRegistry

    r = runtime()
    intent = r.intent
    if kind == "unknown_app":
        intent = intent.model_copy(update={"destination": ApplicationScope(application_id="unknown_app")})
    elif kind == "wrong_workspace":
        intent = intent.model_copy(update={"destination": ApplicationScope(application_id="unrelated_reader", workspace_id="other")})
    elif kind == "missing_workspace":
        intent = intent.model_copy(update={"destination": ApplicationScope(application_id="unrelated_reader")})
    else:
        definition = r.context.definition
        capabilities = r.registry.capabilities
        if kind == "disabled":
            capabilities = tuple(c.model_copy(update={"available": False}) if c.capability_id == "global_profile" else c
                                 for c in capabilities)
        elif kind == "sensitivity":
            definition = definition.model_copy(update={"context_policy": definition.context_policy.model_copy(update={"maximum_model_sensitivity": "public"})})
        else:
            policy = definition.context_policy
            definition = definition.model_copy(update={"context_policy": policy.model_copy(update={
                "provider_policies": tuple(p for p in policy.provider_policies if p.provider_id != "global_profile"),
            })})
        r.service.registry = ApplicationRegistry(
            (definition,), capabilities, workspace_authorizers=r.registry.workspace_authorizers,
        )
    with pytest.raises(ConsentError, match="destination_denied"):
        r.service.mutate(intent)
    assert not r.repository.get_consents(r.principal.owner_id).grants


def test_snapshot_rechecks_deduplicated_dependencies_at_every_boundary():
    from personal_ai.context.authority import source_snapshots_current

    r = runtime()
    r.service.mutate(r.intent)
    with bound(r):
        snapshot = assemble(r).source_items[0].authority_snapshot()
        checks = []
        class Validator:
            def is_current(self, dep):
                checks.append(dep)
                return r.validator.is_current(dep)
        assert source_snapshots_current((snapshot,) * 100, Validator(), now=r.now)
        assert len(checks) == 1
        revoke(r)
        assert not source_snapshots_current((snapshot,) * 100, Validator(), now=r.now)
        assert len(checks) == 2


def test_actual_consent_dependency_rechecked_at_physical_reservation():
    from personal_ai.context.authority import permission_dependencies_current
    from personal_ai.llm.disclosure import bind_disclosure_guard
    from personal_ai.llm.execution import SendAccounting, _send_authority

    r = runtime()
    r.service.mutate(r.intent)
    with bound(r):
        dep = dependency(r)
        calls = []
        ledger = SimpleNamespace(endpoint_profile_resolver=None, reserve_attempt=lambda *a, **k: calls.append(True))
        def guard():
            if not permission_dependencies_current((dep,), r.validator):
                raise ContextError("context_source_authority_changed")
        token = _send_authority.set((object(), object()))
        try:
            revoke(r)
            with bind_disclosure_guard(guard), pytest.raises(ContextError, match="authority_changed"):
                SendAccounting(ledger).reserve_attempt(object(), object(), max_attempts=1)
        finally:
            _send_authority.reset(token)
        assert not calls


def test_concurrent_builder_calls_cannot_overwrite_shared_count_guard():
    from threading import Event

    from personal_ai.context.builder import ContextBuilder, ContextBuildItem, ContextBuildPolicy
    from personal_ai.llm.client import ChatMessage

    r = runtime()
    r.service.mutate(r.intent)
    with bound(r):
        item = assemble(r).source_items[0]
    entered, release = Event(), Event()
    class Counter(FakeTokenCounter):
        held = False
        def count(self, messages):
            if not self.held and any("metric" in m.content for m in messages):
                self.held = True
                entered.set()
                assert release.wait(3)
            return super().count(messages)
    builder = ContextBuilder(Counter(), permission_revalidator=r.validator)
    policy = ContextBuildPolicy.for_settings(r.settings, 2000)
    def first():
        with bound(r):
            return builder.build((ChatMessage("user", "units?"),), (ContextBuildItem.from_context_item(item),), policy)
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(first)
        assert entered.wait(3)
        try:
            builder.build((ChatMessage("user", "independent"),), (), policy)
            revoke(r)
        finally:
            release.set()
        with pytest.raises(ContextError, match="authority_changed"):
            future.result(timeout=3)
