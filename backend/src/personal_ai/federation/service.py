"""Owner-only permission mutation and shared dependency revalidation."""

from datetime import UTC, datetime
from types import MappingProxyType
from uuid import UUID, uuid4

from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import current_request_scope
from personal_ai.federation.contracts import FederationGrant, FederationGrantConflict


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

    def create(self, principal, grant: FederationGrant):
        self._owner(principal, grant.owner_id)
        if grant.acting_user_id != f"{principal.issuer}|{principal.subject}":
            raise ValueError("federation_delegation_denied")
        if grant.revision != 1 or grant.epoch != 1 or grant.state != "active":
            raise ValueError("federation_grant_initial_state_invalid")
        existing = self.repository.get(grant.owner_id, grant.grant_id)
        if existing is not None:
            mutable = {
                "issuance_id",
                "revision",
                "epoch",
                "created_at",
                "updated_at",
                "state",
                "revocation_id",
            }
            if existing.model_dump(exclude=mutable) != grant.model_dump(exclude=mutable):
                raise FederationGrantConflict("federation_grant_idempotency_conflict")
            return existing
        # Issuance belongs to this authority, never to a caller-supplied identifier.
        grant = grant.model_copy(update={"issuance_id": uuid4()})
        # Creating a permission does not establish current source access.
        return self.repository.save(grant, expected_revision=0)

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
        return self.repository.save(candidate, expected_revision=expected_revision)
