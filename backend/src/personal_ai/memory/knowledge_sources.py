"""Narrow trusted source interfaces. No production workflow issuer is installed."""

from contextlib import contextmanager
from typing import Protocol
from uuid import UUID

from personal_ai.auth.scope import current_verified_principal, scope_matches
from personal_ai.context.contracts import complete_turns, fingerprint
from personal_ai.context.history import memory_extraction_context_reason
from personal_ai.memory.knowledge import KnowledgeEvidence, Strict
from personal_ai.memory.services import source_turn_reuse_reason


class KnowledgeSourceError(ValueError):
    """Safe source resolution reason, without external payloads."""


class KnowledgeResolver(Protocol):
    """Host-owned authority, not a model tool.

    lease must fence source, project, permission, branch, and confirmation
    mutations until the enclosed effect has settled. Distributed hosts must
    supply a recoverable lease; a check followed by an unguarded write is invalid.
    """

    def project(self, scope, project_id): ...
    def authorize_memory(self, scope) -> bool: ...
    def resolve(self, reference, scope) -> KnowledgeEvidence: ...
    def lease(self, scope, project_id): ...


class UnsupportedKnowledgeResolver:
    def authorize_memory(self, scope):
        return False

    def project(self, scope, project_id):
        raise KnowledgeSourceError("unsupported_source")

    def resolve(self, reference, scope):
        raise KnowledgeSourceError("unsupported_source")

    @contextmanager
    def lease(self, scope, project_id):
        raise KnowledgeSourceError("unsupported_source")
        yield  # pragma: no cover - contextmanager contract


class DecisionConfirmation(Strict):
    evidence: KnowledgeEvidence
    confirmed: bool
    conversation_id: UUID
    turn_id: UUID
    user_message_id: UUID
    user_fingerprint: str


class AuthenticatedCompletedTurnDecisionResolver:
    """Verify one exact authenticated confirmation registered by a trusted host.

    authority resolves a server-side confirmation reference (not candidate data)
    and supplies the recoverable source lease. No permissive default authority,
    authentication fallback, API route, or automatic chat extraction is provided.
    """

    def __init__(self, authority, messages, *, permission_revalidator=None):
        self.authority, self.messages = authority, messages
        self.permission_revalidator = permission_revalidator

    def project(self, scope, project_id):
        return self.authority.project(scope, project_id)

    def authorize_memory(self, scope):
        return self.authority.authorize_memory(scope)

    def lease(self, scope, project_id):
        return self.authority.lease(scope, project_id)

    def resolve(self, reference, scope):
        principal = current_verified_principal()
        if principal is None or not principal.authenticated or principal.owner_id != scope.owner_id:
            raise KnowledgeSourceError("authentication_required")
        confirmation = DecisionConfirmation.model_validate(
            self.authority.confirmation(reference, scope)
        )
        evidence = KnowledgeEvidence.model_validate(confirmation.evidence)
        if (
            not confirmation.confirmed
            or evidence.proposal.kind != "project_decision"
            or evidence.source_authority != "user_asserted"
            or evidence.verification_status != "user_confirmed"
            or not scope_matches(evidence.scope, scope)
            or evidence.scope.owner_id != scope.owner_id
            or evidence.scope.acting_user_id != scope.acting_user_id
        ):
            raise KnowledgeSourceError("decision_unconfirmed")
        active = self.messages.list_active(
            owner_id=scope.owner_id,
            conversation_id=confirmation.conversation_id,
        )
        turn = next(
            (pair for pair in complete_turns(active) if pair[1].id == confirmation.turn_id), None
        )
        if (
            turn is None
            or turn[0].id != confirmation.user_message_id
            or turn[0].content != evidence.proposal.claim
            or any(not scope_matches(m, scope) or m.owner_id != scope.owner_id for m in turn)
            or memory_extraction_context_reason(turn[1]) is not None
            or getattr(turn[1].attribution, "execution_origin", None) == "manual_import"
            or confirmation.user_fingerprint != fingerprint([turn[0]])
            or evidence.observed_at != turn[0].created_at
            or evidence.verified_at < turn[1].created_at
            or evidence.task_id != str(confirmation.conversation_id)
            or evidence.run_id != str(confirmation.turn_id)
            or evidence.attempt_id != str(confirmation.turn_id)
            or tuple((edge.source_id, edge.fingerprint) for edge in evidence.edges)
            != (
                (str(turn[0].id), fingerprint([turn[0]])),
                (str(turn[1].id), fingerprint([turn[1]])),
            )
        ):
            raise KnowledgeSourceError("decision_source_invalid")
        # Reuse shared history expiry/permission checks without treating the
        # exact project decision as a v1 personal-preference candidate.
        from types import SimpleNamespace

        proxy = SimpleNamespace(
            owner_id=scope.owner_id,
            source_conversation_id=confirmation.conversation_id,
            source_turn_id=confirmation.turn_id,
        )
        reason = source_turn_reuse_reason(
            proxy,
            self.messages,
            None,
            permission_revalidator=self.permission_revalidator,
        )
        if reason:
            raise KnowledgeSourceError(reason)
        return evidence
