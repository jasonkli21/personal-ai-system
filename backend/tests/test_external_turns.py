"""Phase 25.2 synthetic state-machine, provenance, policy and concurrency acceptance."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from personal_ai.api.chat_stream import sse_frames
from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.applications.registry import default_application_registry
from personal_ai.auth.dispatch_grants import DispatchGrantVerifier
from personal_ai.auth.scope import ApplicationScope, RequestScope, application_scope_context
from personal_ai.context import ContextAssembler
from personal_ai.context.tokens import EstimatedTokenCounter
from personal_ai.entities import Conversation, MessageStatus
from personal_ai.entities.turn_execution import TurnAttribution
from personal_ai.llm.client import (
    ExecutionProvenance,
    ExternalCompletion,
    GenerationMetadata,
    ProviderIdentity,
)
from personal_ai.local_bridge.status import CoarseUsage, usage_observation
from personal_ai.routing.contracts import (
    DataUsePolicy,
    EndpointCandidateRequirements,
    EndpointProfile,
    ProviderAccessPolicy,
)
from personal_ai.routing.registry import EndpointRegistry
from personal_ai.services.chat.service import ChatTurnService
from personal_ai.services.external_turns import (
    ContinuationRequest,
    DispatchGrantSigner,
    ExecutionChoice,
    ExternalTurnService,
)
from personal_ai.settings import Settings
from personal_ai.storage import InMemoryConversationRepository, InMemoryMessageRepository
from personal_ai.storage.errors import ConversationConflictError, ResourceNotFoundError


class Authority:
    def __init__(self):
        self.version = "a" * 64
        self.denied = set()
        self.calls = []

    def snapshot(
        self,
        context,
        conversation_id,
        choice,
        source_message_ids,
        source_snapshots,
    ):
        self.calls.append((choice.mode, source_message_ids))
        if set(source_message_ids) & self.denied:
            raise ConversationConflictError("source_revoked")
        return self.version


def profile(provider="openai_chatgpt_plan", execution_mode="CHATGPT_PLAN"):
    plan_execution = execution_mode == "CHATGPT_PLAN"
    return EndpointProfile(
        endpoint_profile_id=f"{provider}:responses",
        profile_version=1,
        provider_id=provider,
        model_id="model-1",
        endpoint_id="responses-v1",
        deployment_id="synthetic-v1",
        credential_source="user_runtime",
        credential_reference="user_runtime:local",
        tier_id="subscription",
        execution_mode=execution_mode,
        cost_class="SUBSCRIPTION" if plan_execution else "USER_BILLED",
        billing_owner="subscription" if plan_execution else "user",
        enabled=True,
        capabilities=frozenset({"streaming"}),
        context_limit_tokens=10000,
        serializer_id="synthetic-v1",
        runtime_id="synthetic-v1",
        external_transport_id="chatgpt_local_v1" if plan_execution else None,
        data_use_policy=DataUsePolicy(
            status="approved", max_sensitivity="sensitive", policy_reference="fixture"
        ),
        access_policy=ProviderAccessPolicy(
            auth_mode="oauth_public_client",
            selection_mode="explicit_only",
            credential_runtime="user_local",
            model_discovery="account_specific",
            automation_eligible=False,
        ),
    )


@pytest.fixture
def setup():
    registration = default_application_registry().registration("personal_ai")
    definition = registration.definition.model_copy(
        update={
            "context_policy": registration.definition.context_policy.model_copy(
                update={"external_execution_modes": ("connected_provider", "manual_external")}
            )
        }
    )
    context = ApplicationContextRequest(
        definition=definition, scope=RequestScope(owner_id="local", request_id="external-test")
    )
    conversations = InMemoryConversationRepository()
    messages = InMemoryMessageRepository(conversations)
    now = datetime.now(UTC)
    conversation = conversations.create(
        Conversation(id=uuid4(), owner_id="local", title="External", created_at=now, updated_at=now)
    )
    chat = ChatTurnService(
        conversations,
        messages,
        None,
        owner_id="local",
        model="fixture",
        application_context=context,
        context_assembler=ContextAssembler(
            Settings(ai_provider="fake", ai_model="fixture"), EstimatedTokenCounter()
        ),
    )
    key = Ed25519PrivateKey.generate()
    authority = Authority()
    registry = EndpointRegistry(
        [
            profile(),
            profile("another_provider"),
            profile("local_byok", execution_mode="EXPLICIT_BYOK"),
        ]
    )
    clock = [now]
    service = ExternalTurnService(
        chat=chat,
        context=context,
        registry=registry,
        authority=authority,
        signer=DispatchGrantSigner(issuer="fixture", key_id="key", key=key),
        clock=lambda: clock[0],
    )
    return service, conversation.id, messages, authority, key, clock


def choice(mode, provider="openai_chatgpt_plan"):
    if mode == "manual_external":
        return ExecutionChoice(mode=mode)
    return ExecutionChoice(
        mode=mode,
        endpoint=profile(provider).ref,
        model_id="account-visible-model",
        connection_id=uuid4(),
        connection_revision=1,
        caller_id=uuid4(),
        audience=uuid4(),
    )


def test_legacy_attribution_modes_decode_to_one_canonical_execution_origin():
    recorded_at = datetime.now(UTC)
    manual = TurnAttribution.model_validate({
        "mode": "manual_external",
        "fact_source": "user_declared",
        "recorded_at": recorded_at,
    })
    automatic = TurnAttribution.model_validate({
        "mode": "connected_provider",
        "fact_source": "server_observed",
        "provider_id": "gemini",
        "model_id": "gemini-fixture",
        "recorded_at": recorded_at,
    })
    connected = TurnAttribution.model_validate({
        "mode": "connected_provider",
        "fact_source": "client_reported",
        "provider_id": "openai_chatgpt_plan",
        "model_id": "gpt-fixture",
        "connection_id": uuid4(),
        "connection_revision": 1,
        "recorded_at": recorded_at,
    })

    assert manual.execution_origin == "manual_import"
    assert automatic.execution_origin == "automatic_managed"
    assert connected.execution_origin == "connected_local"
    assert all("mode" not in item.model_dump() for item in (manual, automatic, connected))


def prepare(
    setup, mode="manual_external", *, provider="openai_chatgpt_plan", candidates=None, key=None
):
    service, cid, *_ = setup
    selected = choice(mode, provider)
    request = ContinuationRequest(
        content="Continue reasoning",
        idempotency_key=key or uuid4(),
        choice=selected,
        candidate_message_ids=candidates,
    )
    return service.prepare(cid, request), selected, request


def completion(prepared, text="External answer", *, provider=None, model=None):
    r = prepared.reservation
    p = ExecutionProvenance(
        mode=r.mode,
        fact_source="user_declared" if r.mode == "manual_external" else "bridge_observed",
        provider_id=provider if r.mode == "manual_external" else r.provider_id,
        model_id=model if r.mode == "manual_external" else r.model_id,
        connection_id=str(r.connection_id) if r.connection_id else None,
    )
    g = (
        None
        if r.mode == "manual_external"
        else GenerationMetadata(
            status="success",
            identity=ProviderIdentity(r.provider_id, r.model_id, "synthetic-v1"),
            provenance=p,
        )
    )
    return ExternalCompletion(text=text, provenance=p, generation=g)


def finish(setup, prepared, selected):
    service, cid, *_ = setup
    if prepared.connected_package:
        service.dispatch(cid, prepared, selected)
    return service.finalize(
        cid,
        prepared.message_id,
        prepared.reservation.package_fingerprint,
        completion(prepared),
        explicit_import=prepared.reservation.mode == "manual_external",
    )


def test_manual_has_no_connected_facts_and_replays(setup):
    service, cid, messages, *_ = setup
    prepared, selected, request = prepare(setup)
    assert service.chat.get_message(cid, prepared.message_id).status == MessageStatus.PENDING
    assert prepared.connected_package is None
    assert prepared.count_kind == "estimated"
    assert "Continue reasoning" in prepared.portable_prompt
    result = finish(setup, prepared, selected)
    assert result.status == MessageStatus.COMPLETED
    assert result.attribution.fact_source == "user_declared"
    assert result.attribution.model_verified is False
    assert result.attribution.input_tokens is None and result.attribution.latency_ms is None
    assert result.execution.connection_id is None
    assert (
        service.finalize(
            cid,
            result.id,
            prepared.reservation.package_fingerprint,
            completion(prepared),
            explicit_import=True,
        )
        == result
    )
    with pytest.raises(ConversationConflictError, match="replay_changed"):
        service.finalize(
            cid,
            result.id,
            prepared.reservation.package_fingerprint,
            completion(prepared, "different"),
            explicit_import=True,
        )
    with pytest.raises(ConversationConflictError, match="reservation_exists"):
        service.prepare(cid, request)
    assert len(messages.list_active(owner_id="local", conversation_id=cid)) == 2


def test_connected_dispatch_bound_proof_and_fence(setup):
    service, cid, _, _, key, clock = setup
    prepared, selected, _ = prepare(setup, "connected_provider")
    with pytest.raises(ConversationConflictError, match="terminal_or_uncertain"):
        service.finalize(
            cid, prepared.message_id, prepared.reservation.package_fingerprint, completion(prepared)
        )
    proof = service.dispatch(cid, prepared, selected)
    assert prepared.reservation.expires_at - clock[0] == timedelta(minutes=15)
    assert proof.claims.expires_at - proof.claims.issued_at <= 120
    verifier = DispatchGrantVerifier(
        issuer="fixture", keys={"key": key.public_key()}, audience=selected.audience
    )
    verifier.verify(
        proof,
        prepared.connected_package,
        caller_id=selected.caller_id,
        now=int(clock[0].timestamp()),
    )
    with pytest.raises(ConversationConflictError, match="dispatch_binding_invalid"):
        service.dispatch(cid, prepared, selected)
    result = service.finalize(
        cid,
        prepared.message_id,
        prepared.reservation.package_fingerprint,
        completion(prepared),
        latency_ms=10,
    )
    assert result.attribution.fact_source == "client_reported"
    assert result.attribution.latency_ms == 10


def test_manual_import_lifetime_is_separate_from_dispatch_grant_ttl(setup):
    service, cid, _, _, _, clock = setup
    prepared, _, _ = prepare(setup, "manual_external")
    assert prepared.reservation.expires_at - clock[0] == timedelta(hours=24)
    clock[0] += timedelta(minutes=2)
    result = service.finalize(
        cid,
        prepared.message_id,
        prepared.reservation.package_fingerprint,
        completion(prepared),
        explicit_import=True,
    )
    assert result.status is MessageStatus.COMPLETED


def test_bridge_output_chars_match_canonical_message_limit(setup):
    service, cid, *_ = setup
    prepared, selected, _ = prepare(setup, "connected_provider")
    assert prepared.connected_package.max_output_chars == prepared.reservation.max_output_chars == 20000
    service.dispatch(cid, prepared, selected)
    too_long = completion(prepared, "x" * 20001)
    with pytest.raises(ConversationConflictError, match="completion_output_invalid"):
        service.finalize(
            cid,
            prepared.message_id,
            prepared.reservation.package_fingerprint,
            too_long,
        )

    unicode_text = "🙂" * 20000
    result = service.finalize(
        cid,
        prepared.message_id,
        prepared.reservation.package_fingerprint,
        completion(prepared, unicode_text),
    )
    assert len(result.content) == 20000 and len(result.content.encode()) == 80000


@pytest.mark.parametrize(
    "first,second",
    [
        ("manual_external", "connected_provider"),
        ("connected_provider", "manual_external"),
        ("connected_provider", "connected_provider"),
        ("manual_external", "manual_external"),
    ],
)
def test_continuation_new_turn_preserves_producer_and_reauthorizes(setup, first, second):
    _service, cid, messages, authority, *_ = setup
    prior, selected, _ = prepare(setup, first)
    completed = finish(setup, prior, selected)
    next_turn, next_choice, _ = prepare(
        setup, second, provider="another_provider", candidates=(completed.id,)
    )
    assert any(completed.content in m.content for m in next_turn.messages)
    assert completed.id in next_turn.reservation.source_message_ids
    finish(setup, next_turn, next_choice)
    assert messages.get(owner_id="local", conversation_id=cid, message_id=completed.id) == completed
    assert any(completed.id in ids for _, ids in authority.calls)
    authority.denied.add(completed.id)
    with pytest.raises(ConversationConflictError, match="source_revoked"):
        prepare(setup, second, candidates=(completed.id,))


@pytest.mark.parametrize("mode", ["manual_external", "connected_provider"])
def test_foreign_expired_edited_revoked_and_superseded(setup, mode):
    service, cid, messages, authority, _, clock = setup
    prepared, selected, _ = prepare(setup, mode)
    with pytest.raises(ConversationConflictError, match="binding_invalid"):
        service.finalize(
            cid, prepared.message_id, "b" * 64, completion(prepared), explicit_import=True
        )
    with (
        application_scope_context(ApplicationScope(application_id="travel")),
        pytest.raises(ResourceNotFoundError),
    ):
        service.finalize(
            cid,
            prepared.message_id,
            prepared.reservation.package_fingerprint,
            completion(prepared),
            explicit_import=True,
        )
    authority.version = "b" * 64
    with pytest.raises(ConversationConflictError, match="authority_changed"):
        finish(setup, prepared, selected)
    authority.version = "a" * 64
    original_time = clock[0]
    clock[0] = prepared.reservation.expires_at + timedelta(seconds=1)
    with pytest.raises(ConversationConflictError, match="expired"):
        finish(setup, prepared, selected)
    clock[0] = original_time
    messages.supersede_path(
        owner_id="local", conversation_id=cid, message_id=prepared.message_id, updated_at=clock[0]
    )
    with pytest.raises((ConversationConflictError, ValueError)):
        finish(setup, prepared, selected)


def test_uncertain_dispatch_stays_fenced_and_partial_text_absent(setup):
    service, cid, messages, *_ = setup
    prepared, selected, _ = prepare(setup, "connected_provider")
    service.dispatch(cid, prepared, selected)
    abandoned = service.abandon(cid, prepared.message_id, prepared.reservation.package_fingerprint)
    assert abandoned.execution.state == "unknown" and abandoned.content == ""
    with pytest.raises(ConversationConflictError, match="terminal_or_uncertain"):
        service.finalize(
            cid, prepared.message_id, prepared.reservation.package_fingerprint, completion(prepared)
        )
    new, selected, _ = prepare(setup)
    finish(setup, new, selected)
    assert (
        messages.get(owner_id="local", conversation_id=cid, message_id=abandoned.id).execution.state
        == "unknown"
    )


def test_concurrent_import_same_response_is_one_completion(setup):
    service, cid, messages, *_ = setup
    prepared, _, _ = prepare(setup)

    def finalize(_):
        return service.finalize(
            cid,
            prepared.message_id,
            prepared.reservation.package_fingerprint,
            completion(prepared),
            explicit_import=True,
        )

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(finalize, range(2)))
    assert results[0] == results[1]
    assert len(messages.list_active(owner_id="local", conversation_id=cid)) == 2


def test_manual_cannot_claim_observed_metadata_or_implicit_import(setup):
    service, cid, *_ = setup
    prepared, _, _ = prepare(setup)
    with pytest.raises(ConversationConflictError, match="provenance_mismatch"):
        service.finalize(
            cid, prepared.message_id, prepared.reservation.package_fingerprint, completion(prepared)
        )
    with pytest.raises(ValidationError):
        TurnAttribution(
            mode="manual_external",
            fact_source="user_declared",
            recorded_at=datetime.now(UTC),
            input_tokens=1,
        )
    with pytest.raises(ValidationError):
        TurnAttribution(
            mode="manual_external", fact_source="server_observed", recorded_at=datetime.now(UTC)
        )
    with pytest.raises(ValidationError):
        ExecutionChoice(mode="manual_external", connection_id=uuid4())


def test_manual_without_labels_and_output_bound(setup):
    service, cid, *_ = setup
    prepared = service.prepare(
        cid,
        ContinuationRequest(
            content="Question",
            idempotency_key=uuid4(),
            choice=ExecutionChoice(mode="manual_external"),
        ),
    )
    with pytest.raises(ConversationConflictError, match="output_invalid"):
        service.finalize(
            cid,
            prepared.message_id,
            prepared.reservation.package_fingerprint,
            completion(prepared, "x" * 20001),
            explicit_import=True,
        )
    result = service.finalize(
        cid,
        prepared.message_id,
        prepared.reservation.package_fingerprint,
        completion(prepared),
        explicit_import=True,
    )
    assert result.attribution.provider_id is None and result.model is None


def test_manual_producer_labels_are_supplied_at_import(setup):
    service, cid, *_ = setup
    prepared, _, _ = prepare(setup, "manual_external")
    result = service.finalize(
        cid,
        prepared.message_id,
        prepared.reservation.package_fingerprint,
        completion(prepared, provider="Local Model Host", model="model-after-copy"),
        explicit_import=True,
    )
    assert prepared.reservation.provider_id is None and prepared.reservation.model_id is None
    assert result.attribution.provider_id == "Local Model Host"
    assert result.attribution.model_id == result.model == "model-after-copy"


def test_connected_model_selection_is_separate_from_endpoint_profile(setup):
    service, cid, *_ = setup
    selected = choice("connected_provider")
    selected = selected.model_copy(update={"model_id": "account-visible-model-v2"})
    prepared = service.prepare(
        cid,
        ContinuationRequest(
            content="Choose visible model",
            idempotency_key=uuid4(),
            choice=selected,
        ),
    )
    assert prepared.connected_package.model_id == "account-visible-model-v2"
    assert prepared.connected_package.execution_profile.endpoint == selected.endpoint
    assert service.registry.profiles[0].model_id == "model-1"


def test_connected_lane_rejects_an_explicit_byok_profile_without_an_adapter(setup):
    service, *_ = setup
    with pytest.raises(ConversationConflictError, match="explicit_endpoint_unavailable"):
        service._profile(choice("connected_provider", "local_byok"), "personal")


def test_plan_never_automatic_candidate_or_free_quota(setup):
    service, *_ = setup
    requirements = EndpointCandidateRequirements(
        required_capabilities=frozenset({"streaming"}),
        sensitivity="public",
        input_tokens=100,
        output_tokens=100,
    )
    candidates = service.registry.candidates(requirements)
    assert not candidates.eligible_profiles
    assert all(not p.quota_buckets for p in service.registry.profiles)
    with pytest.raises(ValidationError):
        EndpointProfile.model_validate(
            profile().model_copy(update={"strict_free_enabled": True}).model_dump()
        )


def test_explicit_local_admission_uses_profile_facts_for_any_provider():
    second_provider = profile("synthetic_local_subscription")
    registry = EndpointRegistry([second_provider])
    admitted = registry.revalidate_explicit(
        second_provider.ref,
        sensitivity="personal",
        required_capabilities=frozenset({"streaming"}),
    )
    assert admitted == second_provider


def test_coarse_usage_no_reset_account_or_secret_fields():
    observation = usage_observation("bridge_usage_limit", now=1)
    assert observation.state == "limit"
    assert "reset" not in observation.model_dump_json()
    assert usage_observation("authorization=secret", now=2).state == "unknown"
    assert "secret" not in usage_observation("authorization=secret", now=2).model_dump_json()
    with pytest.raises(ValidationError):
        CoarseUsage(state="limit", reset_at=123)


@pytest.mark.parametrize("first", ["manual_external", "connected_provider"])
def test_external_to_automatic_to_connected_reuses_shared_context(setup, first):
    from personal_ai.context.providers import ContextPreparationError
    from personal_ai.llm.fake import FakeLLMClient

    service, cid, messages, *_ = setup
    prepared, selected, _ = prepare(setup, first)
    original = finish(setup, prepared, selected)
    llm = FakeLLMClient(["Automatic answer"], provider_id="automatic-fixture")
    # Replace the generation adapter only; repositories/context/branch stay shared.
    service.chat._llm = llm
    request = ContinuationRequest(
        content="Compare that answer", idempotency_key=uuid4(), candidate_message_ids=(original.id,)
    )

    async def collect():
        return [event async for event in sse_frames(service.chat.continue_turn(cid, request))]

    events = asyncio.run(collect())
    assert any("response.completed" in event for event in events)
    assert any(original.content in message.content for message in llm.requests[-1])
    automatic = messages.list_active(owner_id="local", conversation_id=cid)[-1]
    assert automatic.attribution.provider_id == "automatic-fixture"
    assert automatic.attribution.fact_source == "server_observed"
    assert automatic.attribution.execution_origin == "automatic_managed"
    assert automatic.model == automatic.attribution.model_id
    assert automatic.attribution.usage_confidence == "estimated"
    next_turn, selected, _ = prepare(setup, "connected_provider", candidates=(automatic.id,))
    finish(setup, next_turn, selected)
    assert messages.get(owner_id="local", conversation_id=cid, message_id=original.id) == original
    assert messages.get(owner_id="local", conversation_id=cid, message_id=automatic.id) == automatic
    assert automatic.id in next_turn.reservation.source_message_ids
    with pytest.raises(ContextPreparationError):
        service.chat.continue_turn(
            cid,
            ContinuationRequest(
                content="Invalid source", idempotency_key=uuid4(), candidate_message_ids=(uuid4(),)
            ),
        )


def test_narrowing_excludes_history_and_changed_idempotency_rejected(setup):
    service, cid, *_ = setup
    prior, selected, _ = prepare(setup)
    completed = finish(setup, prior, selected)
    next_turn, selected, request = prepare(setup, candidates=())
    assert not any(completed.content in m.content for m in next_turn.messages)
    with pytest.raises(ConversationConflictError, match="idempotency_input_changed"):
        service.prepare(cid, request.model_copy(update={"content": "Changed"}))
    service.abandon(cid, next_turn.message_id, next_turn.reservation.package_fingerprint)


@pytest.mark.parametrize("failure_call", [2, 3])
def test_external_same_key_resumes_after_post_append_preparation_failure(
    setup, monkeypatch, failure_call
):
    service, cid, messages, *_ = setup
    request = ContinuationRequest(
        content="Resume this request", idempotency_key=uuid4(), choice=ExecutionChoice(mode="manual_external")
    )
    original = service._snapshot
    calls = 0

    def fail_during_bound_context(conversation_id, selected, sources, snapshots=()):
        nonlocal calls
        calls += 1
        if calls == failure_call:
            raise ConversationConflictError("synthetic preparation authority failure")
        return original(conversation_id, selected, sources, snapshots)

    monkeypatch.setattr(service, "_snapshot", fail_during_bound_context)
    with pytest.raises(ConversationConflictError, match="authority failure"):
        service.prepare(cid, request)
    active = messages.list_active(owner_id="local", conversation_id=cid)
    assert len(active) == 1 and active[0].role.value == "user"
    monkeypatch.setattr(service, "_snapshot", original)

    restarted_chat = ChatTurnService(
        service.chat._conversations,
        messages,
        None,
        owner_id="local",
        model="fixture",
        application_context=service.context,
        context_assembler=service.chat._context,
    )
    restarted = ExternalTurnService(
        chat=restarted_chat,
        context=service.context,
        registry=service.registry,
        authority=service.authority,
        signer=service.signer,
        clock=service.clock,
    )
    with pytest.raises(ConversationConflictError, match="idempotency_input_changed"):
        restarted.prepare(cid, request.model_copy(update={"content": "changed"}))
    prepared = restarted.prepare(cid, request)
    active = messages.list_active(owner_id="local", conversation_id=cid)
    assert [message.role.value for message in active] == ["user", "assistant"]
    assert active[-1].execution.reservation_id == prepared.reservation.reservation_id


def test_new_external_key_terminalizes_abandoned_partial_user(setup, monkeypatch):
    service, cid, messages, *_ = setup
    original = service._snapshot
    calls = 0

    def fail_once(conversation_id, selected, sources, snapshots=()):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise ConversationConflictError("synthetic preparation failure")
        return original(conversation_id, selected, sources, snapshots)

    monkeypatch.setattr(service, "_snapshot", fail_once)
    with pytest.raises(ConversationConflictError):
        prepare(setup, "manual_external")
    abandoned = messages.list_active(owner_id="local", conversation_id=cid)[-1]
    monkeypatch.setattr(service, "_snapshot", original)
    resumed = service.prepare(
        cid,
        ContinuationRequest(
            content="A fresh explicit turn",
            idempotency_key=uuid4(),
            choice=ExecutionChoice(mode="manual_external"),
        ),
    )
    active = messages.list_active(owner_id="local", conversation_id=cid)
    assert abandoned.id not in {message.id for message in active}
    assert messages.get(owner_id="local", conversation_id=cid, message_id=abandoned.id).status is MessageStatus.SUPERSEDED
    assert active[-1].execution.reservation_id == resumed.reservation.reservation_id


def test_automatic_continuation_resumes_and_replays_same_key(setup, monkeypatch):
    from personal_ai.context.providers import ContextPreparationError
    from personal_ai.llm.fake import FakeLLMClient

    service, cid, _, *_ = setup
    llm = FakeLLMClient(["Recovered automatic answer"], provider_id="automatic-fixture")
    service.chat._llm = llm
    request = ContinuationRequest(content="Automatic request", idempotency_key=uuid4())
    original = service.chat._context.plan_context
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ContextPreparationError("synthetic planner failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(service.chat._context, "plan_context", fail_once)
    with pytest.raises(ContextPreparationError, match="planner failure"):
        service.chat.continue_turn(cid, request)
    monkeypatch.setattr(service.chat._context, "plan_context", original)

    async def collect(stream):
        return [event async for event in sse_frames(stream)]

    first = asyncio.run(collect(service.chat.continue_turn(cid, request)))
    replay = asyncio.run(collect(service.chat.continue_turn(cid, request)))
    assert any("Recovered automatic answer" in event for event in first)
    assert any('"delta":"Recovered automatic answer"' in event for event in replay)
    assert any("response.completed" in event for event in replay)
    assert len(llm.requests) == 1
    with pytest.raises(ConversationConflictError, match="idempotency_input_changed"):
        service.chat.continue_turn(cid, request.model_copy(update={"content": "Changed"}))


def test_dispatch_signing_failure_leaves_prepared_and_tampering_fails(setup):
    service, cid, messages, *_ = setup
    prepared, selected, _ = prepare(setup, "connected_provider")
    with pytest.raises(ConversationConflictError, match="dispatch_binding_invalid"):
        service.dispatch(cid, prepared, selected.model_copy(update={"caller_id": uuid4()}))
    service.signer = None
    with pytest.raises(ConversationConflictError, match="signer_unavailable"):
        service.dispatch(cid, prepared, selected)
    assert (
        messages.get(
            owner_id="local", conversation_id=cid, message_id=prepared.message_id
        ).execution.state
        == "prepared"
    )


def test_endpoint_version_churn_is_not_model_name_fallback(setup):
    service, cid, *_ = setup
    prepared, selected, _ = prepare(setup, "connected_provider")
    service.registry.reconcile(
        [p.model_copy(update={"serializer_id": "synthetic-v2"}) for p in service.registry.profiles]
    )
    with pytest.raises(ConversationConflictError, match="explicit_endpoint_unavailable"):
        service.dispatch(cid, prepared, selected)


def test_historical_attribution_immutable_at_repository_boundary(setup):
    _service, cid, messages, *_ = setup
    prepared, selected, _ = prepare(setup)
    result = finish(setup, prepared, selected)
    with pytest.raises(ValueError, match="producer_attribution_immutable"):
        messages.update_status(
            owner_id="local",
            conversation_id=cid,
            message_id=result.id,
            status=MessageStatus.COMPLETED,
            content="Edited producer",
            updated_at=datetime.now(UTC),
        )


def test_permission_gate_denies_before_preparation(setup):
    service, cid, messages, *_ = setup
    service.context = service.context.model_copy(
        update={
            "definition": service.context.definition.model_copy(
                update={
                    "context_policy": service.context.definition.context_policy.model_copy(
                        update={"external_execution_modes": ()}
                    )
                }
            )
        }
    )
    service.chat._application_context = service.context
    with pytest.raises(ConversationConflictError, match="execution_disclosure_denied"):
        prepare(setup)
    assert messages.list_active(owner_id="local", conversation_id=cid) == []


def test_external_context_cannot_diverge_from_shared_chat_context(setup):
    from personal_ai.context.providers import ContextPreparationError

    service, cid, messages, *_ = setup
    service.context = service.context.model_copy(
        update={"scope": service.context.scope.model_copy(update={"request_id": "changed"})}
    )
    with pytest.raises(ContextPreparationError, match="scope_mismatch"):
        prepare(setup)
    assert messages.list_active(owner_id="local", conversation_id=cid) == []


def test_completed_replay_rejects_superseded_reservation(setup):
    _service, cid, messages, *_, clock = setup
    prepared, selected, _ = prepare(setup)
    completed = finish(setup, prepared, selected)
    messages.supersede_path(
        owner_id="local", conversation_id=cid, message_id=completed.id, updated_at=clock[0]
    )
    with pytest.raises(ConversationConflictError, match="superseded"):
        finish(setup, prepared, selected)


def test_completed_replay_rechecks_authority_digest(setup):
    service, cid, _, authority, *_ = setup
    prepared, _, _ = prepare(setup)
    result = finish(setup, prepared, choice("manual_external"))
    authority.version = "b" * 64
    with pytest.raises(ConversationConflictError, match="source_authority_changed"):
        service.finalize(
            cid,
            result.id,
            prepared.reservation.package_fingerprint,
            completion(prepared),
            explicit_import=True,
        )


def test_cas_lost_response_replay_rechecks_authority(setup, monkeypatch):
    service, _, _, authority, *_ = setup
    prepared, selected, _ = prepare(setup)
    original = service.chat.transition

    def commit_then_report_conflict(current, replacement):
        original(current, replacement)
        authority.version = "b" * 64
        raise ConversationConflictError("synthetic lost response")

    monkeypatch.setattr(service.chat, "transition", commit_then_report_conflict)
    with pytest.raises(ConversationConflictError, match="source_authority_changed"):
        finish(setup, prepared, selected)
    monkeypatch.setattr(service.chat, "transition", original)


@pytest.mark.parametrize("mode", ["manual_external", "connected_provider"])
def test_repository_rejects_failed_execution_with_retained_output(setup, mode):
    from personal_ai.entities.turn_execution import transition_message

    prepared, _, _ = prepare(setup, mode)
    service, cid, *_ = setup
    current = service.chat.get_message(cid, prepared.message_id)
    invalid = current.model_copy(
        update={
            "status": MessageStatus.FAILED,
            "content": "Partial private output",
            "execution": current.execution.model_copy(update={"state": "cancelled"}),
        }
    )
    with pytest.raises(ValueError, match="failed_execution_requires_empty_message"):
        transition_message(current, invalid)


@pytest.mark.parametrize("mode", ["manual_external", "connected_provider"])
def test_canonical_completion_rejects_mismatched_reserved_provenance(setup, mode):
    from personal_ai.entities.turn_execution import transition_message

    service, cid, messages, *_ = setup
    prepared, selected, _ = prepare(setup, mode)
    if mode == "connected_provider":
        service.dispatch(cid, prepared, selected)
    current = service.chat.get_message(cid, prepared.message_id)
    reservation = current.execution
    attribution = TurnAttribution(
        mode=mode,
        fact_source="user_declared" if mode == "manual_external" else "client_reported",
        execution_origin="manual_import" if mode == "manual_external" else "connected_local",
        provider_id=reservation.provider_id,
        model_id=reservation.model_id,
        recorded_at=datetime.now(UTC),
        package_fingerprint=reservation.package_fingerprint,
        connection_id=reservation.connection_id,
        connection_revision=reservation.connection_revision,
        source_message_ids=reservation.source_message_ids,
        source_snapshots=reservation.source_snapshots,
    )
    invalid_attribution = attribution.model_copy(
        update={
            "package_fingerprint": "b" * 64
            if mode == "manual_external"
            else attribution.package_fingerprint,
            "provider_id": "forged-provider"
            if mode == "connected_provider"
            else attribution.provider_id,
        }
    )
    invalid = current.model_copy(
        update={
            "status": MessageStatus.COMPLETED,
            "content": "A canonical answer",
            "model": invalid_attribution.model_id,
            "attribution": invalid_attribution,
            "execution": reservation.model_copy(
                update={"state": "completed", "completion_digest": "c" * 64}
            ),
        }
    )
    with pytest.raises(ValueError, match="completion_attribution_mismatches_reservation"):
        transition_message(current, invalid)
    with pytest.raises(ValueError, match="completion_attribution_mismatches_reservation"):
        messages.update_status(
            owner_id="local",
            conversation_id=cid,
            message_id=current.id,
            status=MessageStatus.COMPLETED,
            replacement=invalid,
            expected_message=current,
            updated_at=datetime.now(UTC),
        )


def test_canonical_connected_completion_rejects_server_observed_client_facts(setup):
    from personal_ai.entities.turn_execution import transition_message

    service, cid, messages, *_ = setup
    prepared, selected, _ = prepare(setup, "connected_provider")
    service.dispatch(cid, prepared, selected)
    current = service.chat.get_message(cid, prepared.message_id)
    reservation = current.execution
    attribution = TurnAttribution(
        mode="connected_provider",
        fact_source="server_observed",
        execution_origin="connected_local",
        provider_id=reservation.provider_id,
        model_id=reservation.model_id,
        recorded_at=datetime.now(UTC),
        package_fingerprint=reservation.package_fingerprint,
        connection_id=reservation.connection_id,
        connection_revision=reservation.connection_revision,
        source_message_ids=reservation.source_message_ids,
        source_snapshots=reservation.source_snapshots,
    )
    invalid = current.model_copy(
        update={
            "status": MessageStatus.COMPLETED,
            "content": "A client-reported answer",
            "model": attribution.model_id,
            "attribution": attribution,
            "execution": reservation.model_copy(
                update={"state": "completed", "completion_digest": "c" * 64}
            ),
        }
    )
    with pytest.raises(ValueError, match="completion_attribution_mismatches_reservation"):
        transition_message(current, invalid)
    with pytest.raises(ValueError, match="completion_attribution_mismatches_reservation"):
        messages.update_status(
            owner_id="local",
            conversation_id=cid,
            message_id=current.id,
            status=MessageStatus.COMPLETED,
            replacement=invalid,
            expected_message=current,
            updated_at=datetime.now(UTC),
        )


def test_external_completions_use_shared_post_completion_lifecycle_once(setup):
    service, cid, *_ = setup

    class LifecycleSpy:
        def __init__(self):
            self.completed = []

        def after_completed(self, message, selected_memory_ids, *, application_context):
            self.completed.append((message.id, tuple(selected_memory_ids), application_context))

    spy = LifecycleSpy()
    service.chat._memory_lifecycle = spy

    async def drain():
        pending = tuple(service.chat._post_completion_tasks)
        if pending:
            await asyncio.gather(*pending)

    manual, _, _ = prepare(setup, "manual_external")
    imported = finish(setup, manual, choice("manual_external"))
    asyncio.run(drain())
    service.finalize(
        cid,
        imported.id,
        manual.reservation.package_fingerprint,
        completion(manual),
        explicit_import=True,
    )
    asyncio.run(drain())
    assert [entry[0] for entry in spy.completed] == [imported.id]

    connected, selected, _ = prepare(setup, "connected_provider")
    completed = finish(setup, connected, selected)
    asyncio.run(drain())
    assert [entry[0] for entry in spy.completed] == [imported.id, completed.id]

    from personal_ai.llm.fake import FakeLLMClient

    service.chat._llm = FakeLLMClient(["Automatic lifecycle answer"], provider_id="automatic")

    async def automatic_turn():
        events = [
            event
            async for event in sse_frames(
                service.chat.continue_turn(
                    cid, ContinuationRequest(content="Automatic completion", idempotency_key=uuid4())
                )
            )
        ]
        pending = tuple(service.chat._post_completion_tasks)
        if pending:
            await asyncio.gather(*pending)
        return events

    events = asyncio.run(automatic_turn())
    automatic_message = service.chat._messages.list_active(owner_id="local", conversation_id=cid)[-1]
    assert any("response.completed" in event for event in events)
    assert [entry[0] for entry in spy.completed] == [imported.id, completed.id, automatic_message.id]


def test_safe_failure_hint_never_releases_send_or_creates_usage_claims(setup):
    service, cid, messages, *_ = setup
    prepared, selected, _ = prepare(setup, "connected_provider")
    service.dispatch(cid, prepared, selected)
    with pytest.raises(ConversationConflictError, match="error_code_invalid"):
        service.report_failure(
            cid, prepared.message_id, prepared.reservation.package_fingerprint, "Bearer SECRET"
        )
    failed = service.report_failure(
        cid,
        prepared.message_id,
        prepared.reservation.package_fingerprint,
        "bridge_usage_limit",
        status=429,
        latency_ms=250,
    )
    assert failed.error_code == "bridge_usage_limit"
    assert failed.error_fact_source == "client_reported"
    assert failed.failure_status == 429 and failed.failure_latency_ms == 250
    assert failed.execution.state == "unknown" and failed.attribution is None
    assert "reset" not in failed.model_dump_json() and "SECRET" not in failed.model_dump_json()
    assert messages.get(owner_id="local", conversation_id=cid, message_id=failed.id) == failed


def test_expiry_recovery_and_restart_keep_canonical_reservation(setup):
    service, cid, messages, *_ = setup
    prepared, selected, _ = prepare(setup, "connected_provider")
    service.dispatch(cid, prepared, selected)
    now = prepared.reservation.expires_at + timedelta(seconds=1)
    messages.recover_stale_turn(
        owner_id="local",
        conversation_id=cid,
        stale_before=now - timedelta(seconds=360),
        updated_at=now,
    )
    recovered = messages.get(owner_id="local", conversation_id=cid, message_id=prepared.message_id)
    assert recovered.execution.state == "unknown"
    assert recovered.status == MessageStatus.FAILED
    # Hydration from persisted JSON preserves typed state and historical producer binding.
    from personal_ai.entities import Message

    assert Message.model_validate_json(recovered.model_dump_json()) == recovered


def test_v3_profile_definition_freezes_access_policy_without_old_schema_churn():
    from personal_ai.routing.definitions import (
        decode_endpoint_profile_definition,
        encode_current_endpoint_profile,
    )

    current = encode_current_endpoint_profile(profile())
    v3_payload = {key: value for key, value in current.payload.items() if key != "external_transport_id"}
    v3 = decode_endpoint_profile_definition(3, v3_payload)
    assert v3.definition_schema_version == 3
    assert v3.payload["access_policy"]["automation_eligible"] is False
    assert decode_endpoint_profile_definition(3, v3.payload) == v3
    with pytest.raises(ValueError, match="payload_invalid"):
        decode_endpoint_profile_definition(2, v3.payload)


def test_v4_profile_definition_freezes_external_transport_id():
    from personal_ai.routing.definitions import (
        decode_endpoint_profile_definition,
        encode_current_endpoint_profile,
    )

    current = encode_current_endpoint_profile(profile())
    assert current.definition_schema_version == 4
    assert current.payload["external_transport_id"] == "chatgpt_local_v1"
    assert decode_endpoint_profile_definition(4, current.payload) == current


def test_registered_source_snapshot_survives_prepare_and_rejects_stale_source(setup):
    from pydantic import BaseModel

    from personal_ai.applications.contracts import (
        CapabilityRegistration,
        ContextFieldPolicy,
        ContextOperationPolicy,
        ContextProviderPolicy,
    )
    from personal_ai.context.planner import ContextPlanner, ContextPlanningRule
    from personal_ai.context.providers import (
        ContextItem,
        ContextOperationSpec,
        ContextProviderCoordinator,
        ContextProviderSpec,
        ContextSourceReference,
        StaticContextProviderFactory,
    )

    service, _cid, _, authority, _, clock = setup

    class Payload(BaseModel):
        value: str

    class Source:
        spec = ContextProviderSpec(
            provider_id="synthetic.source",
            source_class="domain_current",
            source_version="fixture-v1",
            operations=(ContextOperationSpec(operation="current", allowed_fields=("value",)),),
        )

        def validate_selection(self, selection, inputs):
            pass

        def fetch(self, selection, scope, *, deadline):
            return (
                ContextItem(
                    source_class="domain_current",
                    provider_id="synthetic.source",
                    source_id="record-1",
                    source_version="fixture-v1",
                    item_id="item-1",
                    owner_id=scope.owner_id,
                    application_id=scope.application_id,
                    authority="authoritative",
                    sensitivity="personal",
                    observed_at=clock[0],
                    expires_at=clock[0] + timedelta(seconds=30),
                    source_refs=(
                        ContextSourceReference(
                            kind="url",
                            reference_id="source-record-1",
                            uri="https://source.example/item?access_token=synthetic-signed-secret#private",
                        ),
                    ),
                    payload=Payload(value="Authorized source body"),
                ),
            )

    policy = service.context.definition.context_policy
    policy = policy.model_copy(
        update={
            "provider_policies": (
                *policy.provider_policies,
                ContextProviderPolicy(
                    provider_id="synthetic.source",
                    operations=(
                        ContextOperationPolicy(
                            operation="current",
                            sensitivity="personal",
                            fields=(ContextFieldPolicy(field="value", sensitivity="personal"),),
                        ),
                    ),
                ),
            )
        }
    )
    context = service.context.model_copy(
        update={
            "definition": service.context.definition.model_copy(
                update={"context_provider_ids": ("synthetic.source",), "context_policy": policy}
            ),
            "context_provider_capabilities": (
                CapabilityRegistration(
                    capability_id="synthetic.source", kind="context_provider", available=True
                ),
            ),
        }
    )
    service.context = context
    service.chat._application_context = context
    service.chat._context.context_provider_coordinator = ContextProviderCoordinator(
        {"synthetic.source": StaticContextProviderFactory(Source())}
    )
    service.chat._context.context_planner = ContextPlanner(
        (
            ContextPlanningRule(
                rule_id="synthetic.source:v1",
                category="source",
                phrases=("continue reasoning",),
                provider_id="synthetic.source",
                operation="current",
                fields=("value",),
                explanation="Synthetic source",
                max_tokens=1024,
            ),
        ),
        include_default_rules=False,
    )
    prepared, selected, _ = prepare(setup)
    assert "Authorized source body" in prepared.portable_prompt
    snapshot = prepared.reservation.source_snapshots[0]
    assert snapshot.provider_id == "synthetic.source" and snapshot.source_version == "fixture-v1"
    assert snapshot.source_refs[0].reference_digest != "source-record-1"
    serialized = prepared.reservation.model_dump_json()
    assert "Authorized source body" not in serialized
    assert "synthetic-signed-secret" not in serialized
    assert "access_token" not in serialized
    assert "source-record-1" not in serialized
    pending = service.chat.get_message(_cid, prepared.message_id)
    assert "synthetic-signed-secret" not in pending.model_dump_json()
    clock[0] += timedelta(seconds=31)
    with pytest.raises(ConversationConflictError, match="source_expired"):
        finish(setup, prepared, selected)
    clock[0] -= timedelta(seconds=31)
    authority.version = "c" * 64
    with pytest.raises(ConversationConflictError, match="authority_changed"):
        finish(setup, prepared, selected)


def test_commit_response_loss_replays_canonical_completion(setup, monkeypatch):
    from personal_ai.storage.errors import StorageUnavailableError

    _service, cid, messages, *_ = setup
    prepared, selected, _ = prepare(setup)
    original = messages.update_status

    def lose_reply(**kwargs):
        original(**kwargs)
        raise StorageUnavailableError("synthetic committed write response loss")

    monkeypatch.setattr(messages, "update_status", lose_reply)
    with pytest.raises(StorageUnavailableError):
        finish(setup, prepared, selected)
    monkeypatch.setattr(messages, "update_status", original)
    result = finish(setup, prepared, selected)
    assert result.execution.state == "completed" and result.content == "External answer"
    assert len(messages.list_active(owner_id="local", conversation_id=cid)) == 2


def test_authenticated_external_turn_routes_prepare_and_import_through_shared_service(setup):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from personal_ai.api.dependencies import get_external_turn_service, get_settings
    from personal_ai.api.external_turns import router
    from personal_ai.settings import Settings

    service, conversation_id, _messages, *_ = setup
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_external_turn_service] = lambda: service
    app.dependency_overrides[get_settings] = lambda: Settings(
        ai_provider="fake", ai_model="fixture", external_turn_acceptance_enabled=True
    )
    with TestClient(app) as client:
        idempotency_key = str(uuid4())
        response = client.post(
            f"/v1/conversations/{conversation_id}/external-turns/prepare",
            json={
                "content": "Continue from this answer",
                "idempotency_key": idempotency_key,
                "choice": {"mode": "manual_external"},
                "candidate_message_ids": None,
            },
        )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        prepared = response.json()
        assert prepared["mode"] == "manual_external"
        assert prepared["context_package"]["counter_kind"] == "estimated"
        assert prepared["context_package"]["fingerprint"] == prepared["package_fingerprint"]
        assert "user:" in prepared["portable_prompt"]

        reconciliation = client.get(
            f"/v1/conversations/{conversation_id}/external-turns/requests/{idempotency_key}"
        )
        assert reconciliation.status_code == 200
        assert reconciliation.json()["state"] == "prepared"
        assert reconciliation.json()["message_id"] == prepared["message_id"]

        invalid_label = client.post(
            f"/v1/conversations/{conversation_id}/external-turns/{prepared['message_id']}/import",
            json={
                "package_fingerprint": prepared["package_fingerprint"],
                "text": "Imported response",
                "provider_label": "invalid, label",
            },
        )
        assert invalid_label.status_code == 422

        imported = client.post(
            f"/v1/conversations/{conversation_id}/external-turns/{prepared['message_id']}/import",
            json={
                "package_fingerprint": prepared["package_fingerprint"],
                "text": "Imported response",
                "provider_label": "Example Provider",
                "model_label": "unverified-model",
            },
        )
        assert imported.status_code == 200
        payload = imported.json()
        assert payload["content"] == "Imported response"
        assert payload["attribution"]["execution_origin"] == "manual_import"
        assert payload["attribution"]["fact_source"] == "user_declared"
        assert payload["attribution"]["model_verified"] is False


def test_lost_prepare_response_reconciles_and_stale_reservation_can_be_abandoned(setup):
    service, conversation_id, _messages, authority, _key, _clock = setup
    prepared, _selected, request = prepare(setup)

    recovered = service.reconcile(conversation_id, request.idempotency_key)
    assert recovered["state"] == "prepared"
    assert recovered["message_id"] == str(prepared.message_id)

    authority.version = "d" * 64
    stale = service.reconcile(conversation_id, request.idempotency_key)
    assert stale["state"] == "prepared_stale"
    assert stale["stale_reason"] == "source_authority_changed"

    cancelled = service.abandon_by_idempotency_key(conversation_id, request.idempotency_key)
    assert cancelled.execution.state == "cancelled"


def test_principal_bound_authority_requires_verified_owner_and_rechecks_source_grants(setup):
    from personal_ai.auth.contracts import AuthenticatedPrincipal
    from personal_ai.contracts.context_references import (
        ContextPermissionDependency,
        ContextSourceSnapshot,
    )
    from personal_ai.services.external_turns.authority import PrincipalBoundExternalTurnAuthority

    service, conversation_id, messages, *_ = setup
    principal = AuthenticatedPrincipal(
        issuer="https://accounts.google.com",
        subject="subject-123",
        owner_id="local",
        email=None,
        issued_at=1,
        authenticated=True,
    )
    authority = PrincipalBoundExternalTurnAuthority(
        principal=principal,
        conversations=service.chat._conversations,
        messages=messages,
        permission_revalidator=None,
    )
    assert len(authority.snapshot(
        service.context,
        conversation_id,
        choice("manual_external"),
        (),
        (),
    )) == 64

    wrong_owner = principal.__class__(
        issuer=principal.issuer,
        subject=principal.subject,
        owner_id="another-owner",
        email=None,
        issued_at=1,
        authenticated=True,
    )
    denied = PrincipalBoundExternalTurnAuthority(
        principal=wrong_owner,
        conversations=service.chat._conversations,
        messages=messages,
        permission_revalidator=None,
    )
    with pytest.raises(ConversationConflictError, match="principal_scope_mismatch"):
        denied.snapshot(service.context, conversation_id, choice("manual_external"), (), ())

    dependency = ContextPermissionDependency(
        permission_id="source-read",
        version="grant-v3",
        purpose="manual external disclosure",
    )
    snapshot = ContextSourceSnapshot(
        provider_id="synthetic.source",
        source_id="source-1",
        source_version="source-v1",
        item_id="item-1",
        owner_id="local",
        application_id="personal_ai",
        content_fingerprint="b" * 64,
        permission_dependencies=(dependency,),
    )

    class RevokedPermission:
        @staticmethod
        def is_current(_dependency):
            return False

    revoked = PrincipalBoundExternalTurnAuthority(
        principal=principal,
        conversations=service.chat._conversations,
        messages=messages,
        permission_revalidator=RevokedPermission(),
    )
    with pytest.raises(ConversationConflictError, match="source_permission_revoked"):
        revoked.snapshot(
            service.context,
            conversation_id,
            choice("manual_external"),
            (),
            (snapshot,),
        )


def test_execution_options_follow_application_policy_and_current_explicit_profiles(setup, monkeypatch):
    from personal_ai.api.external_turns import execution_options
    from personal_ai.applications.contracts import ExternalDisclosurePolicy
    from personal_ai.settings import Settings

    service, *_ = setup
    settings = Settings(
        ai_provider="fake", ai_model="fixture", external_turn_acceptance_enabled=True
    )
    monkeypatch.setattr(
        "personal_ai.api.external_turns.get_endpoint_registry", lambda _settings: service.registry
    )
    monkeypatch.setattr(
        "personal_ai.api.external_turns.get_external_dispatch_signer", lambda _settings: service.signer
    )
    options = execution_options(service.context, settings)
    assert options.modes == ("automatic", "connected_provider", "manual_external")
    assert {item.provider_id for item in options.explicit_profiles} == {
        "openai_chatgpt_plan",
        "another_provider",
    }

    monkeypatch.setattr(
        "personal_ai.api.external_turns.get_external_dispatch_signer", lambda _settings: None
    )
    without_signer = execution_options(service.context, settings)
    assert without_signer.modes == ("automatic", "manual_external")
    assert without_signer.explicit_profiles == ()

    denied_context = service.context.model_copy(
        update={
            "definition": service.context.definition.model_copy(
                update={
                    "context_policy": service.context.definition.context_policy.model_copy(
                        update={"external_execution_modes": ()}
                    )
                }
            )
        }
    )
    monkeypatch.setattr(
        "personal_ai.api.external_turns.get_external_dispatch_signer", lambda _settings: service.signer
    )
    denied = execution_options(denied_context, settings)
    assert denied.modes == ("automatic",)
    assert denied.explicit_profiles == ()

    original_sidecar = service.context.definition.context_policy.sidecar
    for restricted_sidecar in (
        original_sidecar.model_copy(update={
            "manual_external_disclosure": ExternalDisclosurePolicy(
                allowed=False,
                allowed_context_categories=("conversation",),
                maximum_sensitivity="personal",
            )
        }),
        original_sidecar.model_copy(update={"copy_allowed": False}),
    ):
        restricted_context = service.context.model_copy(update={
            "definition": service.context.definition.model_copy(update={
                "context_policy": service.context.definition.context_policy.model_copy(
                    update={"sidecar": restricted_sidecar}
                )
            })
        })
        restricted = execution_options(restricted_context, settings)
        assert "manual_external" not in restricted.modes
        assert restricted.sidecar == restricted_sidecar
