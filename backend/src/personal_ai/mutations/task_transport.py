"""Canonical destination requests over the existing mutation control aggregate."""

from personal_ai.contracts.delegated_tasks import DelegatedTaskRequest
from personal_ai.mutations.contracts import MutationError, UserCommandProvenance


def task_for_proposal(proposal, action: str) -> DelegatedTaskRequest:
    """Project exact immutable intent, confirmed binding and current dependencies.

    No credentials are retained. Reconciliation keeps the original operation key,
    payload and expiry even when obtaining a fresh short-lived identity assertion.
    """
    intent = proposal.intent
    if not isinstance(intent.producer, UserCommandProvenance):
        raise MutationError("mutation_task_command_provenance_required")
    dependencies = [dep for source in intent.sources for dep in source.permission_dependencies]
    if proposal.validation:
        dependencies.extend(proposal.validation.permission_dependencies)
    canonical = {}
    purposes = set()
    for dependency in dependencies:
        canonical[dependency.model_dump_json()] = dependency.model_dump(mode="json")
        if dependency.permission_id.startswith("federation_grant:"):
            purposes.add(dependency.purpose)
    if len(purposes) != 1 or None in purposes:
        raise MutationError("mutation_task_grant_required")
    expires = intent.expires_at
    if proposal.validation:
        expires = min(expires, proposal.validation.expires_at)
    return DelegatedTaskRequest(
        source_application_id=intent.producer.source_application_id,
        destination_application_id=intent.target.application_id,
        workspace_id=intent.target.workspace_id,
        purpose=next(iter(purposes)), action=action,
        proposal_id=proposal.proposal_id, execution_key=proposal.domain_operation_key,
        operation_id=intent.operation.operation_id, operation_version=intent.operation.version,
        operation_contract_fingerprint=intent.operation_contract_fingerprint,
        payload_schema_id=intent.payload_schema_id, target_entity_type=intent.target.entity_type,
        target_entity_id=intent.target.entity_id, expected_domain_version=intent.expected_domain_version,
        payload=intent.payload, intent_digest=proposal.intent_digest(),
        confirmation_binding=proposal.confirmation.binding if proposal.confirmation else None,
        source_dependencies=tuple(canonical[key] for key in sorted(canonical)), expires_at=expires,
    )
