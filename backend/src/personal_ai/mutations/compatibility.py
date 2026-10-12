"""Deployment guard for operation contracts referenced by retained proposals."""


class MutationRuntimeCompatibilityError(RuntimeError):
    """The runtime cannot inspect/reconcile one or more retained proposals."""


def require_reconciliation_compatibility(repository, runtime) -> None:
    """Fail startup if removing an adapter would strand a stored proposal or receipt."""
    required = repository.required_operation_contracts()
    retained = runtime.mutation_reconciliation_adapters
    missing = [
        (application_id, operation_id, version, fingerprint)
        for application_id, operation_id, version, fingerprint in required
        if not fingerprint
        or (application_id, operation_id, version, fingerprint) not in retained
    ]
    if missing:
        raise MutationRuntimeCompatibilityError(
            "mutation_reconciliation_contract_missing:" + ",".join(
                f"{app}/{operation}@{version}/{fingerprint or 'legacy'}"
                for app, operation, version, fingerprint in missing
            )
        )
