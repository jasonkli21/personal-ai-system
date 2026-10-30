"""Scoped MEM-2 control service; missing host authority always fails closed."""

from contextlib import contextmanager
from datetime import UTC, datetime
from time import monotonic
from uuid import uuid4

from personal_ai.auth.scope import current_verified_principal
from personal_ai.memory.control_contracts import (
    ControlIntent,
    MemoryView,
    OperationResult,
    ReadResult,
)
from personal_ai.memory.knowledge import KnowledgeFilter
from personal_ai.memory.knowledge_service import permitted_content, same_actor
from personal_ai.storage.errors import ResourceNotFoundError


class MemoryControlService:
    def __init__(self, knowledge, repository, scope, project_id, *, clock=None):
        self.knowledge, self.repository = knowledge, repository
        self.settings, self.scope, self.project_id = knowledge.settings, scope, project_id
        self.clock = clock or (lambda: datetime.now(UTC))

    def enabled(self, channel):
        return (
            self.settings.memory_enabled
            and self.settings.memory_knowledge_selection_enabled
            and getattr(self.settings, "memory_" + channel + "_enabled")
        )

    def user_authorized(self):
        p = current_verified_principal()
        now = self.clock().timestamp()
        return (
            p is not None
            and p.authenticated
            and p.owner_id == self.scope.owner_id
            and self.scope.acting_user_id == f"{p.issuer}|{p.subject}"
            and type(p.authenticated_at) is int
            and now - self.settings.auth_recent_token_seconds <= p.authenticated_at <= now + 60
        )

    @contextmanager
    def authority(self):
        if not self.knowledge._authorized(self.scope):
            raise PermissionError("authority_unavailable")
        with self.knowledge.resolver.lease(self.scope, self.project_id):
            if not self.knowledge._authorized(self.scope):
                raise PermissionError("authority_unavailable")
            project = self.knowledge.resolver.project(self.scope, self.project_id)
            yield project

    def _view(self, record):
        if not same_actor(record, self.scope) or self.knowledge.reason(record, self.scope):
            return None
        state = self.knowledge.lifecycle.get_state(
            owner_id=self.scope.owner_id, memory_id=record.id
        )
        return MemoryView(
            application_id=record.application_id,
            workspace_id=record.workspace_id,
            id=record.id,
            kind=record.proposal.kind,
            title=record.proposal.title,
            historical_content=record.content,
            project=record.project,
            authority=record.evidence.source_authority,
            verification=record.evidence.verification_status,
            observed_at=record.evidence.observed_at,
            expires_at=record.evidence.expires_at,
            permission_dependencies=(self.knowledge.dependency(record, self.scope),),
            state_version=state.state_version,
            validity_epoch=state.validity_epoch,
            source_ids=tuple(edge.source_id for edge in record.evidence.edges),
        )

    def read(self, query, *, memory_id=None, topics=False, channel="user_management"):
        if not self.enabled(channel):
            return ReadResult(status="disabled")
        deadline = monotonic() + 2
        try:
            with (
                self.authority() as project,
                self.knowledge.repository.knowledge_consumption_guard(self.scope),
            ):
                if memory_id:
                    rows = (
                        self.knowledge.repository.get_knowledge(
                            owner_id=self.scope.owner_id, memory_id=memory_id, timeout=2
                        ),
                    )
                else:
                    rows = self.knowledge.repository.list_knowledge(
                        scope=self.scope,
                        filters=KnowledgeFilter(project=project),
                        limit=33,
                        timeout=2,
                    )
                candidates_truncated = len(rows) > 32
                rows = rows[:32]
                eligible = []
                terms = query.query.casefold().split()
                for row in rows:
                    if monotonic() >= deadline:
                        raise TimeoutError
                    if row.project != project or (query.kind and row.proposal.kind != query.kind):
                        continue
                    view = self._view(row)
                    if view and all(
                        term in (row.proposal.title + " " + row.proposal.claim).casefold()
                        for term in terms
                    ):
                        eligible.append((row, view))
                # Revalidate everything at release under the same source and namespace leases.
                selected = eligible[: query.limit]
                if (
                    any(self.knowledge.reason(row, self.scope) for row, _ in selected)
                    or monotonic() >= deadline
                ):
                    raise PermissionError
                items = tuple(view for _, view in selected)
                if topics:
                    return ReadResult(
                        status="found",
                        topics=tuple(sorted({v.kind for v in items})),
                        truncated=candidates_truncated or len(eligible) > query.limit,
                    )
                return ReadResult(
                    status="found" if not memory_id or items else "forbidden_or_not_found",
                    items=items,
                    truncated=candidates_truncated or len(eligible) > query.limit,
                )
        except ResourceNotFoundError:
            return ReadResult(status="forbidden_or_not_found")
        except Exception:  # noqa: BLE001 - no raw IDs, counts or exceptions from denied records
            return ReadResult(
                status="forbidden_or_not_found" if memory_id else "temporarily_unavailable"
            )

    def proposals(self):
        if not self.enabled("user_management"):
            return ReadResult(status="disabled")
        try:
            with self.authority() as project:
                rows = self.repository.list_pending(self.scope, project, self.clock())
                if not self.knowledge._authorized(self.scope):
                    raise PermissionError
                return ReadResult(status="found", proposals=rows)
        except Exception:  # noqa: BLE001 - unavailable scope must not leak pending content
            return ReadResult(status="temporarily_unavailable")

    def propose(self, candidate, *, operation_id=None):
        if not self.enabled("agent_tools"):
            return OperationResult(status="disabled", reason="feature_disabled")
        if (
            not permitted_content(candidate, self.settings)
            or any(len(s) > 200 for s in candidate.limitations)
            or any(
                term in (candidate.title + " " + candidate.claim).casefold()
                for term in ("receipt", "verified", "user confirmed", "<|", "role:", "javascript:")
            )
        ):
            return OperationResult(status="rejected", reason="content_policy")
        return self._execute(
            ControlIntent(
                operation_id=operation_id or uuid4(),
                action="propose",
                proposal=candidate,
                actor="agent_proposal",
            )
        )

    def mutate(self, action, target_id, request):
        if not self.enabled("user_mutations"):
            return OperationResult(status="disabled", reason="feature_disabled")
        if not self.user_authorized():
            return OperationResult(
                status="forbidden_or_not_found", reason="verified_recent_user_required"
            )
        if action == "revise":
            return OperationResult(
                status="unsupported_evidence_source", reason="no_registered_revision_issuer"
            )
        return self._execute(
            ControlIntent(
                operation_id=request.operation_id,
                action=action,
                target_id=target_id,
                expected_version=request.expected_version,
                actor="verified_user",
            )
        )

    def _execute(self, intent):
        attempted = False
        try:
            with self.authority() as project:
                # Replays reconcile without requiring an active (now forgotten) target.
                prior = self.repository.reconcile(self.scope, project, intent, self.clock())
                if prior:
                    return prior
                if intent.action == "forget":
                    record = self.knowledge.repository.get_knowledge(
                        owner_id=self.scope.owner_id, memory_id=intent.target_id
                    )
                    if (
                        not same_actor(record, self.scope)
                        or record.project.project_id != project.project_id
                    ):
                        return OperationResult(
                            status="forbidden_or_not_found", reason="target_unavailable"
                        )
                try:
                    attempted = True
                    return self.repository.execute(self.scope, project, intent, self.clock())
                except Exception:  # noqa: BLE001 - reconcile only the exact durable operation
                    try:
                        prior = self.repository.reconcile(self.scope, project, intent, self.clock())
                        if prior:
                            return prior
                    except Exception:  # noqa: BLE001, S110 - commit may have happened
                        pass
                    return OperationResult(
                        status="unknown_commit",
                        reason="reconcile_same_operation",
                        operation_id=intent.operation_id,
                    )
        except ResourceNotFoundError:
            return OperationResult(status="forbidden_or_not_found", reason="target_unavailable")
        except Exception:  # noqa: BLE001 - host or storage unavailable, never optimistic success
            return OperationResult(
                status="unknown_commit" if attempted else "temporarily_unavailable",
                reason="reconcile_same_operation"
                if attempted
                else "authority_or_storage_unavailable",
                operation_id=intent.operation_id,
            )
