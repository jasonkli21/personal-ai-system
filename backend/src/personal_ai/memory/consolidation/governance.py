"""Authenticated, read-only bridge to canonical memory control decisions."""

from datetime import timedelta
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from personal_ai.auth.scope import current_request_scope, current_verified_principal
from personal_ai.memory.consolidation.contracts import DerivedProposal, EvidenceEdge
from personal_ai.memory.control_contracts import (
    ControlIntent,
    OperationResult,
    PendingProposal,
    ProposalInput,
    ReviewInput,
)
from personal_ai.memory.control_repository import decide
from personal_ai.memory.knowledge import Strict


class GovernancePreview(Strict):
    status: Literal["preview_only", "denied"]
    candidate_digest: str | None = None
    candidate: DerivedProposal | None = None
    canonical_mapping: Literal["procedure_content", "typed_review_only"] | None = None
    edges: tuple[EvidenceEdge, ...] = ()
    pending: PendingProposal | None = None
    review: OperationResult | None = None


class ProposalReviewPreview:
    """No storage mutation or acceptance method; no API/tool registration.

    The supplied canonical control service owns identity, current project grants
    and source leases. Offline evidence is revalidated under its synthetic guard.
    Review reuses the canonical pure decision, which never admits knowledge.
    """

    def __init__(self, repository):
        self.repository = repository

    def preview(self, scope, candidate, controls, *, review=None):
        try:
            with self.repository.source.guard(), controls.authority() as project:
                request = current_request_scope()
                principal = current_verified_principal()
                if (
                    request is None
                    or request != controls.scope
                    or (
                        request.owner_id,
                        request.application_id,
                        request.workspace_id,
                        request.acting_user_id,
                    )
                    != (scope.owner, scope.application, scope.workspace, scope.actor)
                    or controls.project_id != scope.project
                    or not controls.enabled("user_management")
                    or not controls.user_authorized()
                    or principal is None
                    or not principal.audience
                    or principal.authorized_party != scope.client
                    or not self.repository.validate_cached(scope, candidate)
                    or project.project_id != scope.project
                    or project.revision != candidate.fact.revision
                ):
                    return GovernancePreview(status="denied")
                now = controls.clock()
                if candidate.kind == "procedure":
                    content = ProposalInput(
                        kind="procedure",
                        title="Synthetic historical check",
                        claim=f"Synthetic check: {candidate.fact.command} passed at {candidate.fact.revision}.",
                        limitations=("Synthetic fixture only; review does not admit memory.",),
                    )
                    intent = ControlIntent(
                        operation_id=uuid5(
                            NAMESPACE_URL, "offline-proposal-preview:" + candidate.key
                        ),
                        action="propose",
                        proposal=content,
                        actor="agent_proposal",
                    )
                    _, pending, _, _ = decide(request, project, intent, now)
                    mapping = "procedure_content"
                else:
                    # The typed candidate remains outside the controls' two-kind
                    # content schema. A bodyless, never-persisted canonical
                    # ticket can still exercise its review CAS/expiry contract.
                    # It is not a proposal submission or a queueable payload.
                    pending = PendingProposal(
                        id=uuid5(NAMESPACE_URL, "offline-review-preview:" + candidate.key),
                        project=project,
                        content=None,
                        created_at=now,
                        expires_at=now + timedelta(hours=24),
                    )
                    mapping = "typed_review_only"
                sources = [self.repository.source.resolve(scope, e) for e in candidate.edges]
                if not all(sources):
                    return GovernancePreview(status="denied")
                pending = pending.model_copy(
                    update={
                        "expires_at": min(
                            pending.expires_at,
                            *(
                                min(s.expires_at, s.observed_at + timedelta(hours=24))
                                for s in sources
                            ),
                        )
                    }
                )
                result = None
                if review is not None:
                    if (
                        type(review) is not ReviewInput
                        or set(review.__dict__) != set(ReviewInput.model_fields)
                        or review.__pydantic_extra__
                    ):
                        return GovernancePreview(status="denied")
                    body = ReviewInput.model_validate(review.model_dump(warnings=False))
                    user_intent = ControlIntent(
                        operation_id=body.operation_id,
                        action=body.decision,
                        target_id=pending.id,
                        expected_version=body.expected_version,
                        actor="verified_user",
                    )
                    result, _, _, _ = decide(request, project, user_intent, now, pending=pending)
                # The canonical authority and source lock remain held at release.
                if not controls.user_authorized() or not self.repository.validate_cached(
                    scope, candidate
                ):
                    return GovernancePreview(status="denied")
                return GovernancePreview(
                    status="preview_only",
                    candidate_digest=candidate.key,
                    candidate=candidate,
                    canonical_mapping=mapping,
                    edges=candidate.edges,
                    pending=pending,
                    review=result,
                )
        except Exception:  # noqa: BLE001 - no external exception/payload escapes this dry run
            return GovernancePreview(status="denied")
