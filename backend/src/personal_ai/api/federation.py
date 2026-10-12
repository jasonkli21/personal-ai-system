"""Explicit owner permission controls; source data never passes through this API."""

from typing import Annotated
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from personal_ai.api.dependencies import (
    get_application_registry,
    get_context_runtime_registry,
    get_request_scope,
    require_recent_auth,
)
from personal_ai.applications.registry import ApplicationNotRegisteredError, ApplicationRegistry
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import ApplicationScope, RequestScope
from personal_ai.context.providers import ContextPreparationError
from personal_ai.context.runtime import ContextRuntimeRegistry
from personal_ai.contracts.context_references import ContextEntityReference
from personal_ai.federation.contracts import (
    FederationGrant,
    FederationGrantConflict,
    FederationGrantIntent,
)
from personal_ai.federation.service import FederationPermissionAuthority
from personal_ai.persistence.postgres.database import PersistenceConflict

router = APIRouter(prefix="/v1/federation/grants", tags=["federation"])


class GrantChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: UUID
    source: ApplicationScope
    destination: ApplicationScope
    category: str = Field(min_length=1, max_length=80)
    purpose: str = Field(min_length=1, max_length=160)
    fields: tuple[str, ...] = Field(min_length=1, max_length=32)
    entities: tuple[ContextEntityReference, ...] = Field(min_length=1, max_length=16)
    expires_at: AwareDatetime


class GrantRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    expected_issuance_id: UUID


def authority_dependency(
    runtime: Annotated[ContextRuntimeRegistry, Depends(get_context_runtime_registry)],
    scope: Annotated[RequestScope, Depends(get_request_scope)],
):
    if scope.application_id != "personal_ai" or scope.workspace_id is not None:
        raise HTTPException(404, "not_found")
    authority = next(
        (
            value
            for value in runtime.permission_revalidators
            if isinstance(value, FederationPermissionAuthority)
        ),
        None,
    )
    if authority is None:
        raise HTTPException(503, "federation_authority_unavailable")
    return authority


@router.post("", response_model=FederationGrant, status_code=201)
def create_grant(
    choice: GrantChoice,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_recent_auth)],
    authority: Annotated[FederationPermissionAuthority, Depends(authority_dependency)],
    registry: Annotated[ApplicationRegistry, Depends(get_application_registry)],
):
    try:
        source = registry.get(choice.source.application_id)
        destination = registry.get(choice.destination.application_id)
    except ApplicationNotRegisteredError as error:
        raise HTTPException(403, "federation_case_denied") from error
    for definition, scope in ((source, choice.source), (destination, choice.destination)):
        if (definition.workspace_kind == "unsupported" and scope.workspace_id is not None) or (
            definition.workspace_kind == "required" and scope.workspace_id is None
        ):
            raise HTTPException(403, "federation_workspace_denied")
    export = next(
        (
            export
            for export in source.federation_exports
            if export.provider_id in destination.context_provider_ids
            and export.category == choice.category
        ),
        None,
    )
    if export is None or not set(choice.fields) <= set(export.fields):
        raise HTTPException(403, "federation_case_denied")
    try:
        intent = FederationGrantIntent(
            **choice.model_dump(exclude={"idempotency_key"}),
            grant_id=uuid5(
                NAMESPACE_URL, f"federation-grant:{principal.owner_id}:{choice.idempotency_key}"
            ),
            owner_id=principal.owner_id,
            acting_user_id=f"{principal.issuer}|{principal.subject}",
        )
        return authority.create(principal, intent)
    except ContextPreparationError as error:
        raise HTTPException(403, "federation_source_authority_unavailable") from error
    except (PersistenceConflict, FederationGrantConflict) as error:
        raise HTTPException(409, "federation_grant_conflict") from error
    except ValueError as error:
        raise HTTPException(422, "federation_grant_invalid") from error


@router.get("/{grant_id}", response_model=FederationGrant)
def read_grant(
    grant_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_recent_auth)],
    authority: Annotated[FederationPermissionAuthority, Depends(authority_dependency)],
):
    grant = authority.repository.get(principal.owner_id, grant_id)
    if grant is None:
        raise HTTPException(404, "not_found")
    return grant


@router.post("/{grant_id}/revoke", response_model=FederationGrant)
def revoke_grant(
    grant_id: UUID,
    revision: GrantRevision,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_recent_auth)],
    authority: Annotated[FederationPermissionAuthority, Depends(authority_dependency)],
):
    try:
        return authority.revoke(
            principal,
            grant_id,
            expected_revision=revision.expected_revision,
            expected_issuance_id=revision.expected_issuance_id,
        )
    except (PersistenceConflict, FederationGrantConflict) as error:
        raise HTTPException(409, "federation_grant_conflict") from error
    except ValueError as error:
        raise HTTPException(404, "federation_grant_not_found") from error
