"""Authenticated ContextPackage and external-turn routes over canonical chat state."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import Field

from personal_ai.api.dependencies import (
    get_application_context,
    get_endpoint_registry,
    get_external_dispatch_signer,
    get_external_turn_service,
    get_settings,
)
from personal_ai.api.schemas import APIModel
from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.auth.dispatch_grants import DispatchGrantSigner, SignedDispatchGrant
from personal_ai.contracts.execution import ContinuationRequest, ExternalFailureCode
from personal_ai.entities import Message
from personal_ai.llm.external import PreparedExecution
from personal_ai.routing.contracts import EndpointRef
from personal_ai.routing.registry import EndpointRegistry
from personal_ai.services.external_turns import (
    ContextPackage,
    ExternalTurnService,
)
from personal_ai.settings import Settings


def no_store(response: Response) -> None:
    """External context, grants and imported content must not enter HTTP caches."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"


def require_external_turn_acceptance(
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Fail closed before resolving repositories or reading conversation data."""
    if not settings.external_turn_acceptance_enabled:
        raise HTTPException(status_code=404, detail="external_execution_not_accepted")


router = APIRouter(
    prefix="/v1/conversations", tags=["external turns"], dependencies=[Depends(no_store)]
)


class ExplicitProfileOption(APIModel):
    endpoint: EndpointRef
    provider_id: str = Field(min_length=1, max_length=200)
    capabilities: tuple[str, ...] = Field(default=(), max_length=16)
    maximum_sensitivity: str = Field(min_length=1, max_length=32)
    external_transport_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,63}$")


class ExecutionOptionsResponse(APIModel):
    modes: tuple[Literal["automatic", "connected_provider", "manual_external"], ...]
    explicit_profiles: tuple[ExplicitProfileOption, ...] = Field(default=(), max_length=32)


class PreparedTurnResponse(APIModel):
    message_id: UUID
    reservation_id: UUID
    mode: Literal["connected_provider", "manual_external"]
    provider_id: str | None = None
    model_id: str | None = None
    package_fingerprint: str
    context_package: ContextPackage
    portable_prompt: str | None = None
    connected_execution: PreparedExecution | None = None


class DispatchRequest(APIModel):
    connected_execution: PreparedExecution


class DispatchResponse(APIModel):
    proof: SignedDispatchGrant


class ManualImportRequest(APIModel):
    package_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    text: str = Field(min_length=1, max_length=20_000)
    provider_label: str | None = Field(
        default=None, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/ -]{0,199}$"
    )
    model_label: str | None = Field(
        default=None, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/ -]{0,199}$"
    )


class ConnectedCompletionRequest(APIModel):
    package_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    text: str = Field(min_length=1, max_length=20_000)
    latency_ms: int | None = Field(default=None, ge=0, le=3_600_000)
    input_tokens: int | None = Field(default=None, ge=0, le=2_000_000)
    output_tokens: int | None = Field(default=None, ge=0, le=2_000_000)


class AbandonRequest(APIModel):
    package_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class FailureRequest(AbandonRequest):
    code: ExternalFailureCode = ExternalFailureCode.EXECUTION_INTERRUPTED


class ContextPreviewSource(APIModel):
    category: str = Field(min_length=1, max_length=48)
    operation: str = Field(min_length=1, max_length=32)
    fields: tuple[str, ...] = Field(default=(), max_length=32)
    max_results: int = Field(ge=1, le=50)
    max_tokens: int | None = Field(default=None, ge=1, le=128_000)


class ContextPreviewExclusion(APIModel):
    category: str = Field(min_length=1, max_length=48)
    reason: str = Field(min_length=1, max_length=64)


class ContextPreviewResponse(APIModel):
    selected_message_count: int = Field(ge=0, le=20000)
    planned_sources: tuple[ContextPreviewSource, ...] = Field(default=(), max_length=16)
    excluded_sources: tuple[ContextPreviewExclusion, ...] = Field(default=(), max_length=64)


class ReconciliationResponse(APIModel):
    state: Literal[
        "not_found", "not_external", "prepared", "prepared_stale", "dispatched",
        "completed", "cancelled", "unknown",
    ]
    message_id: UUID | None = None
    package_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    mode: Literal["connected_provider", "manual_external"] | None = None
    expires_at: datetime | None = None
    stale_reason: str | None = Field(default=None, max_length=80)


@router.get("/execution-options", response_model=ExecutionOptionsResponse)
def execution_options(
    context: Annotated[ApplicationContextRequest, Depends(get_application_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExecutionOptionsResponse:
    """Project only explicitly selectable, current P18 profiles and app policy modes."""
    if not settings.external_turn_acceptance_enabled:
        return ExecutionOptionsResponse(modes=("automatic",), explicit_profiles=())
    allowed = set(context.definition.context_policy.external_execution_modes)
    signer: DispatchGrantSigner | None = get_external_dispatch_signer(settings)
    registry: EndpointRegistry | None = None
    if signer is not None and "connected_provider" in allowed:
        try:
            registry = get_endpoint_registry(settings)
        except Exception:  # noqa: BLE001 - optional connected discovery fails closed.
            registry = None
    if registry is None or signer is None or "connected_provider" not in allowed:
        profiles = ()
    else:
        profiles = tuple(
            ExplicitProfileOption(
                endpoint=profile.ref,
                provider_id=profile.provider_id,
                capabilities=tuple(sorted(profile.capabilities)),
                maximum_sensitivity=profile.data_use_policy.max_sensitivity,
                external_transport_id=profile.external_transport_id,
            )
            for profile in registry.list_explicitly_selectable(
                required_capabilities=frozenset({"streaming"}),
            )
            if profile.context_limit_tokens is not None
        )
    modes = ["automatic"]
    if "connected_provider" in allowed and profiles:
        modes.append("connected_provider")
    if "manual_external" in allowed:
        modes.append("manual_external")
    return ExecutionOptionsResponse(modes=tuple(modes), explicit_profiles=profiles)


@router.post(
    "/{conversation_id}/external-turns/preview",
    response_model=ContextPreviewResponse,
    dependencies=[Depends(require_external_turn_acceptance)],
)
def preview_external_turn(
    conversation_id: UUID,
    request: ContinuationRequest,
    service: Annotated[ExternalTurnService, Depends(get_external_turn_service)],
) -> ContextPreviewResponse:
    return ContextPreviewResponse.model_validate(service.preview(conversation_id, request))


@router.get(
    "/{conversation_id}/external-turns/requests/{idempotency_key}",
    response_model=ReconciliationResponse,
    dependencies=[Depends(require_external_turn_acceptance)],
)
def reconcile_external_turn(
    conversation_id: UUID,
    idempotency_key: UUID,
    service: Annotated[ExternalTurnService, Depends(get_external_turn_service)],
) -> ReconciliationResponse:
    return ReconciliationResponse.model_validate(service.reconcile(conversation_id, idempotency_key))


@router.post(
    "/{conversation_id}/external-turns/requests/{idempotency_key}/abandon",
    response_model=Message,
    dependencies=[Depends(require_external_turn_acceptance)],
)
def abandon_external_turn_by_key(
    conversation_id: UUID,
    idempotency_key: UUID,
    service: Annotated[ExternalTurnService, Depends(get_external_turn_service)],
) -> Message:
    return service.abandon_by_idempotency_key(conversation_id, idempotency_key)


@router.post(
    "/{conversation_id}/external-turns/prepare",
    response_model=PreparedTurnResponse,
    dependencies=[Depends(require_external_turn_acceptance)],
)
def prepare_external_turn(
    conversation_id: UUID,
    request: ContinuationRequest,
    service: Annotated[ExternalTurnService, Depends(get_external_turn_service)],
) -> PreparedTurnResponse:
    prepared = service.prepare(conversation_id, request)
    reservation = prepared.reservation
    return PreparedTurnResponse(
        message_id=prepared.message_id,
        reservation_id=reservation.reservation_id,
        mode=reservation.mode,
        provider_id=reservation.provider_id,
        model_id=reservation.model_id,
        package_fingerprint=reservation.package_fingerprint,
        context_package=prepared.context_package,
        portable_prompt=(
            prepared.portable_prompt if reservation.mode == "manual_external" else None
        ),
        connected_execution=prepared.connected_package,
    )


@router.post(
    "/{conversation_id}/external-turns/{message_id}/dispatch",
    response_model=DispatchResponse,
    dependencies=[Depends(require_external_turn_acceptance)],
)
def dispatch_external_turn(
    conversation_id: UUID,
    message_id: UUID,
    request: DispatchRequest,
    service: Annotated[ExternalTurnService, Depends(get_external_turn_service)],
) -> DispatchResponse:
    proof = service.dispatch_package(
        conversation_id, message_id, request.connected_execution
    )
    return DispatchResponse(proof=proof)


@router.post(
    "/{conversation_id}/external-turns/{message_id}/import",
    response_model=Message,
    dependencies=[Depends(require_external_turn_acceptance)],
)
def import_manual_response(
    conversation_id: UUID,
    message_id: UUID,
    request: ManualImportRequest,
    service: Annotated[ExternalTurnService, Depends(get_external_turn_service)],
) -> Message:
    return service.import_manual(
        conversation_id,
        message_id,
        request.package_fingerprint,
        request.text,
        provider_label=request.provider_label,
        model_label=request.model_label,
    )


@router.post(
    "/{conversation_id}/external-turns/{message_id}/complete",
    response_model=Message,
    dependencies=[Depends(require_external_turn_acceptance)],
)
def complete_connected_turn(
    conversation_id: UUID,
    message_id: UUID,
    request: ConnectedCompletionRequest,
    service: Annotated[ExternalTurnService, Depends(get_external_turn_service)],
) -> Message:
    return service.finalize_connected(
        conversation_id,
        message_id,
        request.package_fingerprint,
        request.text,
        latency_ms=request.latency_ms,
        input_tokens=request.input_tokens,
        output_tokens=request.output_tokens,
    )


@router.post(
    "/{conversation_id}/external-turns/{message_id}/abandon",
    response_model=Message,
    dependencies=[Depends(require_external_turn_acceptance)],
)
def abandon_external_turn(
    conversation_id: UUID,
    message_id: UUID,
    request: AbandonRequest,
    service: Annotated[ExternalTurnService, Depends(get_external_turn_service)],
) -> Message:
    return service.abandon(
        conversation_id, message_id, request.package_fingerprint
    )


@router.post(
    "/{conversation_id}/external-turns/{message_id}/fail",
    response_model=Message,
    dependencies=[Depends(require_external_turn_acceptance)],
)
def fail_external_turn(
    conversation_id: UUID,
    message_id: UUID,
    request: FailureRequest,
    service: Annotated[ExternalTurnService, Depends(get_external_turn_service)],
) -> Message:
    """Record a client-reported interrupted connected send as an unknown effect."""
    return service.report_failure(
        conversation_id,
        message_id,
        request.package_fingerprint,
        request.code,
    )
