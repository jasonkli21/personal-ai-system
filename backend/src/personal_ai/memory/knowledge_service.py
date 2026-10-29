"""Default-off admission, scoped selection and final consumption authority."""

from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import NAMESPACE_URL, uuid5

from personal_ai.auth.scope import ApplicationScope, current_request_scope, scope_matches
from personal_ai.contracts.context_references import (
    ContextEntityReference,
    ContextPermissionDependency,
)
from personal_ai.memory.contracts import (
    MemoryCandidateTrace,
    MemoryRetrievalTrace,
    RetrievalResult,
    ScoredMemory,
)
from personal_ai.memory.dependencies import dependency_version
from personal_ai.memory.knowledge import (
    KnowledgeAdmission,
    KnowledgeRecord,
    admission_key,
    digest,
)
from personal_ai.memory.knowledge_sources import KnowledgeSourceError, UnsupportedKnowledgeResolver
from personal_ai.memory.policy import content_reason


def same_actor(first, second):
    return (first.owner_id, first.application_id, first.workspace_id, first.acting_user_id) == (
        second.owner_id,
        second.application_id,
        second.workspace_id,
        second.acting_user_id,
    )


def permitted_content(proposal, settings):
    text = " ".join(
        [
            proposal.title,
            proposal.claim,
            *proposal.preconditions,
            *proposal.steps,
            *proposal.limitations,
        ]
    )
    # Keep old extraction policy unchanged. Commands are a closed metadata
    # allowlist; no shell parsing, stdout, arbitrary paths or executable text.
    if content_reason(text, settings):
        return False
    denied = ("ignore", "system prompt", "override", "exfiltrat", "instructions", "sudo", "curl ")
    return not any(term in text.casefold() for term in denied) and all(
        ord(c) >= 32 and ord(c) < 127 for c in text
    )


class KnowledgeService:
    def __init__(self, settings, repository, lifecycle, resolver=None, *, clock=None):
        self.settings, self.repository, self.lifecycle = settings, repository, lifecycle
        self.resolver = resolver or UnsupportedKnowledgeResolver()
        self.clock = clock or (lambda: datetime.now(UTC))

    def _scope(self, scope):
        bound = current_request_scope()
        return bound is not None and same_actor(bound, scope) and scope_matches(scope)

    def _authorized(self, scope):
        return self._scope(scope) and self.resolver.authorize_memory(scope)

    def _evidence_reason(self, evidence, scope, project):
        now = self.clock()
        if not self._authorized(scope) or not same_actor(evidence.scope, scope):
            return "not_authorized"
        if evidence.scope.client_context or evidence.scope.capabilities:
            return "source_scope_not_minimized"
        if evidence.project != project:
            return "source_stale"
        if evidence.outcome != "success":
            return "outcome_unverified"
        if (
            not evidence.observed_at <= evidence.verified_at <= now
            or evidence.effective_at > now
            or evidence.expires_at <= now
        ):
            return "source_time_invalid"
        p = evidence.proposal
        if not permitted_content(p, self.settings):
            return "content_policy"
        if evidence.expires_at > evidence.observed_at + timedelta(days=30):
            return "source_retention_unbounded"
        if p.kind == "procedure" and (
            p.title != "Repository validation"
            or p.claim != f"Historical success running {p.command}."
            or p.preconditions != ("Check the current repository revision.",)
            or p.limitations != ("Applies only to the recorded project revision.",)
        ):
            # Source access and a valid command receipt do not support arbitrary
            # prose. This first recipe states only the observed historical run.
            return "unsupported_claim"
        expected = (
            ("tool_receipt_verified", "verified", "repository_test", "supports")
            if p.kind == "procedure"
            else ("user_asserted", "user_confirmed", "completed_user_turn", "confirmed_by")
        )
        if (evidence.source_authority, evidence.verification_status, evidence.tool) != expected[
            :3
        ] or any(
            edge.relation != expected[3] or edge.resolver_id != evidence.issuer
            for edge in evidence.edges
        ):
            return "authority_mismatch"
        return None

    def admit(self, scope, project_id, reference, proposal):
        if not self.settings.memory_enabled or not self.settings.memory_knowledge_admission_enabled:
            return KnowledgeAdmission(status="rejected", reason="disabled")
        if not self._scope(scope):
            return KnowledgeAdmission(status="rejected", reason="not_authorized")
        record = None
        try:
            evidence = self.resolver.resolve(reference, scope)
            with self.resolver.lease(scope, project_id):
                project = self.resolver.project(scope, project_id)
                current = self.resolver.resolve(reference, scope)
                if evidence != current or current.proposal != proposal:
                    raise KnowledgeSourceError("receipt_mismatch")
                reason = self._evidence_reason(current, scope, project)
                if reason:
                    raise KnowledgeSourceError(reason)
                key = admission_key(current)
                record = KnowledgeRecord(
                    id=uuid5(NAMESPACE_URL, "personal-ai-knowledge:" + key),
                    owner_id=scope.owner_id,
                    application_id=scope.application_id,
                    workspace_id=scope.workspace_id,
                    scope_version=2,
                    acting_user_id=scope.acting_user_id,
                    project=project,
                    proposal=proposal,
                    evidence=current,
                    admission_key=key,
                    payload_fingerprint=digest(current),
                    created_at=self.clock(),
                )
                saved, created = self.repository.create_knowledge(record)
                state = self.lifecycle.get_state(owner_id=scope.owner_id, memory_id=saved.id)
                if (
                    state.validity_epoch != record.expected_validity_epoch
                    or state.retrieval_status != "active"
                    or state.unresolved_conflict
                ):
                    return KnowledgeAdmission(
                        status="conflict", reason="lifecycle_changed", record_id=saved.id
                    )
                return KnowledgeAdmission(
                    status="created" if created else "already_exists",
                    reason="durably_saved",
                    record_id=saved.id,
                )
        except KnowledgeSourceError as error:
            return KnowledgeAdmission(status="rejected", reason=str(error))
        except ValueError:
            return KnowledgeAdmission(status="conflict", reason="identity_or_epoch_conflict")
        except Exception:  # noqa: BLE001 - never infer success from a write attempt
            # A known record after a lost acknowledgement is reconciled using
            # exactly the original key. It is never reinserted here.
            if record is not None:
                try:
                    saved = self.repository.get_knowledge(
                        owner_id=scope.owner_id, memory_id=record.id
                    )
                    if (
                        self.reason(saved, scope) is None
                        and saved.payload_fingerprint == record.payload_fingerprint
                    ):
                        return KnowledgeAdmission(
                            status="already_exists",
                            reason="reconciled_original_key",
                            record_id=saved.id,
                        )
                except Exception:  # noqa: BLE001 - unavailable read means unknown
                    return KnowledgeAdmission(
                        status="unknown_commit",
                        reason="reconciliation_unavailable",
                        record_id=record.id,
                    )
            return KnowledgeAdmission(
                status="unknown_commit",
                reason="storage_or_authority_unavailable",
                record_id=record.id if record else None,
            )

    def reason(self, record, scope):
        if not self._authorized(scope) or not same_actor(scope, record.evidence.scope):
            return "not_authorized"
        project = self.resolver.project(scope, record.project.project_id)
        reason = self._evidence_reason(record.evidence, scope, project)
        if reason:
            return reason
        if not self.repository.knowledge_sources_current(record):
            return "source_revoked"
        state = self.lifecycle.get_state(owner_id=scope.owner_id, memory_id=record.id)
        if (
            state.retrieval_status != "active"
            or state.validity_epoch != record.expected_validity_epoch
            or state.unresolved_conflict
        ):
            return "lifecycle_changed"
        for edge in record.evidence.edges:
            resolved = self.resolver.resolve(edge.source_id, scope)
            if digest(resolved) != record.payload_fingerprint or edge not in resolved.edges:
                return "source_changed"
        return None

    def dependency(self, record, scope):
        state = self.lifecycle.get_state(owner_id=scope.owner_id, memory_id=record.id)
        return ContextPermissionDependency(
            permission_id="ai_memory_knowledge",
            version=dependency_version(record, state),
            purpose="reuse historically verified project knowledge",
            owner_id=scope.owner_id,
            acting_user_id=scope.acting_user_id,
            source_scope=ApplicationScope(
                application_id=scope.application_id, workspace_id=scope.workspace_id
            ),
            entity_ref=ContextEntityReference(
                entity_type="memory_knowledge",
                entity_id=str(record.id),
                application_id=scope.application_id,
                workspace_id=scope.workspace_id,
            ),
            source_revision=record.payload_fingerprint,
        )

    def is_current(self, dependency):
        scope = current_request_scope()
        if (
            not self.settings.memory_enabled
            or not self.settings.memory_knowledge_selection_enabled
            or scope is None
        ):
            return False
        try:
            from uuid import UUID

            record = self.repository.get_knowledge(
                owner_id=scope.owner_id, memory_id=UUID(dependency.entity_ref.entity_id)
            )
            return (
                self.reason(record, scope) is None and self.dependency(record, scope) == dependency
            )
        except Exception:  # noqa: BLE001 - deleted/unavailable authority denies
            return False

    def select(self, query):
        started = monotonic()
        if not self.settings.memory_enabled or not self.settings.memory_knowledge_selection_enabled:
            return RetrievalResult(diagnostics=("knowledge_disabled",))
        selected, excluded, metadata, dependencies, traces = [], [], [], [], []
        try:
            if query.knowledge is None or not self._scope(query.scope):
                raise KnowledgeSourceError("not_authorized")
            if (
                self.resolver.project(query.scope, query.knowledge.project.project_id)
                != query.knowledge.project
            ):
                raise KnowledgeSourceError("source_stale")
            records = self.repository.list_knowledge(
                scope=query.scope,
                filters=query.knowledge,
                limit=query.candidate_limit + 1,
                timeout=min(query.time_budget_seconds, max(0.001, query.deadline - monotonic())),
            )
            if len(records) > query.candidate_limit:
                return RetrievalResult(diagnostics=("knowledge_candidate_budget_exceeded",))
            for record in records:
                if monotonic() >= query.deadline:
                    raise TimeoutError("knowledge_deadline")
                reason = self.reason(record, query.scope)
                if (
                    record.project != query.knowledge.project
                    or record.proposal.kind not in query.knowledge.kinds
                    or record.evidence.source_authority not in query.knowledge.authorities
                ):
                    reason = "knowledge_filter_mismatch"
                elif record.evidence.observed_at > query.as_of or record.effective_at > query.as_of:
                    reason = "knowledge_as_of_mismatch"
                if reason is None and len(selected) >= query.max_items:
                    reason = "retrieval_limit"
                metadata.append(
                    (
                        record.id,
                        {
                            "kind": record.proposal.kind,
                            "authority": record.evidence.source_authority,
                            "revision": record.project.revision,
                            "sources": [e.model_dump() for e in record.evidence.edges],
                            "disposition": reason or "selected",
                        },
                    )
                )
                if reason:
                    excluded.append((record.id, reason))
                else:
                    selected.append(ScoredMemory(record, 1.0, origins=("verified_project_exact",)))
                    dependencies.append((record.id, (self.dependency(record, query.scope),)))
                traces.append(
                    MemoryCandidateTrace(
                        memory_id=record.id,
                        original_ids=(record.id,),
                        origins=("verified_project_exact",),
                        disposition=reason or "selected",
                        lifecycle=self.lifecycle.get_state(
                            owner_id=record.owner_id, memory_id=record.id
                        ).retrieval_status,
                        provenance_state="ineligible" if reason else "eligible",
                        source_identity=record.payload_fingerprint,
                        freshness="episodic",
                        authority=record.evidence.source_authority,
                        dependencies=dict(dependencies).get(record.id, ()),
                        estimated_tokens=(len(record.content) + 3) // 4 if reason is None else 0,
                    )
                )
            if monotonic() >= query.deadline:
                raise TimeoutError("knowledge_deadline")
            return RetrievalResult(
                candidates=tuple(ScoredMemory(r, 1.0) for r in records),
                selected=tuple(selected),
                excluded=tuple(excluded),
                requested_variant="mem1_verified_knowledge",
                applied_variant="mem1_verified_knowledge",
                policy_version="verified-knowledge-v1",
                inspection_metadata=tuple(metadata),
                permission_dependencies=tuple(dependencies),
                trace=MemoryRetrievalTrace(
                    query=query,
                    ranker_version="verified-project-exact-v1",
                    packing_version="whole-v1",
                    candidates=tuple(traces),
                    complete=True,
                    hard_exclusion_count=len(excluded),
                    elapsed_ms=(monotonic() - started) * 1000,
                ),
            )
        except Exception:  # noqa: BLE001 - no partial selection on failed authority
            return RetrievalResult(diagnostics=("knowledge_authority_unavailable",))

    def consume(self, dependency, action):
        """Trusted host executes a new action inside the final authority lease."""
        scope = current_request_scope()
        if scope is None or not self.is_current(dependency):
            raise KnowledgeSourceError("consumption_denied")
        from uuid import UUID

        record = self.repository.get_knowledge(
            owner_id=scope.owner_id, memory_id=UUID(dependency.entity_ref.entity_id)
        )
        with (
            self.resolver.lease(scope, record.project.project_id),
            self.repository.knowledge_consumption_guard(record),
        ):
            if not self.is_current(dependency):
                raise KnowledgeSourceError("consumption_denied")
            return action(record)
