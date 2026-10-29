"""Stateful hermetic MEM-1 authority and tools; never production composition."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from threading import RLock
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

from personal_ai.auth.scope import bind_request_scope, reset_request_scope
from personal_ai.memory.knowledge import KnowledgeEdge, KnowledgeEvidence, ProjectSnapshot, digest
from personal_ai.memory.knowledge_sources import KnowledgeSourceError

NOW = datetime(2026, 10, 29, 12, tzinfo=UTC)
ISSUER = "hermetic-repository-v1"


@contextmanager
def request(scope):
    token = bind_request_scope(scope)
    try:
        yield
    finally:
        reset_request_scope(token)


def actor_key(scope):
    return scope.owner_id, scope.application_id, scope.workspace_id, scope.acting_user_id


class HermeticKnowledgeAuthority:
    """Trusted fake issues receipts only after an observed stateful tool action."""

    def __init__(self, scope, *, project_id="repo-alpha"):
        self._lock = RLock()
        self.projects = {
            (actor_key(scope), project_id): ProjectSnapshot(
                project_id=project_id,
                revision="rev-one",
                branch="main",
                permission_version="grant-one",
            )
        }
        self.receipts, self.revoked, self.effects = {}, set(), {}
        self.issued_fingerprints = {}
        self.effect_count = 0
        self.trace = []
        self.disclosure_allowed = True

    def authorize_memory(self, scope):
        return self.disclosure_allowed and any(key[0] == actor_key(scope) for key in self.projects)

    def project(self, scope, project_id):
        with self._lock:
            project = self.projects.get((actor_key(scope), project_id))
            if project is None:
                raise KnowledgeSourceError("project_not_authorized")
            return project

    @contextmanager
    def lease(self, scope, project_id):
        with self._lock:
            self.project(scope, project_id)
            yield

    def resolve(self, reference, scope):
        with self._lock:
            evidence = self.receipts.get(reference)
            if (
                evidence is None
                or reference in self.revoked
                or actor_key(scope) != actor_key(evidence.scope)
            ):
                raise KnowledgeSourceError("source_not_authorized")
            observed = self.effects.get(
                (actor_key(scope), evidence.project.project_id, evidence.run_id)
            )
            if (
                evidence.issuer != ISSUER
                or self.issued_fingerprints.get(evidence.receipt_id) != digest(evidence)
                or observed is None
                or observed[1]["receipt_id"] != evidence.receipt_id
                or observed[1]["outcome"] != evidence.outcome
                or observed[1]["command"] != (evidence.proposal.command or evidence.proposal.claim)
            ):
                raise KnowledgeSourceError("receipt_binding_invalid")
            return evidence

    def complete_task_a(
        self,
        scope,
        project_id,
        proposal,
        *,
        run_id="task-a",
        outcome="success",
        confirmed=True,
        edges=1,
    ):
        with self.lease(scope, project_id):
            project = self.project(scope, project_id)
            command = proposal.command or proposal.claim
            # Actually simulate the historical action, producing an outcome
            # distinct from durable-memory effects and the later target run.
            result = self.execute(
                scope,
                project_id,
                run_id,
                command,
                expected_revision=project.revision,
                outcome=outcome,
            )
            if not confirmed:
                return result["receipt_id"]  # Unregistered claims cannot resolve.
            sources = tuple(
                KnowledgeEdge(
                    source_id=f"{run_id}:source:{index}",
                    resolver_id=ISSUER,
                    fingerprint=digest(
                        {"result": result, "proposal": proposal.model_dump(), "ordinal": index}
                    ),
                    epoch=0,
                    relation="supports" if proposal.kind == "procedure" else "confirmed_by",
                )
                for index in range(edges)
            )
            evidence = KnowledgeEvidence(
                scope=scope,
                project=project,
                proposal=proposal,
                issuer=ISSUER,
                task_id=run_id,
                run_id=run_id,
                attempt_id=run_id + ":attempt-one",
                tool="repository_test" if proposal.kind == "procedure" else "completed_user_turn",
                receipt_id=result["receipt_id"],
                outcome=outcome,
                source_authority="tool_receipt_verified"
                if proposal.kind == "procedure"
                else "user_asserted",
                verification_status="verified"
                if proposal.kind == "procedure"
                else "user_confirmed",
                observed_at=NOW - timedelta(minutes=2),
                effective_at=NOW - timedelta(minutes=2),
                verified_at=NOW - timedelta(minutes=1),
                expires_at=NOW + timedelta(days=1),
                edges=sources,
            )
            self.receipts[evidence.receipt_id] = evidence
            self.issued_fingerprints[evidence.receipt_id] = digest(evidence)
            for source in sources:
                self.receipts[source.source_id] = evidence
            return evidence.receipt_id

    def execute(
        self, scope, project_id, execution_key, command, *, expected_revision, outcome="success"
    ):
        project = self.project(scope, project_id)
        if expected_revision != project.revision:
            raise KnowledgeSourceError("pre_action_revision_mismatch")
        key = (actor_key(scope), project_id, execution_key)
        binding = (command, expected_revision)
        if key in self.effects:
            old_binding, result = self.effects[key]
            if old_binding != binding:
                raise KnowledgeSourceError("effect_identity_conflict")
            return result
        self.effect_count += 1
        result = {
            "receipt_id": str(
                uuid5(
                    NAMESPACE_URL,
                    digest(
                        [
                            list(actor_key(scope)),
                            project_id,
                            execution_key,
                            command,
                            expected_revision,
                        ]
                    ),
                )
            ),
            "run_id": execution_key,
            "command": command,
            "revision": project.revision,
            "outcome": outcome,
        }
        self.effects[key] = binding, result
        self.trace.append({"action": "execute", **result})
        return result

    def replace_evidence(self, reference, **updates):
        with self._lock:
            old = self.receipts[reference]
            new = old.model_copy(update=updates)
            for key, value in list(self.receipts.items()):
                if value is old:
                    self.receipts[key] = new
            return new

    def change_project(self, scope, project_id, **changes):
        with self._lock:
            key = actor_key(scope), project_id
            self.projects[key] = self.project(scope, project_id).model_copy(update=changes)


def messages_stub():
    return SimpleNamespace(_mutation_lock=RLock(), _messages={})
