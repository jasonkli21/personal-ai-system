"""Explicit default-off task composition; installed metadata never grants access."""

from datetime import UTC, datetime

from personal_ai.mutations.commands import SourceCommandResolver
from personal_ai.mutations.contracts import OperationRef
from personal_ai.mutations.http import SignedDomainClient


def domain_client(settings, endpoint, audience=None):
    return SignedDomainClient(
        base_url=endpoint,
        audience=audience or endpoint,
        service_account=settings.task_domain_service_account,
        issuer=settings.task_delegation_issuer,
        key_id=settings.task_delegation_key_id,
        private_key=settings.task_delegation_private_key,
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
    """Install validated current adapters only into registered destination manifests."""
    del settings
    from personal_ai.applications.registry import ApplicationRegistry

    definitions = []
    changed = False
    destinations = {key[0] for key in runtime.mutation_adapters}
    if destinations - registry.application_ids:
        raise ValueError("task_destination_application_unknown")
    for application_id in sorted(registry.application_ids):
        definition = registry.get(application_id)
        existing = {
            (item.operation_id, item.version): item for item in definition.mutation_operations
        }
        additions = []
        for key, adapter in sorted(runtime.mutation_adapters.items()):
            if key[0] != application_id:
                continue
            item = adapter.declaration
            old = existing.get((item.operation_id, item.version))
            if old is not None and old != item:
                raise ValueError("task_operation_declaration_conflict")
            if old is None:
                additions.append(item)
        if additions:
            changed = True
            policy = definition.context_policy
            version = (
                policy.version
                if policy.version.endswith(":tasks-v1")
                else policy.version + ":tasks-v1"
            )
            definition = definition.model_copy(
                update={
                    "mutation_operations": (*definition.mutation_operations, *additions),
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
        definitions.append(definition)
    if not changed:
        return registry
    return ApplicationRegistry(
        definitions,
        registry.capabilities,
        comparison_modules=registry.comparison_modules,
        workspace_authorizers=registry.workspace_authorizers,
    )
