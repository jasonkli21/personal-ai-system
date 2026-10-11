"""Deployment assembly for independently registered context contributions."""

from personal_ai.context.runtime import ContextRuntimeRegistry, compose_context_runtime


def configured_context_runtime(settings) -> ContextRuntimeRegistry:
    """Compose installed deployment contributions through the generic seam."""
    from personal_ai.context.finance import configured_finance_context_contribution
    from personal_ai.context.shopping import configured_shopping_context_contribution
    from personal_ai.context.travel import configured_travel_context_contribution

    return compose_context_runtime(
        configured_travel_context_contribution(settings),
        configured_shopping_context_contribution(settings),
        configured_finance_context_contribution(settings),
    )
