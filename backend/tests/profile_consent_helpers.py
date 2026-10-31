"""Synthetic consent fixture only; never an installed source/identity issuer."""
from datetime import timedelta
from uuid import uuid4

from personal_ai.applications.registry import ApplicationRegistry
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.context.adapters import BuiltInContextPermissionRevalidator
from personal_ai.context.profile import GlobalProfileContextProviderFactory
from personal_ai.context.profile_consent import ProfileShareIntent
from personal_ai.settings import Settings


def enable_profile(monkeypatch, repository, context, fields, settings=None):
    settings = settings or Settings(ai_provider="fake", ai_model="fixture")
    settings.profile_sharing_enabled = True
    principal = AuthenticatedPrincipal(
        issuer="https://accounts.google.com", subject="synthetic-fixture", owner_id=context.scope.owner_id,
        email=None, issued_at=0, authenticated=True,
    )
    actor = f"{principal.issuer}|{principal.subject}"
    scope = context.scope.model_copy(update={"acting_user_id": actor})
    context = context.model_copy(update={"scope": scope})
    class Membership:
        def is_member(self, principal, app, workspace):
            return app == scope.application_id and workspace == scope.workspace_id
    definition = context.definition.model_copy(update={
        "tool_ids": (), "comparison_domain_ids": (),
        "cross_application": context.definition.cross_application.model_copy(update={"application_ids": ()}),
    })
    registry = ApplicationRegistry(
        (definition,), context.context_provider_capabilities,
        workspace_authorizers={scope.application_id: Membership()},
    )
    for field in fields:
        state = repository.get_consents(scope.owner_id)
        profile = repository.get(scope.owner_id)
        repository.mutate_consent(scope.owner_id, actor, ProfileShareIntent(
            operation_id=uuid4(), operation="grant", grant_id=uuid4(), field=field,
            destination=scope.model_dump(include={"application_id", "workspace_id"}),
            expected_revision=state.revision, expected_profile_revision=profile.revision,
            expires_at=repository._clock() + timedelta(hours=1),
        ))
    monkeypatch.setattr("personal_ai.auth.scope.current_verified_principal", lambda: principal)
    monkeypatch.setattr("personal_ai.context.profile.current_verified_principal", lambda: principal)
    return (
        GlobalProfileContextProviderFactory(repository, settings, registry, lambda: None), context,
        BuiltInContextPermissionRevalidator(settings, repository, registry, lambda: None),
    )
