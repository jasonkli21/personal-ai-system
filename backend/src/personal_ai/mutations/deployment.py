"""Explicit default-off task composition; installed metadata never grants access."""

from datetime import UTC, datetime

from personal_ai.context.runtime import ContextRuntimeContribution
from personal_ai.mutations.commands import SourceCommandResolver
from personal_ai.mutations.contracts import MutationOperationDeclaration, OperationRef
from personal_ai.mutations.http import SignedDomainClient
from personal_ai.mutations.shopping import BudgetAllocation, SharedContextNote, ShoppingTaskAdapter


def domain_client(settings, endpoint, audience=None):
    return SignedDomainClient(
        base_url=endpoint,
        audience=audience or endpoint,
        service_account=settings.task_domain_service_account,
        issuer=settings.task_delegation_issuer,
        key_id=settings.task_delegation_key_id,
        private_key=settings.task_delegation_private_key,
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
            for old_fingerprint in settings.task_shopping_retained_operation_fingerprints.get(
                operation_id, ()
            ):
                retained[(*key, old_fingerprint)] = ShoppingTaskAdapter(
                    client,
                    declaration.model_copy(update={"contract_fingerprint": old_fingerprint}),
                    payload_model,
                    clock=lambda: datetime.now(UTC),
                )
            if settings.task_shopping_enabled:
                current[key] = adapter
    return ContextRuntimeContribution(
        {}, mutation_adapters=current, mutation_reconciliation_adapters=retained
    )


def configured_command_resolver(settings, runtime):
    if not settings.task_delegation_enabled or not settings.task_source_endpoints:
        return None
    clients = {
        app: domain_client(settings, endpoint)
        for app, endpoint in settings.task_source_endpoints.items()
    }
    return SourceCommandResolver(clients, runtime, clock=lambda: datetime.now(UTC))


def install_task_metadata(registry, settings, runtime):
    """Opt in to pinned domain operations; never infer policy from an arbitrary adapter."""
    if not settings.task_shopping_enabled:
        return registry
    from personal_ai.applications.registry import ApplicationRegistry

    declarations = tuple(
        adapter.declaration
        for key, adapter in sorted(runtime.mutation_adapters.items())
        if key[0] == "shopping"
    )
    definitions = [registry.get(app) for app in sorted(registry.application_ids)]
    shopping = registry.get("shopping")
    existing = {(item.operation_id, item.version): item for item in shopping.mutation_operations}
    for item in declarations:
        old = existing.get((item.operation_id, item.version))
        if old is not None and old != item:
            raise ValueError("task_operation_declaration_conflict")
    additions = tuple(
        item for item in declarations if (item.operation_id, item.version) not in existing
    )
    if not additions:
        return registry
    policy = shopping.context_policy
    version = (
        policy.version if policy.version.endswith(":tasks-v1") else policy.version + ":tasks-v1"
    )
    updated = shopping.model_copy(
        update={
            "mutation_operations": (*shopping.mutation_operations, *additions),
            "context_policy": policy.model_copy(
                update={
                    "version": version,
                    "sidecar": policy.sidecar.model_copy(
                        update={
                            "mutation_operations": (
                                *policy.sidecar.mutation_operations,
                                *(
                                    OperationRef(
                                        operation_id=item.operation_id, version=item.version
                                    )
                                    for item in additions
                                ),
                            ),
                        }
                    ),
                }
            ),
        }
    )
    definitions = [updated if item.application_id == "shopping" else item for item in definitions]
    return ApplicationRegistry(
        definitions,
        registry.capabilities,
        comparison_modules=registry.comparison_modules,
        workspace_authorizers=registry.workspace_authorizers,
    )
