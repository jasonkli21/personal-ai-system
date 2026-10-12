"""Shared durable state machine, enforced by repositories as well as controller."""

from uuid import uuid5

from personal_ai.mutations.contracts import MutationProposal, proposal_identity
from personal_ai.storage.errors import PersistenceConflict

TRANSITIONS = {
    "proposed": {"validated", "rejected", "expired"},
    "validated": {"confirmed", "rejected", "expired"},
    "confirmed": {"executing", "rejected", "expired"},
    "executing": {"applied", "rejected", "uncertain"},
    "uncertain": {"reconciling"},
    "reconciling": {"applied", "rejected", "uncertain"},
    "applied": set(), "rejected": set(), "expired": set(),
}


def validate_transition(current, candidate, expected_revision):
    candidate = MutationProposal.model_validate(candidate.model_dump())
    target = candidate.intent.target
    expected_id = proposal_identity(candidate.owner_id, candidate.acting_user_id,
                                    target.application_id, target.workspace_id,
                                    candidate.intent.idempotency_key)
    if (candidate.proposal_id != expected_id
        or candidate.domain_operation_key != uuid5(expected_id, "authoritative-domain-operation-v1")):
        raise PersistenceConflict("mutation_identity_invalid")
    if current is None:
        if expected_revision != 0 or candidate.revision != 1 or candidate.state != "proposed":
            raise PersistenceConflict("mutation_create_conflict")
        if any((candidate.validation, candidate.confirmation, candidate.execution_attempt_id,
                candidate.reconciliation_id, candidate.lease_until, candidate.outcome,
                candidate.terminal_code)):
            raise PersistenceConflict("mutation_create_state_invalid")
        return
    if (
        current.revision != expected_revision or candidate.revision != current.revision + 1
        or candidate.state not in TRANSITIONS[current.state]
        or candidate.updated_at < current.updated_at
        or any(getattr(current, name) != getattr(candidate, name) for name in (
            "proposal_id", "owner_id", "acting_user_id", "intent", "created_at",
            "domain_operation_key", "sensitivity",
        ))
    ):
        raise PersistenceConflict("mutation_revision_conflict")
    if current.validation is None and candidate.validation is not None and not (
        current.state == "proposed" and candidate.state in {"validated", "rejected"}
    ):
        raise PersistenceConflict("mutation_validation_transition_invalid")
    if current.confirmation is None and candidate.confirmation is not None and not (
        current.state == "validated" and candidate.state == "confirmed"
    ):
        raise PersistenceConflict("mutation_confirmation_transition_invalid")
    if current.execution_attempt_id is None and candidate.execution_attempt_id is not None and not (
        current.state == "confirmed" and candidate.state == "executing"
    ):
        raise PersistenceConflict("mutation_attempt_transition_invalid")
    if candidate.reconciliation_id != current.reconciliation_id and not (
        current.state == "uncertain" and candidate.state == "reconciling"
    ):
        raise PersistenceConflict("mutation_reconciliation_transition_invalid")
    if candidate.outcome != current.outcome and not (
        current.state in {"executing", "reconciling"}
        or (current.state == "uncertain" and candidate.state == "reconciling" and candidate.outcome is None)
    ):
        raise PersistenceConflict("mutation_outcome_transition_invalid")
    if candidate.state in {"confirmed", "executing"} and (
        candidate.validation is None
        or candidate.updated_at >= candidate.intent.expires_at
        or candidate.updated_at >= candidate.validation.expires_at
    ):
        raise PersistenceConflict("mutation_expired")
    if candidate.state in {"rejected", "expired"} and not candidate.terminal_code:
        raise PersistenceConflict("mutation_terminal_reason_required")
    if current.validation is not None and candidate.validation != current.validation:
        raise PersistenceConflict("mutation_validation_immutable")
    if current.confirmation is not None and candidate.confirmation != current.confirmation:
        raise PersistenceConflict("mutation_confirmation_immutable")
    if current.execution_attempt_id and candidate.execution_attempt_id != current.execution_attempt_id:
        raise PersistenceConflict("mutation_attempt_immutable")
    if candidate.state in {"validated", "confirmed", "executing", "reconciling", "uncertain",
                           "applied"} and (not candidate.validation or not candidate.validation.valid):
        raise PersistenceConflict("mutation_validation_required")
    if candidate.validation and (
        candidate.validation.intent_digest != candidate.intent_digest()
        or candidate.validation.expected_domain_version != candidate.intent.expected_domain_version
        or candidate.validation.expires_at > candidate.intent.expires_at
    ):
        raise PersistenceConflict("mutation_validation_binding_invalid")
    if candidate.state in {"confirmed", "executing", "reconciling", "uncertain", "applied"} and (
        not candidate.confirmation or candidate.confirmation.binding != candidate.binding()
        or candidate.confirmation.acting_user_id != candidate.acting_user_id
        or candidate.confirmation.confirmed_at >= candidate.validation.expires_at
        or candidate.confirmation.confirmed_at > candidate.updated_at
    ):
        raise PersistenceConflict("mutation_confirmation_required")
    if candidate.state in {"executing", "reconciling", "uncertain", "applied"} and (
        candidate.execution_attempt_id is None
    ):
        raise PersistenceConflict("mutation_attempt_required")
    if candidate.state in {"executing", "reconciling"} and (
        candidate.lease_until is None or candidate.lease_until <= candidate.updated_at
    ):
        raise PersistenceConflict("mutation_lease_required")
    if candidate.state == "reconciling" and candidate.reconciliation_id is None:
        raise PersistenceConflict("mutation_reconciliation_required")
    if candidate.outcome and (
        candidate.outcome.state != candidate.state
        or candidate.outcome.domain_operation_key != candidate.domain_operation_key
        or (candidate.outcome.post_state
            and candidate.outcome.post_state.target != candidate.intent.target)
    ):
        raise PersistenceConflict("mutation_outcome_binding_invalid")
    if candidate.state == "applied" and candidate.outcome is None:
        raise PersistenceConflict("mutation_authoritative_outcome_required")
