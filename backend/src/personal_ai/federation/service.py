"""Owner-only permission mutation and shared dependency revalidation."""

from datetime import UTC, datetime
from time import monotonic
from types import MappingProxyType
from uuid import UUID, uuid4

from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import current_request_scope
from personal_ai.context.providers import ContextPreparationError
from personal_ai.federation.contracts import (
    FederationGrant,
    FederationGrantConflict,
    FederationGrantIntent,
)
from personal_ai.persistence.postgres.database import PersistenceConflict


class FederationPermissionAuthority:
    permission_namespaces = ("federation_grant:",)

    def __init__(self, repository, source_permissions, *, clock=None):
        self.repository = repository
        self.source_permissions = source_permissions
        self.clock = clock or (lambda: datetime.now(UTC))
        self._exports = None

    def bind_exports(self, providers):
        """Retain the same registered adapter references for later grant reuse checks."""
        if self._exports is not None:
            raise ValueError("federation_export_authority_already_composed")
        exports = {}
        for provider in providers:
            case = provider.case
            key = (
                case.source_application_id,
                case.destination_application_id,
                case.export.category,
            )
            if key in exports:
                raise ValueError("federation_export_scope_ambiguous")
            exports[key] = provider
        self._exports = MappingProxyType(exports)

    def _export_current(self, grant, scope):
        from personal_ai.context.providers import ContextSelection
        from personal_ai.contracts.federation import FederationSelection

        if self._exports is None:
            return False
        provider = self._exports.get(
            (grant.source.application_id, grant.destination.application_id, grant.category)
        )
        if provider is None:
            return False
        hint = FederationSelection(
            **{field: getattr(grant, field) for field in FederationSelection.model_fields}
        )
        selection = ContextSelection(
            provider_id=provider.spec.provider_id,
            operation="entity",
            fields=grant.fields,
            federation=hint,
        )
        # Authorization only: never reconstruct/retrieve source values for reuse.
        provider._authorize_selection(selection, scope)
        return True

    def supports(self, dependency):
        return dependency.permission_id.startswith("federation_grant:")

    def record_selection(self, selection, scope, result):
        # Canonical audit storage receives only opaque/digested references, never values.
        self.repository.record_access(selection, scope, result)

    def source_is_current(self, dependency):
        try:
            return bool(self.source_permissions.is_current(dependency))
        except Exception:  # noqa: BLE001 - unavailable source authority denies access
            return False

    def is_current(self, dependency):
        scope = current_request_scope()
        if scope is None or (
            dependency.owner_id != scope.owner_id
            or dependency.acting_user_id != scope.acting_user_id
            or dependency.destination_application_id != scope.application_id
            or dependency.destination_workspace_id != scope.workspace_id
        ):
            return False
        try:
            grant = self.repository.get(
                scope.owner_id, UUID(dependency.permission_id.split(":", 1)[1])
            )
            return bool(
                grant
                and grant.current(self.clock())
                and grant.dependency() == dependency
                and self.source_is_current(grant.source_policy)
                and self._export_current(grant, scope)
            )
        except Exception:  # noqa: BLE001 - permission authority fails closed
            return False

    @staticmethod
    def _owner(principal: AuthenticatedPrincipal, owner_id):
        if not principal.authenticated or principal.owner_id != owner_id:
            raise ValueError("federation_grant_owner_denied")

    @staticmethod
    def _same_intent(grant: FederationGrant, intent: FederationGrantIntent) -> bool:
        return all(
            getattr(grant, field) == getattr(intent, field)
            for field in (
                "grant_id",
                "owner_id",
                "acting_user_id",
                "source",
                "destination",
                "category",
                "purpose",
                "entities",
                "fields",
                "expires_at",
            )
        )

    def create(self, principal, intent: FederationGrantIntent):
        self._owner(principal, intent.owner_id)
        if intent.acting_user_id != f"{principal.issuer}|{principal.subject}":
            raise ValueError("federation_delegation_denied")
        existing = self.repository.get(intent.owner_id, intent.grant_id)
        if existing is not None:
            if not self._same_intent(existing, intent):
                raise FederationGrantConflict("federation_grant_idempotency_conflict")
            return existing

        provider = (
            self._exports.get(
                (intent.source.application_id, intent.destination.application_id, intent.category)
            )
            if self._exports is not None
            else None
        )
        if (
            provider is None
            or not set(intent.fields) <= set(provider.case.export.fields)
            or any(
                entity.application_id != intent.source.application_id
                or entity.workspace_id != intent.source.workspace_id
                for entity in intent.entities
            )
        ):
            raise ContextPreparationError("context_federation_export_unavailable")

        source_policy = provider.resolve_source_policy(
            intent, deadline=monotonic() + 5.0
        )
        created_at = self.clock()
        grant = FederationGrant(
            grant_id=intent.grant_id,
            issuance_id=uuid4(),
            revision=1,
            epoch=1,
            source=intent.source,
            destination=intent.destination,
            owner_id=intent.owner_id,
            acting_user_id=intent.acting_user_id,
            category=intent.category,
            purpose=intent.purpose,
            entities=intent.entities,
            fields=intent.fields,
            expires_at=intent.expires_at,
            created_at=created_at,
            updated_at=created_at,
            source_policy=source_policy,
            sensitivity=provider.case.export.sensitivity,
            maximum_sensitivity=provider.case.export.sensitivity,
        )
        try:
            return self.repository.save(grant, expected_revision=0)
        except PersistenceConflict as error:
            # A simultaneous identical request may win the insert. Reload and
            # return its canonical issuance only when the requested intent matches.
            canonical = self.repository.get(intent.owner_id, intent.grant_id)
            if canonical is not None and self._same_intent(canonical, intent):
                return canonical
            raise FederationGrantConflict("federation_grant_idempotency_conflict") from error

    def revoke(self, principal, grant_id, *, expected_revision, expected_issuance_id=None):
        self._owner(principal, principal.owner_id)
        grant = self.repository.get(principal.owner_id, grant_id)
        if grant is None:
            raise ValueError("federation_grant_not_found")
        if expected_issuance_id is not None and expected_issuance_id != grant.issuance_id:
            raise FederationGrantConflict("federation_grant_issuance_conflict")
        if grant.state == "revoked":
            if expected_revision in (grant.revision, grant.revision - 1):
                return grant
            raise ValueError("federation_grant_revision_conflict")
        candidate = grant.model_copy(
            update={
                "state": "revoked",
                "revision": grant.revision + 1,
                "epoch": grant.epoch + 1,
                "revocation_id": uuid4(),
                "updated_at": self.clock(),
            }
        )
        try:
            return self.repository.save(candidate, expected_revision=expected_revision)
        except PersistenceConflict as error:
            canonical = self.repository.get(principal.owner_id, grant_id)
            issuance_matches = (
                expected_issuance_id is None
                or (canonical is not None and canonical.issuance_id == expected_issuance_id)
            )
            if (
                canonical is not None
                and canonical.state == "revoked"
                and issuance_matches
                and expected_revision in (canonical.revision, canonical.revision - 1)
            ):
                return canonical
            raise FederationGrantConflict("federation_grant_revision_conflict") from error
