"""Deployment assembly for independently registered context contributions."""

from personal_ai.context.runtime import (
    ContextRuntimeContribution,
    ContextRuntimeRegistry,
    compose_context_runtime,
)


def configured_context_runtime(settings) -> ContextRuntimeRegistry:
    """Compose installed deployment contributions through the generic seam."""
    from personal_ai.context.finance import configured_finance_context_contribution
    from personal_ai.context.health import configured_health_context_contribution
    from personal_ai.context.shopping import configured_shopping_context_contribution
    from personal_ai.context.travel import configured_travel_context_contribution

    source_runtime = compose_context_runtime(
        configured_travel_context_contribution(settings),
        configured_shopping_context_contribution(settings),
        configured_finance_context_contribution(settings),
        configured_health_context_contribution(settings),
    )

    from personal_ai.federation.deployment import configured_federation_contribution

    federation = configured_federation_contribution(settings, source_runtime)
    return compose_context_runtime(
        ContextRuntimeContribution(
            source_runtime.provider_factories, source_runtime.planning_rules,
            source_runtime.permission_revalidators,
            source_runtime.export_adapters,
        ),
        federation,
    )
