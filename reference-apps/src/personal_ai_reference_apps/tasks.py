"""Pinned Shopping adapters, including observation-only retained contracts."""

from datetime import UTC, datetime

from personal_ai.context.runtime import ContextRuntimeContribution
from personal_ai.mutations.contracts import MutationOperationDeclaration
from personal_ai.mutations.deployment import domain_client

from personal_ai_reference_apps.mutations.shopping import (
    BudgetAllocation,
    SharedContextNote,
    ShoppingTaskAdapter,
)


def configured_task_contribution(settings):
    current, retained = {}, {}
    if (
        settings.task_delegation_enabled
        and settings.task_shopping_base_url
        and settings.task_shopping_operation_fingerprint
    ):
        client = domain_client(
            settings, settings.task_shopping_base_url, settings.task_shopping_audience
        )
        operations = (
            (
                "project.set_budget",
                "shopping-budget-allocation-v1",
                settings.task_shopping_operation_fingerprint,
                BudgetAllocation,
            ),
            (
                "project.append_context_note",
                "shopping-context-note-v1",
                settings.task_shopping_note_operation_fingerprint,
                SharedContextNote,
            ),
        )
        for operation_id, schema_id, fingerprint, payload_model in operations:
            if not fingerprint:
                continue
            declaration = MutationOperationDeclaration(
                operation_id=operation_id,
                version=1,
                payload_schema_id=schema_id,
                entity_types=("project",),
                sensitivity="restricted",
                contract_fingerprint=fingerprint,
            )
            adapter = ShoppingTaskAdapter(
                client, declaration, payload_model, clock=lambda: datetime.now(UTC)
            )
            key = ("shopping", operation_id, 1)
            retained[(*key, fingerprint)] = adapter
            for (
                old_fingerprint
            ) in settings.task_shopping_retained_operation_fingerprints.get(
                operation_id, ()
            ):
                retained[(*key, old_fingerprint)] = ShoppingTaskAdapter(
                    client,
                    declaration.model_copy(
                        update={"contract_fingerprint": old_fingerprint}
                    ),
                    payload_model,
                    clock=lambda: datetime.now(UTC),
                )
            if settings.task_shopping_enabled:
                current[key] = adapter
    return ContextRuntimeContribution(
        {}, mutation_adapters=current, mutation_reconciliation_adapters=retained
    )
