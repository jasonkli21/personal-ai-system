"""FastAPI dependencies for the Phase 1 conversation surface."""

import base64
import time
from typing import Annotated

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import Depends, HTTPException, Request

from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.applications.registry import (
    ApplicationNotRegisteredError,
    ApplicationRegistry,
    application_registry_for,
)
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.dispatch_grants import DispatchGrantSigner
from personal_ai.auth.scope import (
    STANDALONE_APPLICATION_ID,
    DenyWorkspaceAuthorizer,
    RequestScope,
    WorkspaceAuthorizer,
)
from personal_ai.context import ContextAssembler
from personal_ai.context.adapters import (
    BuiltInContextPermissionRevalidator,
    ClientContextProviderFactory,
    ConversationContextProviderFactory,
    MemoryContextProviderFactory,
    ResearchEvidenceContextProviderFactory,
)
from personal_ai.context.contracts import ConversationSummaryRepository
from personal_ai.context.planner import ContextPlanner
from personal_ai.context.profile import GlobalProfileContextProviderFactory
from personal_ai.context.providers import ContextProviderCoordinator
from personal_ai.context.runtime import (
    EMPTY_CONTEXT_RUNTIME_REGISTRY,
    ContextPermissionRevalidatorRegistry,
    ContextRuntimeRegistry,
)
from personal_ai.context.tokens import EstimatedTokenCounter
from personal_ai.context.traces import ContextTraceRepository
from personal_ai.llm import GeminiLLMClient, GenerationClient
from personal_ai.llm.context import GeminiConversationSummarizer, GeminiTokenCounter
from personal_ai.llm.memory import GeminiMemoryAdapter
from personal_ai.memory.lifecycle.jobs import MemoryLifecycleCoordinator, PubSubMemoryJobPublisher
from personal_ai.memory.services import MemoryExtractionService, MemoryRetriever
from personal_ai.persistence.factory import persistence_factory
from personal_ai.routing.registry import EndpointRegistry
from personal_ai.services import ChatTurnService, ConversationService
from personal_ai.services.external_turns import ExternalTurnService
from personal_ai.services.external_turns.authority import PrincipalBoundExternalTurnAuthority
from personal_ai.settings import Settings, get_settings
from personal_ai.storage.repositories import ConversationRepository, MessageRepository
from personal_ai.usage.contracts import ProviderUsageAccounting


def get_current_owner_id(request: Request) -> str:
    """Return only the owner resolved from the application authentication boundary."""
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise HTTPException(status_code=401, detail="authentication_required")
    return principal.owner_id


def get_current_principal(request: Request):
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise HTTPException(status_code=401, detail="authentication_required")
    return principal


def get_workspace_authorizer() -> WorkspaceAuthorizer:
    """Fail closed until the app injects a canonical membership adapter."""
    return DenyWorkspaceAuthorizer()


def get_request_scope(request: Request) -> RequestScope:
    """Return scope validated by auth middleware, including server owner identity."""
    scope = getattr(request.state, "request_scope", None)
    if scope is None:
        raise HTTPException(status_code=401, detail="authentication_required")
    return scope


def get_application_registry(request: Request) -> ApplicationRegistry:
    """Return the registry installed on this app or the built-in manifest registry."""
    return application_registry_for(request)


def get_application_context(
    scope: Annotated[RequestScope, Depends(get_request_scope)],
    registry: Annotated[ApplicationRegistry, Depends(get_application_registry)],
) -> ApplicationContextRequest:
    """Resolve app metadata independently of orchestration or domain-name branches."""
    try:
        definition = registry.get(scope.application_id)
    except ApplicationNotRegisteredError as error:
        raise HTTPException(status_code=404, detail=error.code) from error
    if definition.workspace_kind == "unsupported" and scope.workspace_id is not None:
        raise HTTPException(status_code=400, detail="application_workspace_unsupported")
    if definition.workspace_kind == "required" and scope.workspace_id is None:
        raise HTTPException(status_code=400, detail="application_workspace_required")
    try:
        registration = registry.registration(scope.application_id)
        return ApplicationContextRequest(
            definition=definition,
            scope=scope,
            context_provider_capabilities=registration.context_providers,
            tool_capabilities=registration.tools,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail="application_context_invalid") from error


def require_standalone_application_scope(
    scope: Annotated[RequestScope, Depends(get_request_scope)],
) -> RequestScope:
    """Keep current Travel/Shopping comparison tools in Personal AI's namespace."""
    if scope.application_id != STANDALONE_APPLICATION_ID or scope.workspace_id is not None:
        # A comparison domain label does not establish an external app identity.
        raise HTTPException(status_code=404, detail="not_found")
    return scope


def require_recent_auth(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Require a recently issued Google credential for account lifecycle actions."""
    principal = get_current_principal(request)
    now = int(time.time())
    if (
        not principal.authenticated
        or principal.issued_at > now + 60
        or now - principal.issued_at > settings.auth_recent_token_seconds
    ):
        raise HTTPException(status_code=401, detail="reauthentication_required")
    return principal


def get_conversation_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConversationRepository:
    """Build the production conversation repository from application settings."""
    return persistence_factory(settings).conversation_repository()


def get_message_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> MessageRepository:
    """Build the production message repository from application settings."""
    return persistence_factory(settings).message_repository()


def get_provider_usage_accounting(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProviderUsageAccounting:
    """Build the Postgres admission ledger and its bounded DynamoDB event writer."""
    return persistence_factory(settings).provider_usage_accounting(settings)


def get_conversation_service(
    conversations: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    messages: Annotated[MessageRepository, Depends(get_message_repository)],
    owner_id: Annotated[str, Depends(get_current_owner_id)],
    application_context: Annotated[ApplicationContextRequest, Depends(get_application_context)],
) -> ConversationService:
    """Compose the conversation use cases from injectable boundaries."""
    return ConversationService(
        conversations, messages, owner_id=owner_id, application_context=application_context
    )


def get_llm_client(
    settings: Annotated[Settings, Depends(get_settings)],
    usage: Annotated[ProviderUsageAccounting, Depends(get_provider_usage_accounting)],
) -> GenerationClient:
    """Build the configured provider behind the replaceable streaming contract."""
    return GeminiLLMClient(settings, usage_accounting=usage)


def get_summary_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConversationSummaryRepository:
    return persistence_factory(settings).summary_repository()


def get_context_trace_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ContextTraceRepository:
    factory = persistence_factory(settings)
    repository = factory.context_trace_repository()
    if settings.artifacts_enabled:
        from personal_ai.artifacts.consumers import ArtifactContextTraceRepository

        return ArtifactContextTraceRepository(
            repository, lambda: factory.artifact_service(settings)
        )
    return repository


def get_context_runtime_registry(
    request: Request,
) -> ContextRuntimeRegistry:
    """Return deployment-installed adapters/rules, separate from app permissions."""
    return getattr(
        request.app.state,
        "context_runtime_registry",
        EMPTY_CONTEXT_RUNTIME_REGISTRY,
    )


def get_global_profile_repository(
    settings: Annotated[Settings, Depends(get_settings)],
):
    return persistence_factory(settings).global_profile_repository()


def get_context_research_repository(settings: Annotated[Settings, Depends(get_settings)]):
    """Reuse the canonical repository for explicit selected research context."""
    if not settings.research_enabled:
        return None
    if settings.research_storage == "memory":
        from personal_ai.api.research import local_repository

        return local_repository()
    return persistence_factory(settings).research_repository()


def get_context_assembler(
    runtime: Annotated[ContextRuntimeRegistry, Depends(get_context_runtime_registry)],
    settings: Annotated[Settings, Depends(get_settings)],
    summaries: Annotated[ConversationSummaryRepository, Depends(get_summary_repository)],
    profile_repository: Annotated[object, Depends(get_global_profile_repository)],
    usage: Annotated[ProviderUsageAccounting, Depends(get_provider_usage_accounting)],
    research_repository: Annotated[object, Depends(get_context_research_repository)],
) -> ContextAssembler:
    built_in_providers = {
        "ai_memory": MemoryContextProviderFactory(settings),
        "client_context": ClientContextProviderFactory(),
        "conversation_history": ConversationContextProviderFactory(),
        "external_research": ResearchEvidenceContextProviderFactory(research_repository),
        "global_profile": GlobalProfileContextProviderFactory(profile_repository),
    }
    overlap = set(built_in_providers).intersection(runtime.provider_factories)
    if overlap:
        raise ValueError("context_runtime_provider_conflicts_with_builtin")
    providers = ContextProviderCoordinator(
        {**built_in_providers, **runtime.provider_factories},
        feature_flags={
            "memory_enabled": settings.memory_enabled,
            "travel_context_enabled": settings.travel_context_enabled,
            "shopping_context_enabled": settings.shopping_context_enabled,
            "finance_context_enabled": settings.finance_context_enabled,
        },
    )
    return ContextAssembler(
        settings,
        GeminiTokenCounter(settings, usage_accounting=usage),
        summaries,
        GeminiConversationSummarizer(settings, usage_accounting=usage),
        context_provider_coordinator=providers,
        context_planner=ContextPlanner(runtime.planning_rules),
        permission_revalidator=ContextPermissionRevalidatorRegistry(
            (
                BuiltInContextPermissionRevalidator(settings, profile_repository),
                *runtime.permission_revalidators,
            )
        ),
    )


def get_external_context_assembler(
    automatic: Annotated[ContextAssembler, Depends(get_context_assembler)],
) -> ContextAssembler:
    """Share all context semantics while disabling remote count and summary calls."""
    return ContextAssembler(
        automatic.settings,
        EstimatedTokenCounter(),
        automatic.summaries,
        summarizer=None,
        context_provider_coordinator=automatic.context_provider_coordinator,
        permission_revalidator=automatic.permission_revalidator,
        context_planner=automatic.context_planner,
    )


def get_memory_repository(settings: Annotated[Settings, Depends(get_settings)]):
    if not settings.memory_enabled and not settings.memory_inspection_enabled:
        return None
    return persistence_factory(settings).memory_repository()


def get_memory_adapter(
    settings: Annotated[Settings, Depends(get_settings)],
    usage: Annotated[ProviderUsageAccounting, Depends(get_provider_usage_accounting)],
):
    return GeminiMemoryAdapter(settings, usage_accounting=usage)


def get_lifecycle_repository(
    settings: Annotated[Settings, Depends(get_settings)],
    memory_repository: Annotated[object, Depends(get_memory_repository)],
    messages: Annotated[MessageRepository, Depends(get_message_repository)],
):
    if not settings.memory_lifecycle_inspection_enabled or memory_repository is None:
        return None
    return persistence_factory(settings).memory_lifecycle_repository(memory_repository, messages)


def get_chat_turn_service(
    conversations: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    messages: Annotated[MessageRepository, Depends(get_message_repository)],
    llm: Annotated[GenerationClient, Depends(get_llm_client)],
    settings: Annotated[Settings, Depends(get_settings)],
    owner_id: Annotated[str, Depends(get_current_owner_id)],
    application_context: Annotated[ApplicationContextRequest, Depends(get_application_context)],
    context: Annotated[ContextAssembler, Depends(get_context_assembler)],
    context_traces: Annotated[ContextTraceRepository, Depends(get_context_trace_repository)],
    memory_repository: Annotated[object, Depends(get_memory_repository)],
    memory_adapter: Annotated[object, Depends(get_memory_adapter)],
    lifecycle_repository: Annotated[object, Depends(get_lifecycle_repository)],
) -> ChatTurnService:
    """Compose the durable streaming chat lifecycle."""
    retriever = extraction = lifecycle_coordinator = None
    if settings.memory_enabled and memory_repository is not None:
        lifecycle_repository = lifecycle_repository or persistence_factory(
            settings
        ).memory_lifecycle_repository(memory_repository, messages)
        retriever = MemoryRetriever(
            settings,
            memory_repository,
            messages,
            memory_adapter,
            lifecycle_repository,
            permission_revalidator=context.permission_revalidator,
        )
        if settings.memory_extraction_enabled:
            extraction = MemoryExtractionService(
                settings,
                memory_repository,
                messages,
                memory_adapter,
                memory_adapter,
            )
        if settings.memory_lifecycle_worker_enabled:
            publisher = (
                PubSubMemoryJobPublisher(settings) if settings.memory_lifecycle_topic else None
            )
            lifecycle_coordinator = MemoryLifecycleCoordinator(
                settings,
                lifecycle_repository,
                memory_repository,
                extraction=extraction,
                publisher=publisher,
            )
    return ChatTurnService(
        conversations,
        messages,
        llm,
        owner_id=owner_id,
        application_context=application_context,
        context_assembler=context,
        context_traces=context_traces,
        memory_retriever=retriever,
        memory_extraction=None if lifecycle_coordinator is not None else extraction,
        memory_lifecycle=lifecycle_coordinator,
        model=settings.ai_model,
        stale_stream_after_seconds=settings.request_timeout_seconds + 60,
    )


def get_external_dispatch_signer(
    settings: Annotated[Settings, Depends(get_settings)],
) -> DispatchGrantSigner | None:
    encoded = settings.external_dispatch_grant_private_key.get_secret_value().strip()
    if not encoded or not settings.external_dispatch_grant_key_id:
        return None
    try:
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        key = Ed25519PrivateKey.from_private_bytes(raw)
    except (ValueError, TypeError):
        return None
    return DispatchGrantSigner(
        issuer=settings.external_dispatch_grant_issuer,
        key_id=settings.external_dispatch_grant_key_id,
        key=key,
    )


def get_endpoint_registry(settings: Annotated[Settings, Depends(get_settings)]) -> EndpointRegistry:
    """Expose routing-owned endpoint admission independently of usage accounting."""
    factory = persistence_factory(settings)
    try:
        return factory.endpoint_profile_resolver(settings).endpoint_registry
    except Exception:  # noqa: BLE001 - unavailable routing authority fails closed.
        raise HTTPException(
            status_code=503, detail="external_endpoint_registry_unavailable"
        ) from None


def get_external_turn_service(
    chat: Annotated[ChatTurnService, Depends(get_chat_turn_service)],
    context: Annotated[ApplicationContextRequest, Depends(get_application_context)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    conversations: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    messages: Annotated[MessageRepository, Depends(get_message_repository)],
    context_assembler: Annotated[ContextAssembler, Depends(get_external_context_assembler)],
    registry: Annotated[EndpointRegistry, Depends(get_endpoint_registry)],
    settings: Annotated[Settings, Depends(get_settings)],
    signer: Annotated[DispatchGrantSigner | None, Depends(get_external_dispatch_signer)],
    workspace_authorizer: Annotated[WorkspaceAuthorizer, Depends(get_workspace_authorizer)],
) -> ExternalTurnService:
    """Compose external execution over existing P18, context, auth, and chat seams."""
    if not settings.external_turn_acceptance_enabled:
        raise HTTPException(status_code=404, detail="external_execution_not_accepted")
    authority = PrincipalBoundExternalTurnAuthority(
        principal=principal,
        conversations=conversations,
        messages=messages,
        permission_revalidator=context_assembler.permission_revalidator,
        workspace_authorizer=workspace_authorizer,
        allow_development_principal=(
            settings.auth_mode == "development" and settings.app_environment in {"local", "test"}
        ),
    )
    return ExternalTurnService(
        chat=chat,
        context=context,
        registry=registry,
        authority=authority,
        signer=signer,
        context_assembler=context_assembler,
    )
