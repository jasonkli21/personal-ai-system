"""Thin authenticated API over the registered authoritative-effect controller."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from personal_ai.api.dependencies import (
    get_application_registry,
    get_context_runtime_registry,
    get_conversation_repository,
    get_message_repository,
    get_request_scope,
    require_recent_auth,
)
from personal_ai.applications.registry import ApplicationRegistry
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import RequestScope
from personal_ai.context.runtime import ContextPermissionRevalidatorRegistry, ContextRuntimeRegistry
from personal_ai.mutations.contracts import (
    AuthenticatedCommandRequest,
    MutationAdapterContractError,
    MutationCandidateRequest,
    MutationError,
    MutationUnavailableError,
    ProposalView,
)
from personal_ai.mutations.deployment import configured_command_resolver
from personal_ai.mutations.outputs import CanonicalOutputResolver
from personal_ai.mutations.service import MutationService
from personal_ai.persistence.factory import persistence_factory
from personal_ai.settings import Settings, get_settings
from personal_ai.storage.errors import PersistenceConflict

router = APIRouter(prefix="/v1/mutations", tags=["mutations"])


def get_mutation_service(
    settings: Annotated[Settings, Depends(get_settings)],
    registry: Annotated[ApplicationRegistry, Depends(get_application_registry)],
    runtime: Annotated[ContextRuntimeRegistry, Depends(get_context_runtime_registry)],
    conversations: Annotated[object, Depends(get_conversation_repository)],
    messages: Annotated[object, Depends(get_message_repository)],
):
    return MutationService(
        persistence_factory(settings).mutation_repository(),
        registry,
        runtime,
        ContextPermissionRevalidatorRegistry(runtime.permission_revalidators),
        output_resolver=CanonicalOutputResolver(conversations, messages),
        command_resolver=configured_command_resolver(settings, runtime),
    )


Principal = Annotated[AuthenticatedPrincipal, Depends(require_recent_auth)]
Scope = Annotated[RequestScope, Depends(get_request_scope)]
Service = Annotated[MutationService, Depends(get_mutation_service)]


class ExactConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation_id: UUID
    binding: str = Field(pattern=r"^[0-9a-f]{64}$")


@router.get("/contracts")
def contracts(
    principal: Principal,
    scope: Scope,
    registry: Annotated[ApplicationRegistry, Depends(get_application_registry)],
):
    from personal_ai.contracts.delegated_tasks import task_manifest

    return {
        **task_manifest(),
        "application_id": scope.application_id,
        "operations": [
            operation.model_dump(mode="json")
            for operation in registry.get(scope.application_id).mutation_operations
        ],
    }


@router.post("/commands", response_model=ProposalView, status_code=201)
def create_command(
    command: AuthenticatedCommandRequest, principal: Principal, scope: Scope, service: Service
):
    return invoke(service, principal, scope, "create_from_command", command)


class TaskAuthorityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: dict
    effect: bool = Field(strict=True)


@router.post("/task-authority")
def task_authority(
    request: TaskAuthorityRequest, principal: Principal, scope: Scope, service: Service
):
    from personal_ai.contracts.delegated_tasks import DelegatedTaskRequest

    try:
        task = DelegatedTaskRequest.model_validate(request.task)
        allowed = service.check_task_authority(principal, scope, task, effect=request.effect)
        return {"allowed": allowed}
    except MutationUnavailableError as error:
        raise HTTPException(503, error.code) from error
    except (MutationError, ValueError):
        return {"allowed": False}


def invoke(service, principal, scope, method, *args, **kwargs):
    try:
        proposal = getattr(service, method)(principal, scope, *args, **kwargs)
        return service._present(principal, scope, proposal)
    except MutationUnavailableError as error:
        raise HTTPException(503, error.code) from error
    except MutationAdapterContractError as error:
        raise HTTPException(500, error.code) from error
    except MutationError as error:
        status = (
            422
            if error.code in {"mutation_candidate_not_applicable", "mutation_candidate_invalid"}
            else 404
            if error.code
            in {"mutation_not_found", "mutation_output_not_found", "mutation_output_not_active"}
            else 403
            if "denied" in error.code
            else 409
        )
        raise HTTPException(status, error.code) from error
    except PersistenceConflict as error:
        raise HTTPException(409, "mutation_revision_conflict") from error
    except ValueError as error:
        raise HTTPException(422, "mutation_contract_invalid") from error


@router.post("/candidates", response_model=ProposalView, status_code=201)
def create_candidate(
    candidate: MutationCandidateRequest,
    principal: Principal,
    scope: Scope,
    service: Service,
):
    return invoke(service, principal, scope, "create_from_output", candidate)


@router.get("/{proposal_id}", response_model=ProposalView)
def read(proposal_id: UUID, principal: Principal, scope: Scope, service: Service):
    try:
        return service.read_view(principal, scope, proposal_id)
    except MutationUnavailableError as error:
        raise HTTPException(503, error.code) from error
    except MutationError as error:
        status = (
            404 if error.code == "mutation_not_found" else (403 if "denied" in error.code else 409)
        )
        raise HTTPException(status, error.code) from error


@router.post("/{proposal_id}/validate", response_model=ProposalView)
def validate(proposal_id: UUID, principal: Principal, scope: Scope, service: Service):
    return invoke(service, principal, scope, "validate", proposal_id)


@router.post("/{proposal_id}/confirm", response_model=ProposalView)
def confirm(
    proposal_id: UUID,
    choice: ExactConfirmation,
    principal: Principal,
    scope: Scope,
    service: Service,
):
    return invoke(service, principal, scope, "confirm", proposal_id, **choice.model_dump())


@router.post("/{proposal_id}/apply", response_model=ProposalView)
def apply(
    proposal_id: UUID,
    choice: ExactConfirmation,
    principal: Principal,
    scope: Scope,
    service: Service,
):
    return invoke(service, principal, scope, "apply", proposal_id, **choice.model_dump())


@router.post("/{proposal_id}/reconcile", response_model=ProposalView)
def reconcile(proposal_id: UUID, principal: Principal, scope: Scope, service: Service):
    return invoke(service, principal, scope, "reconcile", proposal_id)
