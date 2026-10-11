"""Authenticated ContextPackage and external-turn routes over canonical chat state."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import Field

from personal_ai.api.dependencies import (
    get_application_context,
    get_external_dispatch_signer,
    get_external_turn_service,
    get_provider_usage_accounting,
)
from personal_ai.api.schemas import APIModel
from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.auth.dispatch_grants import DispatchGrantSigner, SignedDispatchGrant
from personal_ai.contracts.execution import ContinuationRequest, ExternalFailureCode
from personal_ai.entities import Message
from personal_ai.llm.external import PreparedExecution
from personal_ai.routing.contracts import EndpointRef
from personal_ai.services.external_turns import (
    ContextPackage,
    ExternalTurnService,
)
from personal_ai.usage.contracts import ProviderUsageAccounting


def no_store(response: Response) -> None:
    """External context, grants and imported content must not enter HTTP caches."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"


router = APIRouter(
    prefix="/v1/conversations", tags=["external turns"], dependencies=[Depends(no_store)]
)


class ExplicitProfileOption(APIModel):
    endpoint: EndpointRef
    provider_id: str = Field(min_length=1, max_length=200)
    capabilities: tuple[str, ...] = Field(default=(), max_length=16)
    maximum_sensitivity: str = Field(min_length=1, max_length=32)


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


@router.get("/execution-options", response_model=ExecutionOptionsResponse)
def execution_options(
    context: Annotated[ApplicationContextRequest, Depends(get_application_context)],
    usage: Annotated[ProviderUsageAccounting, Depends(get_provider_usage_accounting)],
    signer: Annotated[DispatchGrantSigner | None, Depends(get_external_dispatch_signer)],
) -> ExecutionOptionsResponse:
    """Project only explicitly selectable, current P18 profiles and app policy modes."""
    allowed = set(context.definition.context_policy.external_execution_modes)
    resolver = getattr(usage, "endpoint_profile_resolver", None)
    if resolver is None or signer is None or "connected_provider" not in allowed:
        profiles = ()
    else:
        snapshot = resolver.endpoint_registry.refresh()
        profiles = tuple(
            ExplicitProfileOption(
                endpoint=profile.ref,
                provider_id=profile.provider_id,
                capabilities=tuple(sorted(profile.capabilities)),
                maximum_sensitivity=profile.data_use_policy.max_sensitivity,
            )
            for profile in snapshot.profiles
            if profile.enabled
            and profile.execution_mode == "CHATGPT_PLAN"
            and "streaming" in profile.capabilities
            and profile.context_limit_tokens is not None
            and profile.access_policy is not None
            and profile.access_policy.selection_mode == "explicit_only"
            and profile.access_policy.automation_eligible is False
            and profile.access_policy.credential_runtime == "user_local"
            and profile.access_policy.model_discovery == "account_specific"
            and profile.access_policy.hosted_conversation_state is False
            and profile.data_use_policy.status == "approved"
        )
    modes = ["automatic"]
    if "connected_provider" in allowed and profiles:
        modes.append("connected_provider")
    if "manual_external" in allowed:
        modes.append("manual_external")
    return ExecutionOptionsResponse(modes=tuple(modes), explicit_profiles=profiles)


@router.post(
    "/{conversation_id}/external-turns/prepare",
    response_model=PreparedTurnResponse,
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
