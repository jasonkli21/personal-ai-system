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
from tests.test_chatgpt_bridge_transport import bridge_fixture, created, delta, run_bridge
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
