"""Synthetic local source-to-normal-turn tests, including retained disclosure."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from personal_ai.applications.contracts import (
    ApplicationContextPolicy,
    ApplicationContextRequest,
    ApplicationDefinition,
    CapabilityRegistration,
    ContextFieldPolicy,
    ContextOperationPolicy,
    ContextProviderPolicy,
)
from personal_ai.auth.account_data import AccountDataUnavailable
from personal_ai.auth.scope import ApplicationScope, application_scope_context
from personal_ai.context import ContextAssembler
from personal_ai.context.authority import source_snapshots_current
from personal_ai.context.history import (
    conversation_context_messages,
    memory_extraction_context_reason,
)
from personal_ai.context.providers import ContextProviderCoordinator
from personal_ai.context.tokens import EstimatedTokenCounter
from personal_ai.contracts.execution import ContinuationRequest, ContinuationRequestPayload
from personal_ai.entities import Conversation
from personal_ai.llm.fake import FakeLLMClient
from personal_ai.retrieval.context import (
    RetrievalContextAuthority,
    RetrievalContextProviderFactory,
)
from personal_ai.retrieval.export import require_export_safe
from personal_ai.services import ChatTurnService, ConversationService
from personal_ai.services.conversations import ExternalHistoryDisclosureDenied
from personal_ai.settings import Settings
from personal_ai.storage import InMemoryConversationRepository, InMemoryMessageRepository

from .test_retrieval_integrations import access, document, install, scope


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def application_scope():
    with application_scope_context(ApplicationScope(application_id="reader", workspace_id="shelf")):
        yield


@pytest.fixture
def runtime(tmp_path):
    s = scope()
    path = tmp_path / "source.json"
    install(
        path, model_context_access=[access(s)], documents=[document(model_context_allowed=True)]
    )
    settings = Settings(
        _env_file=None,
        ai_provider="fake",
        ai_model="test",
        app_environment="test",
        retrieval_enabled=True,
        retrieval_context_enabled=True,
        retrieval_installation_file=str(path),
    )
    base = ApplicationContextPolicy()
    context = ApplicationContextRequest(
        definition=ApplicationDefinition(
            application_id=s.application_id,
            display_name="Reader",
            memory_namespace="reader",
            workspace_kind="required",
            context_provider_ids=("retrieval_context",),
            context_policy=base.model_copy(
                update={
                    "provider_policies": (
                        *base.provider_policies,
                        ContextProviderPolicy(
                            provider_id="retrieval_context",
                            operations=(
                                ContextOperationPolicy(
                                    operation="search",
                                    sensitivity="sensitive",
                                    fields=(
                                        ContextFieldPolicy(
                                            field="excerpt", sensitivity="sensitive"
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    )
                }
            ),
        ),
        scope=s,
        context_provider_capabilities=(
            CapabilityRegistration(
                capability_id="conversation_history", kind="context_provider", available=True
            ),
            CapabilityRegistration(
                capability_id="retrieval_context", kind="context_provider", available=True
            ),
        ),
    )
    r = SimpleNamespace(
        path=path,
        settings=settings,
        context=context,
        scope=s,
        revoked=False,
        counts=[],
        guard_calls=0,
    )

    def authority():
        r.guard_calls += 1
        if r.revoked:
            raise ValueError("owner_deleted")

    validator = RetrievalContextAuthority(
        settings, scope=s, authority=authority, context=lambda: r.context
    )
    assembler = ContextAssembler(
        settings,
        EstimatedTokenCounter(),
        context_provider_coordinator=ContextProviderCoordinator(
            {
                "retrieval_context": RetrievalContextProviderFactory(validator),
            }
        ),
        permission_revalidator=validator,
    )
    conversations = InMemoryConversationRepository()
    messages = InMemoryMessageRepository(conversations)
    conversation = conversations.create(
        Conversation(
            id=uuid4(),
            owner_id=s.owner_id,
            application_id=s.application_id,
            workspace_id=s.workspace_id,
            title="Test",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    llm = FakeLLMClient(("A synthetic answer.",))
    service = ChatTurnService(
        conversations,
        messages,
        llm,
        owner_id=s.owner_id,
        application_context=context,
        model="fake",
        context_assembler=assembler,
    )
    r.validator, r.assembler, r.service = validator, assembler, service
    r.conversation, r.conversations, r.messages, r.llm = conversation, conversations, messages, llm
    return r


def request(**changes):
    return ContinuationRequest(
        content="Atlas", idempotency_key=uuid4(), retrieval_context=True, **changes
    )


async def complete(r, body=None):
    body = body or request()
    events = [event async for event in r.service.continue_turn(r.conversation.id, body)]
    return body, events


@pytest.mark.anyio
async def test_normal_turn_packs_exact_quote_and_retains_authority(runtime):
    r = runtime
    body, events = await complete(r)
    assert events[-1].__class__.__name__ == "TurnCompleted"
    sent = r.llm.requests[0]
    assert "Atlas is a book" in str(sent) and "invoke memory.forget" in str(sent)
    completed = events[-1].message
    snapshots = completed.attribution.source_snapshots
    assert len(snapshots) == 1 and snapshots[0].provider_id == "retrieval_context"
    assert snapshots[0].permission_dependencies[0].source_revision == "1"
    assert memory_extraction_context_reason(completed) == "context_source_not_reusable"
    assert r.guard_calls > 3
    replay = [event async for event in r.service.continue_turn(r.conversation.id, body)]
    assert replay[-1].__class__.__name__ == "TurnCompleted" and len(r.llm.requests) == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "change", ["revoke", "delete", "revision", "grant", "issuer", "kill", "owner"]
)
async def test_retained_output_detail_replay_history_and_export_deny(runtime, change):
    r = runtime
    body, events = await complete(r)
    completed = events[-1].message
    if change == "delete":
        r.path.unlink()
    elif change == "kill":
        r.settings.retrieval_context_enabled = False
    elif change == "owner":
        r.revoked = True
    else:
        value = json.loads(r.path.read_text())
        if change == "revoke":
            value["documents"][0]["model_context_allowed"] = False
        elif change == "revision":
            value["documents"][0]["revision"] = "2"
        elif change == "grant":
            value["model_context_access"] = []
        elif change == "issuer":
            value["issuer_id"] = str(uuid4())
        r.path.write_text(json.dumps(value))
    assert not source_snapshots_current(
        completed.attribution.source_snapshots, r.validator, now=datetime.now(UTC)
    )
    replay = [event async for event in r.service.continue_turn(r.conversation.id, body)]
    assert replay[-1].__class__.__name__ == "TurnFailed" and len(r.llm.requests) == 1
    assert all("Atlas" not in str(event) for event in replay)
    history = r.messages.list_active(owner_id=r.scope.owner_id, conversation_id=r.conversation.id)
    assert not conversation_context_messages(
        history,
        manual_import_reuse=r.context.definition.context_policy.sidecar.manual_import_reuse,
        permission_revalidator=r.validator,
        check_source_permissions=True,
    )
    detail = ConversationService(
        r.conversations, r.messages, owner_id=r.scope.owner_id, application_context=r.context
    )
    with pytest.raises(ExternalHistoryDisclosureDenied):
        detail.get_conversation(r.conversation.id, permission_revalidator=r.validator)
    with pytest.raises(AccountDataUnavailable):
        require_export_safe(
            {"collections": {"messages": [{"data": completed.model_dump(mode="json")}]}}
        )


@pytest.mark.anyio
@pytest.mark.parametrize("change", ["owner_id", "acting_user_id", "application_id", "workspace_id"])
async def test_retained_dependency_bound_to_exact_actor_scope(runtime, change):
    r = runtime
    _, events = await complete(r)
    dependency = events[-1].message.attribution.source_snapshots[0].permission_dependencies[0]
    foreign = scope(**{change: "foreign"})
    validator = RetrievalContextAuthority(
        r.settings, scope=foreign, authority=lambda: None, context=r.context
    )
    assert not validator.is_current(dependency)


@pytest.mark.anyio
async def test_revocation_during_packed_count_sends_nothing(runtime):
    r = runtime

    class Counter(EstimatedTokenCounter):
        def count(self, messages):
            from personal_ai.llm.disclosure import revalidate_disclosure

            if "Atlas is a book" in str(messages):
                r.revoked = True
            revalidate_disclosure()
            return super().count(messages)

    r.assembler.counter = Counter()
    with pytest.raises(
        Exception, match="context_source_authority_changed|context_source_unavailable"
    ):
        await complete(r)
    assert not r.llm.requests


@pytest.mark.anyio
async def test_revocation_after_preparation_before_model_send(runtime):
    r = runtime
    iterator = r.service.continue_turn(r.conversation.id, request())
    r.revoked = True
    events = [event async for event in iterator]
    assert events[-1].__class__.__name__ == "TurnFailed" and not r.llm.requests


@pytest.mark.anyio
async def test_defaults_and_interactive_quote_grant_do_not_allow_model_context(runtime):
    r = runtime
    value = json.loads(r.path.read_text())
    value["model_context_access"] = []
    r.path.write_text(json.dumps(value))
    with pytest.raises(Exception, match="context"):
        await complete(r)
    assert not r.llm.requests
    assert not Settings(
        _env_file=None, ai_provider="fake", ai_model="test"
    ).retrieval_context_enabled


def test_additive_request_intent_keeps_original_digest():
    body = request()
    assert (
        ContinuationRequestPayload.model_validate(
            body.model_dump(exclude={"federation_context"})
        ).to_internal_request()
        == body
    )
    plain = body.model_copy(update={"retrieval_context": False})
    from hashlib import sha256

    payload = plain.model_dump(mode="json")
    for key in ("retrieval_context", "launch_context", "federation_context"):
        payload.pop(key)
    assert (
        plain.intent_digest
        == sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
    )
    assert body.intent_digest != plain.intent_digest


@pytest.mark.anyio
@pytest.mark.parametrize("profile", ["offline_fake", "offline_fake_alt"])
async def test_shared_execution_pair_exact_count_and_one_send(runtime, profile):
    from personal_ai.llm.execution import compose_pair

    r = runtime
    r.settings.inference_profile = profile
    pair = compose_pair(r.settings)
    r.assembler.counter = pair.counter
    r.service._llm = pair.generator
    body, events = await complete(r)
    assert events[-1].__class__.__name__ == "TurnCompleted"
    assert "Atlas is a book" in str(pair.generator.delegate.requests[0])
    assert pair.counter.identity == pair.generator.identity
    await complete(r, body)
    assert len(pair.generator.delegate.requests) == 1


@pytest.mark.anyio
async def test_revocation_during_sse_and_failed_partial_body_is_not_retained(runtime):
    from personal_ai.llm import GenerationEvent

    r = runtime

    class RevokingModel(FakeLLMClient):
        async def stream_events(self, *args, **kwargs):
            async for event in super().stream_events(*args, **kwargs):
                if event.kind == "delta":
                    yield event
                    r.revoked = True
                    yield GenerationEvent.text_delta("Atlas private continuation")
                else:
                    yield event

    r.service._llm = RevokingModel(("Atlas private partial",))
    _, events = await complete(r)
    assert events[-1].__class__.__name__ == "TurnFailed"
    assert not any(getattr(event, "delta", "") == "Atlas private continuation" for event in events)
    failed = r.messages.list_active(owner_id=r.scope.owner_id, conversation_id=r.conversation.id)[
        -1
    ]
    assert failed.status.value == "failed" and not failed.content


@pytest.mark.anyio
async def test_summary_inherits_rights_and_expiry(runtime):
    from personal_ai.context.contracts import ConversationSummary, fingerprint
    from personal_ai.context.history import summary_authority_snapshot

    r = runtime
    _, events = await complete(r)
    history = r.messages.list_active(owner_id=r.scope.owner_id, conversation_id=r.conversation.id)
    summary = ConversationSummary(
        id=uuid4(),
        owner_id=r.scope.owner_id,
        conversation_id=r.conversation.id,
        application_id=r.scope.application_id,
        workspace_id=r.scope.workspace_id,
        content="Atlas private summary",
        source_message_ids=tuple(m.id for m in history),
        source_fingerprint=fingerprint(history),
        covers_through_message_id=history[-1].id,
        source_token_count=100,
        summary_token_count=10,
        counter_kind="estimated",
        model="synthetic",
        created_at=datetime.now(UTC),
    )
    snapshot = summary_authority_snapshot(summary, history)
    assert (
        snapshot.permission_dependencies
        == events[-1].message.attribution.source_snapshots[0].permission_dependencies
    )
    assert snapshot.expires_at is not None
    r.revoked = True
    assert not source_snapshots_current((snapshot,), r.validator, now=datetime.now(UTC))


@pytest.mark.anyio
async def test_missing_validator_or_missing_retrieval_provenance_denies(runtime):
    r = runtime
    _, events = await complete(r)
    snapshot = events[-1].message.attribution.source_snapshots[0]
    assert not source_snapshots_current((snapshot,), None, now=datetime.now(UTC))
    assert not source_snapshots_current(
        (snapshot.model_copy(update={"permission_dependencies": ()}),),
        r.validator,
        now=datetime.now(UTC),
    )
