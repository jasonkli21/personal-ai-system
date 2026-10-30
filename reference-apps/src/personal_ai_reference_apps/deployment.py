"""Reference runtime factories; installation alone never selects these."""

from personal_ai.context.runtime import ContextRuntimeContribution

from personal_ai_reference_apps.federation import INITIAL_FEDERATION_CASES


def _with_cases(contribution, destination):
    return ContextRuntimeContribution(
        contribution.provider_factories,
        contribution.planning_rules,
        contribution.permission_revalidators,
        contribution.export_adapters,
        tuple(
            case
            for case in INITIAL_FEDERATION_CASES
            if case.destination_application_id == destination
        ),
        contribution.mutation_adapters,
        contribution.mutation_reconciliation_adapters,
    )


def travel_context(settings):
    from personal_ai_reference_apps.context.travel import (
        configured_travel_context_contribution,
    )

    return _with_cases(configured_travel_context_contribution(settings), "travel")


def shopping_context(settings):
    from personal_ai.context.runtime import compose_context_runtime

    from personal_ai_reference_apps.context.shopping import (
        configured_shopping_context_contribution,
    )
    from personal_ai_reference_apps.tasks import configured_task_contribution

    runtime = compose_context_runtime(
        configured_shopping_context_contribution(settings),
        configured_task_contribution(settings),
    )
    return _with_cases(
        ContextRuntimeContribution(
            runtime.provider_factories,
            runtime.planning_rules,
            runtime.permission_revalidators,
            runtime.export_adapters,
            (),
            runtime.mutation_adapters,
            runtime.mutation_reconciliation_adapters,
        ),
        "shopping",
    )


def finance_context(settings):
    from personal_ai_reference_apps.context.finance import (
        configured_finance_context_contribution,
    )

    return configured_finance_context_contribution(settings)


def health_context(settings):
    from personal_ai_reference_apps.context.health import (
        configured_health_context_contribution,
    )

    return configured_health_context_contribution(settings)


def reference_context_catalog():
    """Explicit source-tree equivalent of selecting all installed reference entries."""
    from personal_ai.context.runtime import ContextRuntimeContributionCatalog

    return ContextRuntimeContributionCatalog(
        (
            ("travel", travel_context),
            ("shopping", shopping_context),
            ("finance", finance_context),
            ("health", health_context),
        )
    )
