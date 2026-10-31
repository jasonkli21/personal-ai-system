"""Owner-authenticated management for sparse AI-owned profile defaults."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from personal_ai.api.dependencies import (
    get_application_registry,
    get_current_owner_id,
    get_global_profile_repository,
    get_request_scope,
    require_recent_auth,
)
from personal_ai.applications.registry import ApplicationRegistry
from personal_ai.auth.application_clients import is_external_client_request
from personal_ai.auth.scope import STANDALONE_APPLICATION_ID, RequestScope
from personal_ai.context.profile import (
    GlobalProfile,
    GlobalProfileRepository,
    GlobalProfileUpdate,
)
from personal_ai.context.profile_consent import (
    ConsentError,
    ProfileConsentService,
    ProfileShareIntent,
    ProfileShareReceipt,
)
from personal_ai.persistence.postgres import PersistenceConflict, PersistenceUnavailable
from personal_ai.settings import Settings, get_settings
from personal_ai.storage import StorageUnavailableError

router = APIRouter(prefix="/v1/profile", tags=["profile"])


def _require_profile_owner_scope(scope: RequestScope) -> None:
    if scope.application_id != STANDALONE_APPLICATION_ID or scope.workspace_id is not None:
        raise HTTPException(status_code=404, detail="not_found")


@router.get("", response_model=GlobalProfile)
def read_profile(
    owner_id: Annotated[str, Depends(get_current_owner_id)],
    scope: Annotated[RequestScope, Depends(get_request_scope)],
    repository: Annotated[GlobalProfileRepository, Depends(get_global_profile_repository)],
) -> GlobalProfile:
    _require_profile_owner_scope(scope)
    try:
        return repository.get(owner_id)
    except (PersistenceUnavailable, TimeoutError) as error:
        raise StorageUnavailableError("profile storage unavailable") from error


@router.put("", response_model=GlobalProfile)
def update_profile(
    update: GlobalProfileUpdate,
    owner_id: Annotated[str, Depends(get_current_owner_id)],
    scope: Annotated[RequestScope, Depends(get_request_scope)],
    registry: Annotated[ApplicationRegistry, Depends(get_application_registry)],
    repository: Annotated[GlobalProfileRepository, Depends(get_global_profile_repository)],
) -> GlobalProfile:
    _require_profile_owner_scope(scope)
    if any(
        application_id not in registry.application_ids
        for entry in update.fields
        for application_id in entry.shared_with_applications
    ):
        raise HTTPException(status_code=422, detail="profile_sharing_application_not_registered")
    if any(entry.shared_with_applications for entry in update.fields):
        raise HTTPException(status_code=409, detail="profile_sharing_requires_consent")
    try:
        return repository.update(owner_id, update)
    except (PersistenceUnavailable, TimeoutError) as error:
        raise StorageUnavailableError("profile storage unavailable") from error
    except PersistenceConflict as error:
        raise HTTPException(status_code=409, detail="profile_update_conflict") from error


def get_profile_consent_service(
    request: Request,
    scope: Annotated[RequestScope, Depends(get_request_scope)],
    principal: Annotated[object, Depends(require_recent_auth)],
    settings: Annotated[Settings, Depends(get_settings)],
    registry: Annotated[ApplicationRegistry, Depends(get_application_registry)],
    repository: Annotated[GlobalProfileRepository, Depends(get_global_profile_repository)],
):
    _require_profile_owner_scope(scope)
    if not settings.profile_sharing_enabled:
        raise HTTPException(status_code=404, detail="not_found")
    if (
        is_external_client_request()
        or principal.audience != settings.auth_audience
        or principal.authorized_party != settings.auth_audience
        or principal.issuer != "https://accounts.google.com"
        or principal.owner_id != scope.owner_id
        or scope.acting_user_id != f"{principal.issuer}|{principal.subject}"
    ):
        raise HTTPException(status_code=404, detail="not_found")
    return ProfileConsentService(repository, registry, principal)


@router.get("/shares")
def list_profile_shares(service: Annotated[ProfileConsentService, Depends(get_profile_consent_service)]):
    try:
        return service.list()
    except Exception as error:
        raise StorageUnavailableError("profile consent storage unavailable") from error


@router.post("/shares", response_model=ProfileShareReceipt)
def mutate_profile_share(
    intent: ProfileShareIntent,
    service: Annotated[ProfileConsentService, Depends(get_profile_consent_service)],
    if_match: Annotated[str | None, Header()] = None,
):
    if if_match != f'"{intent.expected_revision}"':
        raise HTTPException(status_code=409, detail="profile_share_conflict")
    try:
        return service.mutate(intent)
    except ConsentError as error:
        status = 422 if str(error) == "profile_share_expiry_invalid" else 409
        raise HTTPException(status_code=status, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail="profile_share_unknown_commit") from error
