"""Initial feature allowlist; domain names stay out of generic broker control flow."""

from personal_ai.applications.contracts import (
    CapabilityRegistration,
    ContextFieldPolicy,
    ContextOperationPolicy,
    ContextProviderPolicy,
)
from personal_ai.context.runtime import ContextPermissionRevalidatorRegistry
from personal_ai.contracts.federation import FederationExportDeclaration
from personal_ai.federation.broker import FederationCase, federation_contribution
from personal_ai.federation.service import FederationPermissionAuthority

INITIAL_FEDERATION_CASES = (
    FederationCase(
        "health",
        "travel",
        FederationExportDeclaration(
            category="dietary_restrictions",
            provider_id="federation.health_dietary_to_travel",
            fields=("dietary_restrictions",),
            sensitivity="restricted",
        ),
    ),
    FederationCase(
        "health",
        "shopping",
        FederationExportDeclaration(
            category="ergonomic_constraints",
            provider_id="federation.health_ergonomic_to_shopping",
            fields=("ergonomic_constraints",),
            sensitivity="restricted",
        ),
    ),
    FederationCase(
        "travel",
        "shopping",
        FederationExportDeclaration(
            category="trip",
            provider_id="federation.travel_trip_to_shopping",
            fields=("destination", "start_date", "end_date"),
            sensitivity="sensitive",
        ),
    ),
    FederationCase(
        "finance",
        "shopping",
        FederationExportDeclaration(
            category="discretionary_budget",
            provider_id="federation.finance_budget_to_shopping",
            fields=("amount", "currency", "period"),
            sensitivity="restricted",
        ),
    ),
)


def install_federation_metadata(
    definitions, capabilities, cases=INITIAL_FEDERATION_CASES, *, implemented_provider_ids=()
):
    """Declare exports independently of installed executable adapters and permission."""
    implemented = frozenset(implemented_provider_ids)
    if implemented - {case.export.provider_id for case in cases}:
        raise ValueError("federation_implementation_not_declared")
    values = []
    case_provider_ids = {case.export.provider_id for case in cases}
    for definition in definitions:
        imports = tuple(
            case for case in cases if case.destination_application_id == definition.application_id
        )
        exports = tuple(
            export
            for export in definition.federation_exports
            if export.provider_id not in case_provider_ids
        ) + tuple(
            case.export for case in cases if case.source_application_id == definition.application_id
        )
        providers = tuple(
            ContextProviderPolicy(
                provider_id=case.export.provider_id,
                operations=(
                    ContextOperationPolicy(
                        operation="entity",
                        sensitivity=case.export.sensitivity,
                        fields=tuple(
                            ContextFieldPolicy(field=field, sensitivity=case.export.sensitivity)
                            for field in case.export.fields
                        ),
                    ),
                ),
            )
            for case in imports
        )
        values.append(
            definition.model_copy(
                update={
                    "federation_exports": exports,
                    "context_provider_ids": (
                        *(
                            provider_id
                            for provider_id in definition.context_provider_ids
                            if provider_id not in case_provider_ids
                        ),
                        *(case.export.provider_id for case in imports),
                    ),
                    "context_policy": definition.context_policy.model_copy(
                        update={
                            "provider_policies": (
                                *(
                                    provider
                                    for provider in definition.context_policy.provider_policies
                                    if provider.provider_id not in case_provider_ids
                                ),
                                *providers,
                            ),
                            "version": (
                                definition.context_policy.version
                                if not imports
                                or definition.context_policy.version.endswith(":federation-v1")
                                else f"{definition.context_policy.version}:federation-v1"
                            ),
                        }
                    ),
                }
            )
        )
    metadata = tuple(
        CapabilityRegistration(
            capability_id=case.export.provider_id,
            kind="context_provider",
            available=case.export.provider_id in implemented,
            unavailable_reason=None
            if case.export.provider_id in implemented
            else "narrow_source_export_and_identity_unverified",
        )
        for case in cases
    )
    remaining_capabilities = tuple(
        capability for capability in capabilities
        if capability.capability_id not in case_provider_ids
    )
    return tuple(values), (*remaining_capabilities, *metadata)


class _ConfiguredGrantRepository:
    """Lazy canonical persistence binding; startup never connects just for metadata."""

    def __init__(self, settings):
        self.settings = settings

    def get(self, owner_id, grant_id):
        from personal_ai.persistence.factory import persistence_factory

        return (
            persistence_factory(self.settings).federation_grant_repository().get(owner_id, grant_id)
        )

    def list_destination(self, owner_id, destination):
        from personal_ai.persistence.factory import persistence_factory

        return persistence_factory(self.settings).federation_grant_repository().list_destination(
            owner_id, destination
        )

    def record_access(self, selection, scope, result):
        from personal_ai.persistence.factory import persistence_factory

        return (
            persistence_factory(self.settings)
            .federation_grant_repository()
            .record_access(selection, scope, result)
        )

    def save(self, grant, *, expected_revision):
        from personal_ai.persistence.factory import persistence_factory

        return (
            persistence_factory(self.settings)
            .federation_grant_repository()
            .save(grant, expected_revision=expected_revision)
        )


def configured_federation_contribution(settings, source_runtime, *, cases=None):
    cases = (
        (*INITIAL_FEDERATION_CASES, *source_runtime.federation_cases)
        if cases is None
        else tuple(cases)
    )
    authority = FederationPermissionAuthority(
        _ConfiguredGrantRepository(settings),
        ContextPermissionRevalidatorRegistry(source_runtime.permission_revalidators),
    )
    return federation_contribution(cases, authority, source_runtime.export_adapters)


def reconcile_federation_runtime_metadata(registry, runtime):
    """Reconcile registered federation cases with installed runtime implementations."""
    from personal_ai.applications.registry import ApplicationRegistry
    from personal_ai.federation.broker import FederationProvider

    registrations = tuple(registry.registration(key) for key in sorted(registry.application_ids))
    definitions = tuple(app.definition for app in registrations)
    capabilities = {
        capability.capability_id: capability
        for app in registrations
        for capability in (*app.context_providers, *app.tools)
    }
    modules = {
        module.registration.domain_id: module
        for app in registrations
        for module in app.comparison_modules
    }
    if runtime.federation_cases:
        definitions, registered_capabilities = install_federation_metadata(
            definitions,
            tuple(capabilities.values()),
            cases=runtime.federation_cases,
        )
        capabilities = {item.capability_id: item for item in registered_capabilities}
    export_ids = {
        export.provider_id for definition in definitions for export in definition.federation_exports
    }
    for capability_id, capability in tuple(capabilities.items()):
        if capability_id in export_ids and capability.kind == "context_provider":
            provider = runtime.provider_factories.get(capability_id)
            available = isinstance(provider, FederationProvider) and provider.adapter is not None
            capabilities[capability_id] = capability.model_copy(
                update={
                    "available": available,
                    "unavailable_reason": None
                    if available
                    else "narrow_source_export_implementation_unavailable",
                }
            )
    return ApplicationRegistry(
        definitions, capabilities.values(), comparison_modules=modules
    )
