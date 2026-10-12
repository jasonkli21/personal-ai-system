"""Implementation registration separate from declaration and eligibility."""

from pydantic import BaseModel

from personal_ai.mutations.contracts import MutationOperationDeclaration


def validate_adapters(adapters):
    registered = dict(adapters)
    for key, adapter in registered.items():
        declaration = getattr(adapter, "declaration", None)
        payload_model = getattr(adapter, "payload_model", None)
        if (
            not isinstance(key, tuple) or len(key) != 3
            or not isinstance(key[0], str) or not key[0]
            or not isinstance(declaration, MutationOperationDeclaration)
            or key[1:] != (declaration.operation_id, declaration.version)
            or not isinstance(payload_model, type) or not issubclass(payload_model, BaseModel)
            or payload_model.model_config.get("extra") != "forbid"
            or not all(callable(getattr(adapter, name, None))
                       for name in ("authorize", "validate", "execute", "reconcile"))
        ):
            raise ValueError("mutation_adapter_contract_invalid")
    return registered


def operation_adapter(registry, runtime, scope, operation, *, require_policy=True):
    from personal_ai.mutations.contracts import MutationError

    definition = registry.get(scope.application_id)
    declaration = next((item for item in definition.mutation_operations
                        if item.operation_id == operation.operation_id
                        and item.version == operation.version), None)
    if declaration is None:
        raise MutationError("mutation_operation_unsupported")
    if require_policy and operation not in definition.context_policy.sidecar.mutation_operations:
        raise MutationError("mutation_operation_denied")
    adapter = runtime.mutation_adapters.get(
        (scope.application_id, operation.operation_id, operation.version)
    )
    if adapter is None or adapter.declaration != declaration:
        raise MutationError("mutation_implementation_unavailable")
    return adapter
