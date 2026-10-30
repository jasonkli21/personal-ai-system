"""Explicit all-reference profile; standard deployment uses entry-point selection."""

from personal_ai.applications.registry import ApplicationContributionCatalog
from personal_ai.main import create_app

from personal_ai_reference_apps.applications import application_contribution
from personal_ai_reference_apps.deployment import reference_context_catalog


def create_reference_app():
    return create_app(
        application_catalog=ApplicationContributionCatalog(
            (name, lambda name=name: application_contribution(name))
            for name in ("travel", "shopping", "finance", "health")
        ),
        context_runtime_catalog=reference_context_catalog(),
        selected_contributions=(),
    )


app = create_reference_app()
