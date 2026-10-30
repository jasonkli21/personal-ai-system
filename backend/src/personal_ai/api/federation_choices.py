"""Resolve destination-scoped browser handles to canonical internal choices."""

from fastapi import HTTPException

from personal_ai.auth.application_clients import is_external_client_request
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import ApplicationScope, RequestScope
from personal_ai.context.providers import ContextPreparationError
from personal_ai.context.runtime import ContextRuntimeRegistry
from personal_ai.contracts.execution import ContinuationRequestPayload
from personal_ai.federation.service import FederationPermissionAuthority


def resolve_continuation_payload(
    payload: ContinuationRequestPayload,
    principal: AuthenticatedPrincipal,
    scope: RequestScope,
    runtime: ContextRuntimeRegistry,
):
    """Reject client-authored grant selectors and resolve only signed handles."""
    choices = ()
    if payload.federation_choice_ids:
        if is_external_client_request():
            raise HTTPException(status_code=403, detail="external_federation_unavailable")
        acting_user_id = f"{principal.issuer}|{principal.subject}"
        if (
            not principal.authenticated
            or scope.owner_id != principal.owner_id
            or scope.acting_user_id != acting_user_id
        ):
            raise HTTPException(status_code=403, detail="federation_choice_invalid")
        authority = next(
            (
                value
                for value in runtime.permission_revalidators
                if isinstance(value, FederationPermissionAuthority)
            ),
            None,
        )
        if authority is None:
            raise HTTPException(status_code=503, detail="federation_authority_unavailable")
        try:
            choices = authority.resolve_choice_handles(
                principal,
                ApplicationScope(
                    application_id=scope.application_id,
                    workspace_id=scope.workspace_id,
                ),
                payload.federation_choice_ids,
            )
        except ContextPreparationError as error:
            raise HTTPException(status_code=503, detail="federation_authority_unavailable") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail="federation_choice_invalid") from error
    return payload.to_internal_request(federation_context=choices)
