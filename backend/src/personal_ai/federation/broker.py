"""Generic export broker installed as an ordinary shared context contribution."""

from dataclasses import dataclass
from time import monotonic
from typing import Protocol

from personal_ai.applications.contracts import SENSITIVITY_RANK
from personal_ai.auth.scope import ApplicationScope
from personal_ai.context.providers import (
    ContextItem,
    ContextOperationSpec,
    ContextPermissionDependency,
    ContextPreparationError,
    ContextProviderSpec,
)
from personal_ai.context.runtime import ContextRuntimeContribution
from personal_ai.contracts.context_references import ContextEntityReference, FederationProvenance
from personal_ai.contracts.federation import FederationExportDeclaration
from personal_ai.federation.contracts import FederationGrantIntent


class FederationExportAdapter(Protocol):
    """Source authority must check membership/policy without reading domain values.

    fetch receives the authorized exact grant/selection; implementations must issue
    a narrow export request, never retrieve a broad record and filter afterward.
    Returned items must carry exact revision and revocable source dependencies.
    Completeness is explicit so empty results cannot be confused with truncation.
    """

    def resolve_source_policy(
        self, intent: FederationGrantIntent, *, deadline: float
    ) -> ContextPermissionDependency:
        """Resolve current source policy without reading domain values."""
        ...

    def authorize_export(self, grant, selection, scope, *, deadline: float) -> bool:
        """Check current source eligibility for exact category/fields/entities/purpose.

        This is a metadata/policy check, not retrieval of source values. Permission
        dependencies must version every restriction affecting later derived reuse.
        """
        ...

    def fetch(self, grant, selection, scope, *, deadline) -> "FederationExportResult": ...


@dataclass(frozen=True)
class FederationExportResult:
    """A complete bounded export, including explicitly authoritative empty entities."""

    items: tuple[ContextItem, ...]
    complete: bool
    authoritative_empty_entities: tuple[ContextEntityReference, ...] = ()
    continuation: str | None = None


@dataclass(frozen=True)
class FederationCase:
    source_application_id: str
    destination_application_id: str
    export: FederationExportDeclaration


class FederationProvider:
    def __init__(self, case, authority, adapter=None):
        self.case, self.authority, self.adapter = case, authority, adapter
        self.spec = ContextProviderSpec(
            provider_id=case.export.provider_id,
            source_class="domain_current",
            source_version="federation-export-v1",
            operations=(
                ContextOperationSpec(operation="entity", allowed_fields=case.export.fields),
            ),
        )

    def authorize_selection(self, selection, scope):
        try:
            grant = self._authorize_selection(selection, scope)
        except ContextPreparationError as error:
            self.authority.record_selection(selection, scope, error.code)
            raise
        self.authority.record_selection(selection, scope, "authorized")
        return grant

    def _authorize_selection(self, selection, scope):
        hint = selection.federation
        if hint is None or scope.acting_user_id is None:
            raise ContextPreparationError("context_federation_grant_required")
        grant = self.authority.repository.get(scope.owner_id, hint.grant_id)
        if grant is None or not grant.current(self.authority.clock()):
            raise ContextPreparationError("context_federation_grant_denied")
        if (
            hint.issuance_id != grant.issuance_id
            or hint.revision != grant.revision
            or hint.epoch != grant.epoch
            or scope.acting_user_id != grant.acting_user_id
            or grant.destination
            != ApplicationScope(
                application_id=scope.application_id, workspace_id=scope.workspace_id
            )
            or hint.source != grant.source
            or hint.category != grant.category
            or hint.purpose != grant.purpose
            or not set(hint.entities) <= set(grant.entities)
            or not selection.fields
            or not set(selection.fields) <= set(grant.fields)
            or not set(selection.fields) <= set(self.case.export.fields)
            or grant.category != self.case.export.category
            or grant.source.application_id != self.case.source_application_id
            or grant.destination.application_id != self.case.destination_application_id
            or selection.operation != "entity"
            or selection.entity_refs
            or selection.window_start is not None
        ):
            raise ContextPreparationError("context_federation_scope_denied")
        # Source policy is independently registered; a grant never substitutes for it.
        if not self.authority.source_is_current(grant.source_policy):
            raise ContextPreparationError("context_federation_source_policy_denied")
        if self.adapter is None:
            raise ContextPreparationError("context_federation_export_unavailable")
        try:
            policy_deadline = monotonic() + selection.timeout_seconds
            eligible = (
                self.adapter.authorize_export(grant, selection, scope, deadline=policy_deadline)
                is True
                and monotonic() < policy_deadline
            )
        except Exception:  # noqa: BLE001 - unavailable source eligibility denies access
            eligible = False
        if not eligible:
            raise ContextPreparationError("context_federation_source_policy_denied")
        current = self.authority.repository.get(scope.owner_id, hint.grant_id)
        if current is None or not current.current(self.authority.clock()) or current != grant:
            raise ContextPreparationError("context_federation_grant_denied")
        return grant

    def validate_selection(self, selection, inputs):
        self.authorize_selection(selection, inputs.scope)

    def resolve_source_policy(self, intent: FederationGrantIntent, *, deadline: float):
        if (
            self.adapter is None
            or intent.source.application_id != self.case.source_application_id
            or intent.destination.application_id != self.case.destination_application_id
            or intent.category != self.case.export.category
            or not set(intent.fields) <= set(self.case.export.fields)
        ):
            raise ContextPreparationError("context_federation_export_unavailable")
        resolver = getattr(self.adapter, "resolve_source_policy", None)
        if not callable(resolver):
            raise ContextPreparationError("context_federation_source_policy_unavailable")
        try:
            dependency = resolver(intent, deadline=deadline)
        except Exception as error:
            raise ContextPreparationError(
                "context_federation_source_policy_unavailable"
            ) from error
        if (
            not isinstance(dependency, ContextPermissionDependency)
            or dependency.permission_id.startswith("federation_grant:")
            or dependency.owner_id != intent.owner_id
            or dependency.acting_user_id != intent.acting_user_id
            or dependency.source_scope != intent.source
            or dependency.purpose != intent.purpose
            or not self.authority.source_is_current(dependency)
            or monotonic() >= deadline
        ):
            raise ContextPreparationError("context_federation_source_policy_denied")
        return dependency

    def fetch(self, selection, scope, *, deadline):
        grant = self.authorize_selection(selection, scope)
        response = self.adapter.fetch(grant, selection, scope, deadline=deadline)
        if (
            not isinstance(response, FederationExportResult)
            or response.complete is not True
            or response.continuation is not None
            or not isinstance(response.items, tuple)
            or any(not isinstance(item, ContextItem) for item in response.items)
            or not isinstance(response.authoritative_empty_entities, tuple)
            or any(
                not isinstance(entity, ContextEntityReference)
                for entity in response.authoritative_empty_entities
            )
            or len(response.items) > selection.max_results
            or (deadline is not None and monotonic() >= deadline)
        ):
            raise ContextPreparationError("context_federation_export_incomplete")
        selected_entities = set(selection.federation.entities)
        empty_entities = set(response.authoritative_empty_entities)
        if len(empty_entities) != len(response.authoritative_empty_entities):
            raise ContextPreparationError("context_federation_export_incomplete")
        present_entities = {
            entity for item in response.items for entity in item.entity_refs
        }
        if (
            not present_entities <= selected_entities
            or not empty_entities <= selected_entities
            or present_entities & empty_entities
            or present_entities | empty_entities != selected_entities
        ):
            raise ContextPreparationError("context_federation_export_incomplete")
        if sum(len(item.model_dump_json().encode("utf-8")) for item in response.items) > selection.max_bytes:
            raise ContextPreparationError("context_federation_export_incomplete")
        self.authorize_selection(selection, scope)
        hint = selection.federation
        result = []
        for item in response.items:
            if (
                item.owner_id != scope.owner_id
                or item.application_id != grant.source.application_id
                or item.workspace_id != grant.source.workspace_id
                or not item.entity_refs
                or not set(item.entity_refs) <= set(hint.entities)
                or not item.permission_dependencies
                or grant.source_policy not in item.permission_dependencies
                or any(
                    not any(
                        dependency.entity_ref == entity
                        and dependency.source_revision == item.source_version
                        for dependency in item.permission_dependencies
                    )
                    for entity in item.entity_refs
                )
                or not item.source_refs
                or any(ref.fingerprint is None for ref in item.source_refs)
                or item.partial_result
                or (item.omitted_count is not None and item.omitted_count > 0)
                or item.observed_at is None
                or item.expires_at is None
                or item.expires_at <= self.authority.clock()
                or item.federation is not None
                or any(
                    dep.source_application_id is not None for dep in item.permission_dependencies
                )
                or set(item.payload.model_dump(exclude_none=True)) - set(selection.fields)
            ):
                raise ContextPreparationError("context_federation_source_contract_invalid")
            for dependency in item.permission_dependencies:
                if (
                    dependency.owner_id != grant.owner_id
                    or dependency.acting_user_id != grant.acting_user_id
                    or dependency.source_scope != grant.source
                    or dependency.purpose != grant.purpose
                    or not self.authority.source_is_current(dependency)
                ):
                    raise ContextPreparationError("context_federation_source_policy_denied")
            sensitivity = max(
                (item.sensitivity, self.case.export.sensitivity, grant.sensitivity),
                key=SENSITIVITY_RANK.__getitem__,
            )
            if SENSITIVITY_RANK[sensitivity] > SENSITIVITY_RANK[grant.maximum_sensitivity]:
                raise ContextPreparationError("context_federation_sensitivity_denied")
            if len(item.permission_dependencies) >= 16:
                raise ContextPreparationError("context_federation_dependency_limit")
            # The destination owns only the disclosure envelope. Source truth and
            # exact revisions/references survive separately; no source entity is
            # reinterpreted as a destination-owned entity.
            result.append(
                item.model_copy(
                    update={
                        "provider_id": self.spec.provider_id,
                        "source_class": self.spec.source_class,
                        "application_id": scope.application_id,
                        "workspace_id": scope.workspace_id,
                        "entity_refs": (),
                        "inherited_source_classes": tuple(
                            dict.fromkeys((*item.inherited_source_classes, item.source_class))
                        ),
                        "sensitivity": sensitivity,
                        "expires_at": min(item.expires_at, grant.expires_at),
                        "permission_dependencies": (
                            *item.permission_dependencies,
                            grant.dependency(),
                        ),
                        "federation": FederationProvenance(
                            source_provider_id=item.provider_id,
                            source=grant.source,
                            destination=grant.destination,
                            category=grant.category,
                            entities=item.entity_refs,
                            grant_id=grant.grant_id,
                            grant_issuance_id=grant.issuance_id,
                            grant_revision=grant.revision,
                            grant_epoch=grant.epoch,
                            purpose=grant.purpose,
                        ),
                    }
                )
            )
        self.authorize_selection(selection, scope)
        return tuple(result)


def federation_contribution(cases, authority, adapters=None):
    """Same composition seam for deployment and synthetic conformance adapters."""
    adapters = adapters or {}
    ids = [case.export.provider_id for case in cases]
    if len(set(ids)) != len(ids) or set(adapters) - set(ids):
        raise ValueError("federation_registration_invalid")
    if any(
        not callable(getattr(adapter, "authorize_export", None))
        or not callable(getattr(adapter, "resolve_source_policy", None))
        or not callable(getattr(adapter, "fetch", None))
        for adapter in adapters.values()
    ):
        raise ValueError("federation_export_authorization_contract_required")
    providers = {
        case.export.provider_id: FederationProvider(
            case, authority, adapters.get(case.export.provider_id)
        )
        for case in cases
    }
    authority.bind_exports(providers.values())
    return ContextRuntimeContribution(
        provider_factories=providers, permission_revalidators=(authority,)
    )
