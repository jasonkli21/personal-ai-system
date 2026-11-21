"""One source-free PAS turn through the canonical issuer and injected local transport."""

import json
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs
from uuid import uuid4

import pytest

from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.applications.registry import default_application_registry
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.dispatch_grants import DispatchGrantSigner
from personal_ai.auth.scope import RequestScope
from personal_ai.context import ContextAssembler
from personal_ai.context.tokens import EstimatedTokenCounter
from personal_ai.contracts.context_references import ContextSourceSnapshot
from personal_ai.entities import Conversation, Message, MessageRole, MessageStatus
from personal_ai.entities.turn_execution import TurnAttribution, TurnReservation
from personal_ai.llm.chatgpt.responses import ChatGPTResponses
from personal_ai.llm.client import ExternalCompletion
from personal_ai.llm.external import CHATGPT_PLAN_PROFILE
from personal_ai.local_bridge.runtime import BridgeDenied
from personal_ai.local_bridge.store import LocalStoreError, ProtectedLocalStore
from personal_ai.routing.registry import EndpointRegistry
from personal_ai.services.chat.service import ChatTurnService
from personal_ai.services.external_turns import (
    ContinuationRequest,
    ExecutionChoice,
    ExternalTurnService,
)
from personal_ai.services.external_turns.authority import (
    LocalChatDispatch,
    PrincipalBoundExternalTurnAuthority,
)
from personal_ai.settings import Settings
from personal_ai.storage import InMemoryConversationRepository, InMemoryMessageRepository
from personal_ai.storage.errors import ConversationConflictError
from tests.test_chatgpt_bridge_transport import (
    FOREGROUND_PROMPT,
    bridge_fixture,
    created,
    delta,
    run_bridge,
)
from tests.test_chatgpt_oauth import OAuthFixture
from tests.test_external_turns import profile


@pytest.fixture
def local_turn(tmp_path):
    bridge, provider, session, _, _, key = bridge_fixture(tmp_path)
    scope = bridge.installation.scope
    principal = AuthenticatedPrincipal(
        issuer="https://pas-identity.test",
        subject="owner",
        owner_id=scope.owner_id,
        email=None,
        issued_at=0,
        authenticated=True,
    )
    definition = default_application_registry().registration("personal_ai").definition
    policy = definition.context_policy.model_copy(
        update={"external_execution_modes": ("connected_provider",)},
    )
    context = ApplicationContextRequest(
        definition=definition.model_copy(update={"context_policy": policy}),
        scope=RequestScope(
            owner_id=scope.owner_id,
            acting_user_id=scope.actor_id,
            request_id="fixture",
        ),
    )
    conversations = InMemoryConversationRepository()
    messages = InMemoryMessageRepository(conversations)
    cid, now = uuid4(), datetime.now(UTC)
    conversations.create(
        Conversation(
            id=cid,
            owner_id=scope.owner_id,
            title="Synthetic chat",
            created_at=now,
            updated_at=now,
        )
    )
    parent = None
    for index, (role, content) in enumerate(
        (
            (MessageRole.USER, "A previous synthetic question"),
            (MessageRole.ASSISTANT, "A previous synthetic answer"),
        )
    ):
        timestamp = now - timedelta(seconds=2 - index)
        parent = messages.create(
            Message(
                id=uuid4(),
                conversation_id=cid,
                owner_id=scope.owner_id,
                parent_message_id=parent,
                role=role,
                content=content,
                status=MessageStatus.COMPLETED,
                created_at=timestamp,
            )
        ).id

    fallback = []

    class Fallback:
        def stream_events(self, *args, **kwargs):
            fallback.append("stream")
            raise AssertionError("unexpected fallback")

    chat = ChatTurnService(
        conversations,
        messages,
        Fallback(),
        owner_id=scope.owner_id,
        application_context=context,
        model="synthetic-fallback",
        context_assembler=ContextAssembler(
            Settings(ai_provider="fake", ai_model="synthetic-local-model"),
            EstimatedTokenCounter(),
        ),
    )
    wire = CHATGPT_PLAN_PROFILE.model_copy(update={"external_transport_id": "chatgpt_local_v1"})
    registered_profile = profile().model_copy(
        update={
            "deployment_id": wire.deployment_id,
            "endpoint_id": wire.endpoint_id,
            "serializer_id": wire.serializer_id,
            "runtime_id": wire.runtime_id,
        }
    )
    gate = next(iter(bridge.gates.values())).model_copy(update={"execution_profile": wire})
    bridge.gates = {gate.key: gate}
    bridge.provider = ChatGPTResponses(
        transport=provider.provider.transport,
        supported_profiles=(wire,),
    )
    service = ExternalTurnService(
        chat=chat,
        context=context,
        registry=EndpointRegistry([registered_profile]),
        authority=PrincipalBoundExternalTurnAuthority(
            principal=principal,
            conversations=conversations,
            messages=messages,
            permission_revalidator=None,
        ),
        signer=DispatchGrantSigner(
            issuer=bridge.verifier.issuer,
            key_id="key-v1",
            key=key,
        ),
        local_chat=LocalChatDispatch(
            scope,
            session.caller_id,
            bridge.verifier.audience,
            session.connection_id,
            session.connection_revision,
        ),
    )
    request = ContinuationRequest(
        content="An explicit synthetic follow-up",
        idempotency_key=uuid4(),
        choice=ExecutionChoice(
            mode="connected_provider",
            endpoint=wire.endpoint,
            model_id="account-visible-model",
            caller_id=session.caller_id,
            audience=bridge.verifier.audience,
            connection_id=session.connection_id,
            connection_revision=session.connection_revision,
        ),
    )
    return service, cid, request, bridge, provider, session, fallback


@pytest.mark.parametrize("terminal", ["success", "lost"])
def test_foreground_turn_uses_shared_history_and_one_durable_send(local_turn, terminal):
    service, cid, request, bridge, provider, session, fallback = local_turn
    # Exercise the real refresh/JWKS validators independently of the Responses fixture.
    oauth = OAuthFixture()
    bridge.lifecycle.oauth = oauth.oauth
    with bridge.lifecycle.store.transaction() as tx:
        tx.state.registrations[str(session.connection_id)].credentials.expires_at = 1
        tx.save()
    if terminal == "lost":
        provider.events = [created(), delta("transient partial answer")]

    prepared = service.prepare(cid, request)
    assert len(prepared.reservation.source_message_ids) == 3
    assert not prepared.reservation.source_snapshots
    assert prepared.context_package.input_tokens > 0
    assert not oauth.requests and not provider.requests
    proof = service.dispatch_package(cid, prepared.message_id, prepared.connected_package)
    assert proof.claims.local_chat == bridge.installation.scope
    with pytest.raises(ConversationConflictError, match="dispatch_binding_invalid"):
        service.dispatch_package(cid, prepared.message_id, prepared.connected_package)
    events = run_bridge(bridge, session, prepared.connected_package, proof)

    refresh = [item for item in oauth.requests if item.method == "POST"]
    assert len(refresh) == 1
    assert parse_qs(refresh[0].content.decode())["grant_type"] == ["refresh_token"]
    get, post = provider.requests
    assert (get.method, post.method) == ("GET", "POST")
    assert get.headers["authorization"] == post.headers["authorization"]
    assert post.headers["authorization"] != "Bearer synthetic-access"
    body = json.loads(post.content)
    assert set(body) == {"model", "input", "store", "stream"}
    assert [item["content"] for item in body["input"] if item["role"] in {"user", "assistant"}] == [
        "A previous synthetic question",
        "A previous synthetic answer",
        request.content,
    ]

    metadata = events[-1].metadata
    with bridge.lifecycle.store.transaction() as tx:
        receipt = tx.state.receipts[prepared.connected_package.dispatch_identity]
        assert receipt.status == ("success" if terminal == "success" else "send_started")
    if terminal == "success":
        text = "".join(event.delta for event in events if event.kind == "delta")
        message = service.finalize(
            cid,
            prepared.message_id,
            prepared.reservation.package_fingerprint,
            ExternalCompletion(text, metadata.provenance, metadata),
        )
        assert message.execution.state == "completed" and message.content == text
    else:
        assert metadata.error_code == "bridge_terminal_missing"
        message = service.abandon(
            cid, prepared.message_id, prepared.reservation.package_fingerprint
        )
        assert message.execution.state == "unknown" and not message.content
        with pytest.raises(ConversationConflictError, match="previous_dispatch_uncertain"):
            service.prepare(cid, request.model_copy(update={"idempotency_key": uuid4()}))
    assert len(provider.sends()) == 1 and not fallback


def test_issuer_requires_paired_foreground_principal_and_denies_explicit_sources(local_turn):
    service, cid, request, bridge, provider, _, fallback = local_turn
    other_caller = request.choice.model_copy(update={"caller_id": uuid4()})
    with pytest.raises(ConversationConflictError, match="local_chat_scope_denied"):
        service.prepare(cid, request.model_copy(update={"choice": other_caller}))
    with pytest.raises(ConversationConflictError, match="source_context_denied"):
        service.prepare(cid, request.model_copy(update={"retrieval_context": True}))
    service.local_chat = None
    with pytest.raises(ConversationConflictError, match="local_chat_execution_unavailable"):
        service.prepare(cid, request)
    assert (
        len(
            service.authority.messages.list_active(
                owner_id=service.context.scope.owner_id,
                conversation_id=cid,
            )
        )
        == 2
    )
    assert not provider.requests and not fallback
    assert [call for call in bridge.lifecycle.oauth.calls if call[0] == "refresh"] == []


def test_preview_uses_source_free_snapshot_for_inherited_active_history(local_turn):
    service, cid, request, _bridge, provider, _session, fallback = local_turn

    clean = service.preview(cid, request)
    assert clean["selected_message_count"] == 2
    assert not provider.requests and not fallback

    active = service.authority.messages.list_active(
        owner_id=service.context.scope.owner_id,
        conversation_id=cid,
    )
    assistant = next(message for message in active if message.role == MessageRole.ASSISTANT)
    snapshot = ContextSourceSnapshot(
        provider_id="synthetic.source",
        source_id="record",
        source_version="v1",
        item_id="item",
        owner_id=assistant.owner_id,
        application_id=assistant.application_id,
        workspace_id=None,
        operation="current",
        content_fingerprint="a" * 64,
    )
    service.authority.messages._messages[assistant.id] = assistant.model_copy(
        update={
            "attribution": TurnAttribution(
                fact_source="server_observed",
                execution_origin="automatic_managed",
                provider_id="synthetic-provider",
                model_id="synthetic-model",
                recorded_at=datetime.now(UTC),
                source_snapshots=(snapshot,),
            )
        }
    )

    with pytest.raises(ConversationConflictError, match="local_chat_source_context_denied"):
        service.preview(cid, request)

    service.authority.messages._messages[assistant.id] = assistant.model_copy(
        update={
            "attribution": None,
            "execution": TurnReservation(
                reservation_id=uuid4(),
                request_digest="b" * 64,
                mode="manual_external",
                state="completed",
                package_fingerprint="c" * 64,
                branch_digest="d" * 64,
                authority_digest="e" * 64,
                policy_version="legacy-memory-turn",
                effective_sensitivity="personal",
                expires_at=datetime.now(UTC),
                max_output_bytes=100,
                completion_digest="f" * 64,
                selected_memory_ids=(uuid4(),),
            ),
        }
    )
    with pytest.raises(ConversationConflictError, match="local_chat_source_context_denied"):
        service.preview(cid, request)
    assert not provider.requests and not fallback


def test_issuer_rechecks_inherited_application_provenance_before_signing(local_turn):
    service, cid, request, _, provider, _, _ = local_turn
    prepared = service.prepare(cid, request)
    assistant_id = prepared.reservation.source_message_ids[1]
    messages = service.authority.messages
    assistant = service.chat.get_message(cid, assistant_id)
    assert assistant.role == MessageRole.ASSISTANT
    snapshot = ContextSourceSnapshot(
        provider_id="synthetic.source",
        source_id="record",
        source_version="v1",
        item_id="item",
        owner_id=assistant.owner_id,
        application_id=assistant.application_id,
        workspace_id=None,
        operation="current",
        content_fingerprint="a" * 64,
    )
    # Model a prior turn whose application provenance became visible after preparation.
    messages._messages[assistant_id] = assistant.model_copy(
        update={
            "attribution": TurnAttribution(
                fact_source="server_observed",
                execution_origin="automatic_managed",
                provider_id="synthetic-provider",
                model_id="synthetic-model",
                recorded_at=datetime.now(UTC),
                source_snapshots=(snapshot,),
            ),
        }
    )
    with pytest.raises(ConversationConflictError, match="local_chat_source_context_denied"):
        service.dispatch_package(cid, prepared.message_id, prepared.connected_package)
    assert service.chat.get_message(cid, prepared.message_id).execution.state == "prepared"
    assert not provider.requests


@pytest.mark.parametrize(
    ("missing", "revoked_fact", "hidden_model"),
    [
        (None, None, False),
        (None, "owner_policy", False),
        (None, "route_grant", False),
        (None, "consent", False),
        (None, "before_fence", False),
        (None, "quarantine", False),
        (None, "unconfirmed", False),
        (None, None, True),
        ("consent", None, False),
        ("program", None, False),
        ("account", None, False),
        ("included_only", None, False),
        ("weekly_cap", None, False),
        ("quota", None, False),
        ("credit_risk", None, False),
    ],
)
def test_policy_offer_fences_before_publication_and_stays_local(
    local_turn, missing, revoked_fact, hidden_model, monkeypatch, caplog
):
    from contextlib import ExitStack

    from personal_ai.auth.scope import (
        bind_request_scope,
        bind_verified_principal,
        reset_request_scope,
        reset_verified_principal,
    )
    from personal_ai.routing import RoutingDecisionService
    from personal_ai.routing.isolated import (
        IsolatedInferenceRouting,
        PlanOfferEvidence,
        SyntheticOffer,
    )
    from personal_ai.routing.owner_policy import OwnerInferenceSettings, PolicyDenied
    from tests.test_isolated_inference import Authority, MemorySettings, binding, policy
    from tests.test_routing_decision_lifecycle import MemoryRepository, task
    from tests.test_routing_decision_lifecycle import request as route_request

    issuer, _, continuation, bridge, provider, session, fallback = local_turn
    cid, now = uuid4(), datetime.now(UTC)
    issuer.authority.conversations.create(
        Conversation(
            id=cid, owner_id=issuer.context.scope.owner_id, title="Public fixture",
            created_at=now, updated_at=now,
        )
    )
    continuation = continuation.model_copy(update={"content": FOREGROUND_PROMPT})
    registered = issuer.registry.profiles[0].model_copy(
        update={
            "model_id": continuation.choice.model_id,
            "credential_scope_id": "fixture-local-revision",
            "account_scope_id": "fixture-local-account",
        }
    )
    issuer.registry = EndpointRegistry([registered])
    exact = binding(registered, "subscription")
    prepared = issuer.prepare(cid, continuation)
    assert not prepared.reservation.source_snapshots
    assert not prepared.reservation.selected_memory_ids
    document = continuation.model_dump(mode="json")
    for key in ("federation_context", "launch_context", "retrieval_context"):
        document.pop(key)
    payload = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    store = MemorySettings()

    class LocalAuthority(Authority):
        admission = None
        offer_evidence = None

        def plan_offer(self, connection, admission, package, choice, now):
            self.admission = admission
            self.offer_evidence = PlanOfferEvidence(
                exact,
                prepared.connected_package.fingerprint,
                continuation.choice.audience,
                continuation.choice.connection_id,
                continuation.choice.connection_revision,
                now + timedelta(minutes=1),
                missing != "consent",
                missing != "program",
                missing != "account",
                missing not in {"included_only", "weekly_cap", "quota", "credit_risk"},
            )
            return self.offer_evidence

    local_authority = LocalAuthority(
        maximum_sensitivity=prepared.connected_package.effective_sensitivity
    )
    coordinator = IsolatedInferenceRouting(
        RoutingDecisionService(issuer.registry, MemoryRepository()),
        OwnerInferenceSettings(store, issuer.registry, is_member=lambda _: False),
        authority=local_authority,
    )
    with ExitStack() as stack:
        stack.callback(reset_request_scope, bind_request_scope(issuer.context.scope))
        stack.callback(
            reset_verified_principal, bind_verified_principal(issuer.authority.principal)
        )
        coordinator.settings.update(
            expected_revision=0, payload=policy(exact).model_dump_json().encode()
        )
        kwargs = {
            "request": route_request().model_copy(
                update={
                    "requirements": route_request().requirements.model_copy(
                        update={"sensitivity": prepared.connected_package.effective_sensitivity}
                    ),
                }
            ),
            "task": task(max_physical_attempts=1),
            "payload": payload,
            "ranked": (exact,),
            "recipient": exact.recipient,
            "prepare_candidate": lambda *_: SyntheticOffer(
                issuer, cid, prepared, continuation.choice
            ),
        }
        if missing is not None:
            with pytest.raises(PolicyDenied):
                coordinator.prepare(**kwargs)
            assert not provider.requests
            return
        grant = coordinator.prepare(**kwargs)
        root = next(iter(store.roots.values()))
        assert root[4] == "fenced"
        assert (grant.claims.routing_root, issuer.context.scope.owner_id) in store.roots
        assert grant.claims.expires_at <= int(root[2].timestamp())
        assert grant.claims.local_chat == bridge.installation.scope
        with pytest.raises(PolicyDenied, match="fenced"):
            coordinator.prepare(**kwargs)
    assert not provider.requests

    owner_confirmed = False
    installation_current = revoked_fact != "quarantine"
    paired_session = session

    class CurrentRootAuthority:
        def authorize(self, *, root_id, package, claims, installation, session):
            now = datetime.now(UTC)
            try:
                coordinator.require_authority(None, local_authority.admission, now)
            except PolicyDenied:
                return False
            evidence = local_authority.offer_evidence
            return (
                owner_confirmed
                and installation_current
                and session == paired_session
                and claims == grant.claims
                and evidence is not None
                and evidence.matches(
                    local_authority.admission, package, continuation.choice
                )
                and evidence.eligible(now)
                and root_id == grant.claims.routing_root
                and claims.routing_root == root_id
                and package.fingerprint == prepared.connected_package.fingerprint
                and package.owner_id == issuer.context.scope.owner_id
                and package.application_id == issuer.context.scope.application_id
                and package.workspace_id == issuer.context.scope.workspace_id
                and package.model_id == grant.claims.model_id
                and package.execution_profile.endpoint == continuation.choice.endpoint
                and claims.package_hash == package.fingerprint
                and claims.connection_id == installation.connection_id
                and package.connection_revision == installation.connection_revision
                and session.connection_id == installation.connection_id
                and claims.local_chat == installation.scope
                and claims.local_chat.actor_id == installation.scope.actor_id
            )

    root_authority = CurrentRootAuthority()
    bridge.root_authority = root_authority
    def dispatch():
        return run_bridge(
            bridge, session, prepared.connected_package, grant,
            foreground_root=grant.claims.routing_root,
        )

    snapshots = []
    snapshot = bridge.lifecycle.snapshot
    oauth = bridge.lifecycle.oauth
    oauth_before = list(oauth.calls)

    def count_snapshot(*args, **kwargs):
        snapshots.append("snapshot")
        return snapshot(*args, **kwargs)

    monkeypatch.setattr(bridge.lifecycle, "snapshot", count_snapshot)
    with pytest.raises(BridgeDenied, match="admission_denied"):
        dispatch()
    assert not snapshots and not provider.requests and oauth.calls == oauth_before
    if revoked_fact == "unconfirmed":
        return
    owner_confirmed = True
    if revoked_fact == "owner_policy":
        with ExitStack() as stack:
            stack.callback(reset_request_scope, bind_request_scope(issuer.context.scope))
            stack.callback(
                reset_verified_principal, bind_verified_principal(issuer.authority.principal)
            )
            coordinator.settings.update(
                expected_revision=1, payload=policy().model_dump_json().encode()
            )
    elif revoked_fact == "route_grant":
        local_authority.active = False
    elif revoked_fact == "consent":
        from dataclasses import replace

        local_authority.offer_evidence = replace(
            local_authority.offer_evidence, owner_plan_consent=False
        )
    if revoked_fact == "before_fence":
        mark = bridge.lifecycle.store.mark_send_started

        def revoke_before_fence(*args, **kwargs):
            nonlocal owner_confirmed
            owner_confirmed = False
            return mark(*args, **kwargs)

        monkeypatch.setattr(bridge.lifecycle.store, "mark_send_started", revoke_before_fence)

    if revoked_fact is not None:
        with pytest.raises(BridgeDenied, match="admission_denied"):
            dispatch()
        expected = ["GET"] if revoked_fact == "before_fence" else []
        assert [req.method for req in provider.requests] == expected
        assert len(snapshots) == len(expected) and oauth.calls == oauth_before
        assert root[4] == "fenced"
        with bridge.lifecycle.store.transaction() as tx:
            assert prepared.connected_package.dispatch_identity not in tx.state.receipts
        return

    if hidden_model:
        provider.catalog = []
        with pytest.raises(BridgeDenied, match="model_unavailable"):
            dispatch()
        assert [req.method for req in provider.requests] == ["GET"]
        return

    package = prepared.connected_package
    assert grant.claims.schema_version == 1 and grant.claims.application_plan is None
    assert grant.claims.key_id == bridge.installation.signer_key_id
    store = bridge.lifecycle.store
    state = store.directory / "state.json"
    fence = store.directory / "send-fences" / package.dispatch_identity
    before = state.read_bytes()
    send = provider.handle

    def after_fence(request):
        if request.method == "POST":
            assert fence.is_file()
            assert json.loads(state.read_bytes())["receipts"][package.dispatch_identity][
                "status"
            ] == "send_started"
        return send(request)

    monkeypatch.setattr(bridge.provider.transport, "handler", after_fence)
    events = dispatch()
    assert events[-1].metadata.status == "success"
    get, post = provider.requests
    assert str(get.url) == "https://api.openai.com/v1/models"
    assert str(post.url) == "https://api.openai.com/v1/responses"
    body = json.loads(post.content)
    assert set(body) == {"input", "model", "store", "stream"}
    assert body["store"] is False and body["stream"] is True
    assert body["model"] == continuation.choice.model_id
    assert [item for item in body["input"] if item["role"] != "developer"] == [
        {"role": "user", "content": FOREGROUND_PROMPT}
    ]
    assert "previous synthetic" not in post.content.decode()
    recorded = state.read_text() + fence.read_text() + caplog.text
    assert FOREGROUND_PROMPT not in recorded and "A streamed answer" not in recorded
    # The state file also contains credentials by design. Inspect the receipt separately.
    receipt = json.loads(state.read_bytes())["receipts"][package.dispatch_identity]
    assert receipt["status"] == "success"
    for secret in ("synthetic-access", "synthetic-refresh", session.authorization):
        assert secret not in json.dumps(receipt) + fence.read_text() + caplog.text
    assert len(snapshots) == 1 and oauth.calls == oauth_before
    text = "".join(event.delta for event in events if event.kind == "delta")
    message = issuer.finalize(
        cid, prepared.message_id, prepared.reservation.package_fingerprint,
        ExternalCompletion(text, events[-1].metadata.provenance, events[-1].metadata),
    )
    assert message.execution.state == "completed" and message.content == text

    # Roll back only receipts, with the independent fence still present.
    state.write_bytes(before)
    bridge.lifecycle.store = ProtectedLocalStore(store.directory)
    with pytest.raises(LocalStoreError, match="dispatch_already_claimed"):
        dispatch()
    assert [req.method for req in provider.requests] == ["GET", "POST", "GET"]
    assert not fallback
