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
                       for name in (
                           "authorize", "validate", "candidate_from_output", "execute", "reconcile"
                       ))
        ):
            raise ValueError("mutation_adapter_contract_invalid")
    return registered


def validate_reconciliation_adapters(adapters):
    """Validate retained historical adapters, even when current app policy retires them."""
    registered = dict(adapters)
    for key, adapter in registered.items():
        declaration = getattr(adapter, "declaration", None)
        if (
            not isinstance(key, tuple)
            or len(key) != 4
            or not isinstance(key[0], str)
            or not key[0]
            or not isinstance(declaration, MutationOperationDeclaration)
            or key[:3] != (key[0], declaration.operation_id, declaration.version)
            or key[3] != declaration.contract_fingerprint
            or not callable(getattr(adapter, "reconcile", None))
            or not callable(getattr(adapter, "authorize", None))
        ):
            raise ValueError("mutation_reconciliation_adapter_contract_invalid")
    return registered


def operation_adapter(
    registry,
    runtime,
    scope,
    operation,
    *,
    contract_fingerprint,
    require_policy=True,
):
    from personal_ai.mutations.contracts import MutationError

    key = (scope.application_id, operation.operation_id, operation.version)
    if not require_policy:
        # Recovery uses an immutable retained resolver, not mutable new-write policy
        # or a declaration that may have been retired after a possible effect.
        adapter = runtime.mutation_reconciliation_adapters.get(
            (*key, contract_fingerprint)
        )
        if adapter is None:
            raise MutationError("mutation_reconciliation_implementation_unavailable")
        return adapter

    definition = registry.get(scope.application_id)
    declaration = next(
        (
            item
            for item in definition.mutation_operations
            if item.operation_id == operation.operation_id
            and item.version == operation.version
        ),
        None,
    )
    if declaration is None:
        raise MutationError("mutation_operation_unsupported")
    if operation not in definition.context_policy.sidecar.mutation_operations:
        raise MutationError("mutation_operation_denied")
    if declaration.contract_fingerprint != contract_fingerprint:
        raise MutationError("mutation_contract_changed")
    adapter = runtime.mutation_adapters.get(key)
    if adapter is None or adapter.declaration != declaration:
        raise MutationError("mutation_implementation_unavailable")
    return adapter
