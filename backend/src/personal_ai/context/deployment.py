"""Deployment assembly through explicitly selected existing catalogs."""

from personal_ai.context.runtime import (
    ContextRuntimeContribution,
    ContextRuntimeContributionCatalog,
    ContextRuntimeRegistry,
    compose_context_runtime,
)


def default_context_runtime_catalog(selected=None) -> ContextRuntimeContributionCatalog:
    return ContextRuntimeContributionCatalog.from_entry_points(selected=selected)


def configured_context_runtime(
    settings, *, catalog: ContextRuntimeContributionCatalog | None = None
) -> ContextRuntimeRegistry:
    source_runtime = (
        default_context_runtime_catalog(settings.application_contributions)
        if catalog is None
        else catalog
    ).compose(settings)
    from personal_ai.federation.deployment import configured_federation_contribution

    return compose_context_runtime(
        ContextRuntimeContribution(
            source_runtime.provider_factories,
            source_runtime.planning_rules,
            source_runtime.permission_revalidators,
            source_runtime.export_adapters,
            source_runtime.federation_cases,
            source_runtime.mutation_adapters,
            source_runtime.mutation_reconciliation_adapters,
        ),
        configured_federation_contribution(settings, source_runtime),
    )
