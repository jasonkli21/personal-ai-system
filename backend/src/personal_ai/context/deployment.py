"""Deployment assembly for independently registered context contributions."""

from personal_ai.context.runtime import (
    ContextRuntimeContribution,
    ContextRuntimeContributionCatalog,
    ContextRuntimeRegistry,
    compose_context_runtime,
)


def default_context_runtime_catalog() -> ContextRuntimeContributionCatalog:
    """Load installed registrations, with source-tree registrations for local runs."""
    catalog = ContextRuntimeContributionCatalog.from_entry_points()
    if catalog.registration_names:
        return catalog

    from personal_ai.context.finance import configured_finance_context_contribution
    from personal_ai.context.health import configured_health_context_contribution
    from personal_ai.context.shopping import configured_shopping_context_contribution
    from personal_ai.context.travel import configured_travel_context_contribution

    return ContextRuntimeContributionCatalog(
        (
            ("finance", configured_finance_context_contribution),
            ("health", configured_health_context_contribution),
            ("shopping", configured_shopping_context_contribution),
            ("travel", configured_travel_context_contribution),
        )
    )


def configured_context_runtime(
    settings, *, catalog: ContextRuntimeContributionCatalog | None = None
) -> ContextRuntimeRegistry:
    """Compose installed registrations through the same startup extension seam."""
    source_runtime = (catalog or default_context_runtime_catalog()).compose(settings)

    from personal_ai.federation.deployment import configured_federation_contribution

    federation = configured_federation_contribution(settings, source_runtime)
    return compose_context_runtime(
        ContextRuntimeContribution(
            source_runtime.provider_factories, source_runtime.planning_rules,
            source_runtime.permission_revalidators,
            source_runtime.export_adapters,
            source_runtime.federation_cases,
        ),
        federation,
    )
