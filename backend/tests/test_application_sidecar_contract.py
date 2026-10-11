"""Synthetic application-host conformance through shared launch and turn contracts."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel

from personal_ai.api.chat_stream import sse_frames
from personal_ai.applications.contracts import (
    ApplicationContextPolicy,
    ApplicationContextRequest,
    ApplicationDefinition,
    ApplicationLaunchContext,
    ApplicationSidecarPolicy,
    CapabilityRegistration,
    ContextFieldPolicy,
    ContextOperationPolicy,
    ContextProviderPolicy,
    ExternalDisclosurePolicy,
)
from personal_ai.applications.registry import ApplicationRegistry
from personal_ai.auth.dispatch_grants import DispatchGrantSigner
from personal_ai.auth.scope import ApplicationScope, RequestScope, application_scope_context
from personal_ai.context import ContextAssembler
from personal_ai.context.planner import ContextPlanner, ContextPlanningRule
from personal_ai.context.providers import (
    ContextItem,
    ContextOperationSpec,
    ContextPermissionDependency,
    ContextProviderCoordinator,
    ContextProviderError,
    ContextProviderSpec,
    ContextSelection,
    ContextSourceReference,
)
from personal_ai.context.tokens import EstimatedTokenCounter
from personal_ai.contracts.context_references import ContextEntityReference
from personal_ai.entities import Conversation
from personal_ai.routing.contracts import DataUsePolicy, EndpointProfile, ProviderAccessPolicy
from personal_ai.routing.registry import EndpointRegistry
from personal_ai.services.chat.service import ChatTurnService
from personal_ai.services.external_turns import ExternalTurnService
from personal_ai.settings import Settings
from personal_ai.storage import InMemoryConversationRepository, InMemoryMessageRepository
from personal_ai.storage.errors import ConversationConflictError

REFERENCE_APPLICATIONS = ("travel", "shopping", "finance", "health", "synthetic_fifth")
PROVIDER_ID = "host.selected_record"


def test_legacy_continuation_digest_remains_stable_without_launch_context():
    from personal_ai.contracts.execution import ContinuationRequest, ExecutionChoice

    idempotency_key = uuid4()
    choice = ExecutionChoice(mode="manual_external")
    request = ContinuationRequest(
        content="Continue reasoning",
        idempotency_key=idempotency_key,
        choice=choice,
    )
    legacy_payload = {
        "content": "Continue reasoning",
        "idempotency_key": str(idempotency_key),
        "choice": choice.model_dump(mode="json"),
        "candidate_message_ids": None,
        "excluded_source_classes": [],
    }
    expected = sha256(json.dumps(
        legacy_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")).hexdigest()

    assert request.intent_digest == expected


class SelectedRecordPayload(BaseModel):
    label: str


class FakeDomainReadAdapter:
    """A domain-owned fake that independently authorizes one exact entity ref."""

    spec = ContextProviderSpec(
        provider_id=PROVIDER_ID,
        source_class="domain_current",
        source_version="synthetic-host-record-v1",
        operations=(
            ContextOperationSpec(
                operation="current",
                allowed_fields=("label",),
                accepts_entity_refs=True,
                maximum_results=1,
            ),
        ),
    )

    def __init__(self, authorized_ref: ContextEntityReference) -> None:
        self.authorized_ref = authorized_ref
        self.calls: list[ContextSelection] = []

    def validate_selection(self, selection: ContextSelection, inputs) -> None:
        if inputs.scope.application_id != self.authorized_ref.application_id:
            raise ContextProviderError("host_scope_mismatch")
        if selection.entity_refs != (self.authorized_ref,):
            raise ContextProviderError("host_entity_not_authorized")

    def fetch(self, selection: ContextSelection, scope: RequestScope, *, deadline: float):
        del deadline
        self.calls.append(selection)
        reference = selection.entity_refs[0]
        return (
            ContextItem(
                source_class="domain_current",
                provider_id=PROVIDER_ID,
                source_id=f"{reference.entity_type}-source",
                source_version="revision-7",
                item_id=reference.entity_id,
                owner_id=scope.owner_id,
                application_id=scope.application_id,
                workspace_id=scope.workspace_id,
                entity_refs=(reference,),
                authority="authoritative",
                observed_at=datetime.now(UTC),
                sensitivity="personal",
                source_refs=(ContextSourceReference(
                    kind="record", reference_id=reference.entity_id, fingerprint="a" * 64
                ),),
                permission_dependencies=(ContextPermissionDependency(
                    permission_id="host.read_selected_record",
                    version="synthetic-membership-v1",
                    purpose="read the exact selected record through its owning adapter",
                ),),
                payload=SelectedRecordPayload(label="Authorized host record contents"),
            ),
        )


class FakeExternalAuthority:
    def snapshot(self, context, conversation_id, choice, source_message_ids, source_snapshots):
        del context, conversation_id, choice, source_message_ids, source_snapshots
        return "b" * 64


class CurrentSelectedRecordPermission:
    """Synthetic host permission recheck used by the shared context builder."""

    @staticmethod
    def is_current(dependency):
        return (
            dependency.permission_id == "host.read_selected_record"
            and dependency.version == "synthetic-membership-v1"
        )


def _connected_profile():
    return EndpointProfile(
        endpoint_profile_id="synthetic-provider:responses",
        profile_version=1,
        provider_id="synthetic_provider",
        model_id="model-1",
        endpoint_id="responses-v1",
        deployment_id="synthetic-v1",
        credential_source="user_runtime",
        credential_reference="user_runtime:local",
        tier_id="subscription",
        execution_mode="CHATGPT_PLAN",
        cost_class="SUBSCRIPTION",
        billing_owner="subscription",
        enabled=True,
        capabilities=frozenset({"streaming"}),
        context_limit_tokens=10000,
        serializer_id="synthetic-v1",
        runtime_id="synthetic-v1",
        external_transport_id="chatgpt_local_v1",
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


def _runtime(
    application_id: str,
    *,
    categories=None,
    maximum_sensitivity="sensitive",
    manual_disclosure_allowed=True,
    manual_import_reuse_allowed=True,
    manual_import_maximum_sensitivity="restricted",
    copy_allowed=True,
    connected_enabled=False,
):
    workspace_id = "workspace-1"
    reference = ContextEntityReference(
        entity_type="record",
        entity_id=f"{application_id}-record-1",
        application_id=application_id,
        workspace_id=workspace_id,
    )
    provider_policy = ContextProviderPolicy(
        provider_id=PROVIDER_ID,
        operations=(ContextOperationPolicy(
            operation="current",
            fields=(ContextFieldPolicy(field="label", sensitivity="personal"),),
            sensitivity="personal",
        ),),
    )
    base_policy = ApplicationContextPolicy()
    sidecar = ApplicationSidecarPolicy(
        manual_external_disclosure=ExternalDisclosurePolicy(
            allowed=manual_disclosure_allowed,
            allowed_context_categories=tuple(categories or (
                "conversation", "domain_current"
            )),
            maximum_sensitivity=maximum_sensitivity,
        ),
        connected_provider_disclosure=ExternalDisclosurePolicy(
            allowed=connected_enabled,
            allowed_context_categories=tuple(categories or ("conversation", "domain_current")),
            maximum_sensitivity=maximum_sensitivity,
        ),
        manual_import_reuse={
            "allowed": manual_import_reuse_allowed,
            "maximum_sensitivity": manual_import_maximum_sensitivity,
        },
        copy_allowed=copy_allowed,
        draft_insert_target_ids=("host.edit_draft",),
    )
    definition = ApplicationDefinition(
        application_id=application_id,
        display_name=f"{application_id} fixture",
        memory_namespace=application_id,
        context_provider_ids=(PROVIDER_ID,),
        context_policy=ApplicationContextPolicy(
            version="synthetic-sidecar-policy-v1",
            provider_policies=(*base_policy.provider_policies, provider_policy),
            external_execution_modes=(
                ("manual_external", "connected_provider")
                if connected_enabled else ("manual_external",)
            ),
            maximum_model_sensitivity="sensitive",
            sidecar=sidecar,
        ),
    )
    registry = ApplicationRegistry(
        (definition,),
        (CapabilityRegistration(
            capability_id=PROVIDER_ID, kind="context_provider", available=True
        ),),
    )
    registration = registry.registration(application_id)
    scope = RequestScope(
        owner_id="owner-1",
        request_id=f"{application_id}-request",
        application_id=application_id,
        workspace_id=workspace_id,
        client_context={"origin_view": "detail"},
    )
    context = ApplicationContextRequest(
        definition=definition,
        scope=scope,
        context_provider_capabilities=registration.context_providers,
        tool_capabilities=registration.tools,
    )
    conversation_id = uuid4()
    launch = ApplicationLaunchContext(
        application_id=application_id,
        workspace_id=workspace_id,
        entity_refs=(reference,),
        view_id="record.detail",
        conversation_id=str(conversation_id),
        client_context=scope.client_context,
    )
    adapter = FakeDomainReadAdapter(reference)
    planner = ContextPlanner(
        (
            ContextPlanningRule(
                rule_id="host.selected-record:v1",
                category="selected_host_record",
                phrases=("use the selected record",),
                provider_id=PROVIDER_ID,
                operation="current",
                fields=("label",),
                max_tokens=1200,
                use_candidate_entities=True,
                require_candidate_entities=True,
                required=True,
                priority=1,
                explanation="Read the exact entity selected by the host adapter.",
            ),
        ),
        include_default_rules=False,
    )
    assembler = ContextAssembler(
        Settings(ai_provider="fake", ai_model="fixture"),
        EstimatedTokenCounter(),
        context_provider_coordinator=ContextProviderCoordinator({PROVIDER_ID: adapter}),
        permission_revalidator=CurrentSelectedRecordPermission(),
        context_planner=planner,
    )
    conversations = InMemoryConversationRepository()
    messages = InMemoryMessageRepository(conversations)
    app_scope = ApplicationScope(application_id=application_id, workspace_id=workspace_id)
    with application_scope_context(app_scope):
        conversation = conversations.create(
            Conversation(
                id=conversation_id,
                owner_id=scope.owner_id,
                application_id=application_id,
                workspace_id=workspace_id,
                title=f"{application_id} fixture",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
    chat = ChatTurnService(
        conversations,
        messages,
        None,
        owner_id=scope.owner_id,
        model="fixture",
        application_context=context,
        context_assembler=assembler,
    )
    endpoint_profile = _connected_profile() if connected_enabled else None
    signer = (
        DispatchGrantSigner(
            issuer="synthetic-fixture",
            key_id="synthetic-key",
            key=Ed25519PrivateKey.generate(),
        )
        if connected_enabled else None
    )
    service = ExternalTurnService(
        chat=chat,
        context=context,
        registry=EndpointRegistry((endpoint_profile,) if endpoint_profile else ()),
        authority=FakeExternalAuthority(),
        signer=signer,
        context_assembler=assembler,
    )
    return service, context, conversation, messages, launch, reference, adapter, app_scope


@pytest.mark.parametrize("application_id", REFERENCE_APPLICATIONS)
def test_reference_and_synthetic_hosts_share_one_launch_package_and_turn_contract(application_id):
    service, context, conversation, messages, launch, reference, adapter, app_scope = _runtime(
        application_id
    )
    from personal_ai.contracts.execution import ContinuationRequest, ExecutionChoice

    request = ContinuationRequest(
        content="Use the selected record to continue.",
        idempotency_key=uuid4(),
        choice=ExecutionChoice(mode="manual_external"),
        launch_context=launch,
    )
    with application_scope_context(app_scope):
        prepared = service.prepare(conversation.id, request)
        assert "Authorized host record contents" in prepared.portable_prompt
        assert prepared.context_package is not None
        assert any(
            source.category == "domain_current"
            for source in prepared.context_package.included_sources
        )
        assert adapter.calls[0].entity_refs == (reference,)

        completed = service.import_manual(
            conversation.id,
            prepared.message_id,
            prepared.reservation.package_fingerprint,
            "Imported response from a user-controlled external session.",
        )
        assert completed.attribution.execution_origin == "manual_import"
        assert completed.attribution.fact_source == "user_declared"
        original_attribution = completed.attribution

        import asyncio

        from personal_ai.contracts.execution import ExecutionChoice
        from personal_ai.llm.fake import FakeLLMClient

        automatic_llm = FakeLLMClient(["Automatic follow-up"], provider_id="automatic-fixture")
        service.chat._llm = automatic_llm
        next_request = request.model_copy(update={
            "idempotency_key": uuid4(),
            "content": "Use the selected record and the earlier response.",
            "choice": ExecutionChoice(mode="automatic"),
            "candidate_message_ids": (completed.id,),
        })

        async def collect_events():
            return [
                event
                async for event in sse_frames(
                    service.chat.continue_turn(conversation.id, next_request)
                )
            ]

        events = asyncio.run(collect_events())
        assert any("response.completed" in event for event in events)
        assert any(
            "Imported response from a user-controlled external session." in message.content
            for message in automatic_llm.requests[-1]
        )
        automatic = messages.list_active(
            owner_id=context.scope.owner_id, conversation_id=conversation.id
        )[-1]
        assert automatic.attribution.provider_id == "automatic-fixture"
        assert completed.id in automatic.attribution.source_message_ids
        assert messages.get(
            owner_id=context.scope.owner_id,
            conversation_id=conversation.id,
            message_id=completed.id,
        ).attribution == original_attribution


def test_domain_launch_contract_spans_manual_connected_and_automatic_lanes():
    service, context, conversation, messages, launch, reference, adapter, app_scope = _runtime(
        "synthetic_fifth", connected_enabled=True
    )
    from personal_ai.contracts.execution import ContinuationRequest, ExecutionChoice
    from personal_ai.llm.fake import FakeLLMClient

    manual_request = ContinuationRequest(
        content="Use the selected record to continue.",
        idempotency_key=uuid4(),
        choice=ExecutionChoice(mode="manual_external"),
        launch_context=launch,
    )
    with application_scope_context(app_scope):
        manual_prepared = service.prepare(conversation.id, manual_request)
        imported = service.import_manual(
            conversation.id,
            manual_prepared.message_id,
            manual_prepared.reservation.package_fingerprint,
            "Manual source response for the connected follow-up.",
        )
        original_attribution = imported.attribution

        endpoint = _connected_profile()
        connected_choice = ExecutionChoice(
            mode="connected_provider",
            endpoint=endpoint.ref,
            model_id="account-visible-model",
            connection_id=uuid4(),
            connection_revision=1,
            caller_id=uuid4(),
            audience=uuid4(),
        )
        connected_request = ContinuationRequest(
            content="Use the selected record and imported result.",
            idempotency_key=uuid4(),
            choice=connected_choice,
            candidate_message_ids=(imported.id,),
            launch_context=launch,
        )
        connected_prepared = service.prepare(conversation.id, connected_request)
        assert connected_prepared.connected_package is not None
        assert any(
            item.entity_refs == (reference,) for item in adapter.calls
        )
        assert any(
            "Manual source response for the connected follow-up." in message.content
            for message in connected_prepared.connected_package.messages
        )
        service.dispatch(conversation.id, connected_prepared, connected_choice)
        connected = service.finalize_connected(
            conversation.id,
            connected_prepared.message_id,
            connected_prepared.reservation.package_fingerprint,
            "Connected result using the synthetic domain source.",
        )
        assert connected.attribution.execution_origin == "connected_local"
        assert messages.get(
            owner_id=context.scope.owner_id,
            conversation_id=conversation.id,
            message_id=imported.id,
        ).attribution == original_attribution

        automatic_llm = FakeLLMClient(["Automatic result"], provider_id="automatic-fixture")
        service.chat._llm = automatic_llm
        automatic_request = connected_request.model_copy(update={
            "idempotency_key": uuid4(),
            "choice": ExecutionChoice(mode="automatic"),
            "candidate_message_ids": (connected.id,),
            "content": "Use the selected record to continue automatically.",
        })
        import asyncio

        asyncio.run(_collect_stream(service, conversation.id, automatic_request))
        automatic = messages.list_active(
            owner_id=context.scope.owner_id, conversation_id=conversation.id
        )[-1]

    assert adapter.calls[-1].entity_refs == (reference,)
    assert automatic.attribution.execution_origin == "automatic_managed"
    assert imported.attribution == original_attribution


def test_external_category_and_sensitivity_narrowing_happen_before_domain_fetch():
    service, _context, conversation, _messages, launch, _reference, adapter, app_scope = _runtime(
        "synthetic_fifth", categories=("conversation",)
    )
    from personal_ai.contracts.execution import ContinuationRequest, ExecutionChoice

    request = ContinuationRequest(
        content="Use the selected record to continue.",
        idempotency_key=uuid4(),
        choice=ExecutionChoice(mode="manual_external"),
        launch_context=launch,
    )
    with application_scope_context(app_scope):
        prepared = service.prepare(conversation.id, request)
    assert adapter.calls == []
    assert "Authorized host record contents" not in prepared.portable_prompt

    restrictive, _context, conversation, _messages, launch, _reference, adapter, app_scope = _runtime(
        "synthetic_fifth", maximum_sensitivity="public"
    )
    with application_scope_context(app_scope), pytest.raises(
        ConversationConflictError, match="execution_sensitivity_denied|context_mode_sensitivity_denied"
    ):
        restrictive.prepare(conversation.id, request.model_copy(update={
            "idempotency_key": uuid4(), "launch_context": launch,
        }))
    assert adapter.calls == []


@pytest.mark.parametrize(
    "manual_disclosure_allowed,copy_allowed",
    [(False, True), (True, False)],
)
def test_application_can_disable_manual_external_disclosure_without_adapter_work(
    manual_disclosure_allowed, copy_allowed
):
    service, _context, conversation, messages, launch, _reference, adapter, app_scope = _runtime(
        "finance",
        manual_disclosure_allowed=manual_disclosure_allowed,
        copy_allowed=copy_allowed,
    )
    from personal_ai.contracts.execution import ContinuationRequest, ExecutionChoice

    request = ContinuationRequest(
        content="Use the selected record to continue.",
        idempotency_key=uuid4(),
        choice=ExecutionChoice(mode="manual_external"),
        launch_context=launch,
    )
    with application_scope_context(app_scope), pytest.raises(
        ConversationConflictError, match="execution_disclosure_denied"
    ):
        service.prepare(conversation.id, request)
    assert adapter.calls == []
    assert messages.list_active(owner_id="owner-1", conversation_id=conversation.id) == []


def test_domain_policy_can_prevent_manual_import_reuse_as_automatic_context():
    service, context, conversation, messages, launch, _reference, _adapter, app_scope = _runtime(
        "health", manual_import_reuse_allowed=False
    )
    from personal_ai.contracts.execution import ContinuationRequest, ExecutionChoice
    from personal_ai.llm.fake import FakeLLMClient

    request = ContinuationRequest(
        content="Use the selected record to continue.",
        idempotency_key=uuid4(),
        choice=ExecutionChoice(mode="manual_external"),
        launch_context=launch,
    )
    extraction_calls = []

    class RecordingExtraction:
        def run(self, completed, *, application_context=None):
            extraction_calls.append((completed.id, application_context))

    service.chat._memory_extraction = RecordingExtraction()
    with application_scope_context(app_scope):
        prepared = service.prepare(conversation.id, request)
        imported = service.import_manual(
            conversation.id,
            prepared.message_id,
            prepared.reservation.package_fingerprint,
            "Sensitive manual response that health policy excludes from future context.",
        )
        from personal_ai.context.contracts import ConversationSummary, fingerprint
        from personal_ai.context.repositories import InMemorySummaryRepository

        imported_branch = tuple(messages.list_active(
            owner_id=context.scope.owner_id, conversation_id=conversation.id
        ))
        imported_ids = tuple(message.id for message in imported_branch)
        summary = ConversationSummary(
            id=uuid4(),
            conversation_id=conversation.id,
            owner_id=context.scope.owner_id,
            application_id=context.scope.application_id,
            workspace_id=context.scope.workspace_id,
            content="Stale summary leak: Sensitive manual response that health policy excludes from future context.",
            source_message_ids=imported_ids,
            source_fingerprint=fingerprint(imported_branch),
            coverage_message_ids=imported_ids,
            coverage_fingerprint=fingerprint(imported_branch, include_state=True),
            covers_through_message_id=imported_ids[-1],
            source_token_count=100,
            summary_token_count=20,
            model="fixture",
            created_at=datetime.now(UTC),
        )
        summaries = InMemorySummaryRepository()
        summaries.create(summary)
        service.chat._context.summaries = summaries

        llm = FakeLLMClient(["Follow-up without imported detail"], provider_id="automatic-fixture")
        service.chat._llm = llm
        continuation = request.model_copy(update={
            "idempotency_key": uuid4(),
            "content": "Continue from the earlier response.",
            "choice": ExecutionChoice(mode="automatic"),
            "candidate_message_ids": (imported.id,),
        })

        import asyncio

        from personal_ai.context.providers import ContextPreparationError

        with pytest.raises(ContextPreparationError, match="continuation_source_policy_denied"):
            asyncio.run(_collect_stream(service, conversation.id, continuation))

        external_continuation = continuation.model_copy(update={
            "idempotency_key": uuid4(),
            "choice": ExecutionChoice(mode="manual_external"),
        })
        with pytest.raises(ContextPreparationError, match="continuation_source_policy_denied"):
            service.preview(conversation.id, external_continuation)

        without_explicit_target = continuation.model_copy(update={
            "idempotency_key": uuid4(),
            "candidate_message_ids": None,
        })
        asyncio.run(_collect_stream(service, conversation.id, without_explicit_target))
        assert messages.get(
            owner_id=context.scope.owner_id,
            conversation_id=conversation.id,
            message_id=imported.id,
        ).attribution == imported.attribution

    assert extraction_calls == []
    assert all(
        "Sensitive manual response that health policy excludes from future context." not in message.content
        for message in llm.requests[-1]
    )
    assert all("Stale summary leak" not in message.content for message in llm.requests[-1])


async def _collect_stream(service, conversation_id, request):
    return [
        event
        async for event in sse_frames(service.chat.continue_turn(conversation_id, request))
    ]


def test_manual_import_reuse_can_narrow_by_effective_sensitivity():
    service, _context, conversation, _messages, launch, _reference, _adapter, app_scope = _runtime(
        "synthetic_fifth", manual_import_maximum_sensitivity="personal"
    )
    from personal_ai.contracts.execution import ContinuationRequest, ExecutionChoice
    from personal_ai.llm.fake import FakeLLMClient

    request = ContinuationRequest(
        content="Use the selected record to continue.",
        idempotency_key=uuid4(),
        choice=ExecutionChoice(mode="manual_external"),
        launch_context=launch,
    )
    with application_scope_context(app_scope):
        prepared = service.prepare(conversation.id, request)
        imported = service.import_manual(
            conversation.id,
            prepared.message_id,
            prepared.reservation.package_fingerprint,
            "Imported answer excluded by the personal reuse ceiling.",
        )
        assert imported.execution.effective_sensitivity == "sensitive"

        llm = FakeLLMClient(["Follow-up without imported detail"], provider_id="automatic-fixture")
        service.chat._llm = llm
        automatic = request.model_copy(update={
            "idempotency_key": uuid4(),
            "choice": ExecutionChoice(mode="automatic"),
            "launch_context": launch,
        })
        import asyncio

        asyncio.run(_collect_stream(service, conversation.id, automatic))

    assert all(
        "Imported answer excluded by the personal reuse ceiling."
        not in message.content
        for message in llm.requests[-1]
    )


def test_launch_context_is_advisory_and_must_match_authenticated_request_scope():
    service, _context, conversation, messages, launch, _reference, adapter, app_scope = _runtime(
        "synthetic_fifth"
    )
    from personal_ai.contracts.execution import ContinuationRequest, ExecutionChoice

    request = ContinuationRequest(
        content="Use the selected record to continue.",
        idempotency_key=uuid4(),
        choice=ExecutionChoice(mode="manual_external"),
        launch_context=ApplicationLaunchContext(
            **launch.model_dump(exclude={"conversation_id"}),
            conversation_id=str(uuid4()),
        ),
    )
    with application_scope_context(app_scope), pytest.raises(
        ConversationConflictError, match="application_launch_scope_mismatch"
    ):
        service.prepare(conversation.id, request)
    assert messages.list_active(owner_id="owner-1", conversation_id=conversation.id) == []
    assert adapter.calls == []
