"""Phase 25.2 synthetic state-machine, provenance, policy and concurrency acceptance."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

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
from personal_ai.services.chat_turns import ChatTurnService
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


def profile(provider="openai_chatgpt_plan"):
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
        execution_mode="CHATGPT_PLAN",
        cost_class="SUBSCRIPTION",
        enabled=True,
        capabilities=frozenset({"streaming"}),
        context_limit_tokens=10000,
        serializer_id="synthetic-v1",
        runtime_id="synthetic-v1",
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
    registry = EndpointRegistry([profile(), profile("another_provider")])
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
        return ExecutionChoice(
            mode=mode, declared_provider="Optional service", declared_model="Optional model"
        )
    return ExecutionChoice(
        mode=mode,
        endpoint=profile(provider).ref,
        connection_id=uuid4(),
        connection_revision=1,
        caller_id=uuid4(),
        audience=uuid4(),
    )


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


def completion(prepared, text="External answer"):
    r = prepared.reservation
    p = ExecutionProvenance(
        mode=r.mode,
        fact_source="user_declared" if r.mode == "manual_external" else "bridge_observed",
        provider_id=r.provider_id,
        model_id=r.model_id,
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
    clock[0] += timedelta(seconds=121)
    with pytest.raises(ConversationConflictError, match="expired"):
        finish(setup, prepared, selected)
    clock[0] -= timedelta(seconds=121)
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
        return [event async for event in service.chat.continue_turn(cid, request)]

    events = asyncio.run(collect())
    assert any("response.completed" in event for event in events)
    assert any(original.content in message.content for message in llm.requests[-1])
    automatic = messages.list_active(owner_id="local", conversation_id=cid)[-1]
    assert automatic.attribution.provider_id == "automatic-fixture"
    assert automatic.attribution.fact_source == "server_observed"
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


def test_safe_failure_hint_never_releases_send_or_creates_usage_claims(setup):
    service, cid, messages, *_ = setup
    prepared, selected, _ = prepare(setup, "connected_provider")
    service.dispatch(cid, prepared, selected)
    with pytest.raises(ConversationConflictError, match="error_code_invalid"):
        service.report_failure(
            cid, prepared.message_id, prepared.reservation.package_fingerprint, "Bearer SECRET"
        )
    failed = service.report_failure(
        cid, prepared.message_id, prepared.reservation.package_fingerprint, "bridge_usage_limit"
    )
    assert failed.error_code == "bridge_usage_limit"
    assert failed.error_fact_source == "client_reported"
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
    assert current.definition_schema_version == 3
    assert current.payload["access_policy"]["automation_eligible"] is False
    assert decode_endpoint_profile_definition(3, current.payload) == current
    with pytest.raises(ValueError, match="payload_invalid"):
        decode_endpoint_profile_definition(2, current.payload)


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
                    source_refs=(ContextSourceReference(kind="record", reference_id="record-1"),),
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
    assert snapshot.source_refs[0].reference_id == "record-1"
    assert "Authorized source body" not in prepared.reservation.model_dump_json()
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
