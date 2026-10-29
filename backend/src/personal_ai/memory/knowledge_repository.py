"""In-memory methods of the existing memory repository, matching SQL fences."""

from contextlib import contextmanager

from personal_ai.auth.scope import current_request_scope, scope_matches
from personal_ai.memory.knowledge import KnowledgeRecord
from personal_ai.storage.errors import ResourceNotFoundError

MAX_KNOWLEDGE_RECORDS = 128
MAX_KNOWLEDGE_SOURCES = 1024


def validate_knowledge(record):
    record = KnowledgeRecord.model_validate(record.model_dump())
    scope = current_request_scope()
    if (
        scope is None
        or not scope_matches(record, scope)
        or record.owner_id != scope.owner_id
        or record.acting_user_id != scope.acting_user_id
    ):
        raise ValueError("knowledge_scope_invalid")
    if len(record.model_dump_json().encode()) > 16384:
        raise ValueError("knowledge_storage_budget")
    return record


def namespace(record):
    return record.owner_id, record.application_id, record.workspace_id


class InMemoryKnowledgeMethods:
    def _init_knowledge(self):
        self.knowledge_records = {}
        self.knowledge_sources = {}
        self.knowledge_fenced_owners = set()

    @contextmanager
    def knowledge_consumption_guard(self, record):
        with self.messages._mutation_lock, self._lock:
            yield

    def create_knowledge(self, record, *, timeout=5):
        record = validate_knowledge(record)
        ns = namespace(record)
        with self.knowledge_consumption_guard(record):
            if record.owner_id in self.knowledge_fenced_owners:
                raise ValueError("owner_deletion_fenced")
            old = self.knowledge_records.get(record.id)
            if old:
                if (
                    old.payload_fingerprint != record.payload_fingerprint
                    or old.admission_key != record.admission_key
                ):
                    raise ValueError("knowledge_identity_conflict")
                state = self.knowledge_lifecycle.get_state(
                    owner_id=record.owner_id, memory_id=record.id
                )
                if (
                    state.validity_epoch
                    or state.retrieval_status != "active"
                    or state.unresolved_conflict
                    or not self.knowledge_sources_current(old)
                ):
                    raise ValueError("knowledge_epoch_conflict")
                return old, False
            if (
                sum(namespace(r) == ns for r in self.knowledge_records.values())
                >= MAX_KNOWLEDGE_RECORDS
            ):
                raise ValueError("knowledge_storage_budget")
            additions = {}
            for edge in record.evidence.edges:
                key = (*ns, edge.resolver_id, edge.source_id)
                expected = (edge.epoch, edge.fingerprint, True)
                if key in self.knowledge_sources and self.knowledge_sources[key] != expected:
                    raise ValueError("knowledge_source_epoch_conflict")
                additions[key] = expected
            if (
                sum(key[:3] == ns for key in set(self.knowledge_sources) | set(additions))
                > MAX_KNOWLEDGE_SOURCES
            ):
                raise ValueError("knowledge_source_budget")
            self.knowledge_sources.update(additions)
            self.knowledge_records[record.id] = record
            return record, True

    def get_knowledge(self, *, owner_id, memory_id, timeout=5):
        with self._lock:
            record = self.knowledge_records.get(memory_id)
            if record is None or record.owner_id != owner_id or not scope_matches(record):
                raise ResourceNotFoundError("knowledge not found")
            return record

    def list_knowledge(self, *, scope, filters, limit, timeout=5):
        if not 1 <= limit <= 101 or not scope_matches(scope):
            raise ValueError("knowledge_query_invalid")
        with self._lock:
            return tuple(
                sorted(
                    (
                        r
                        for r in self.knowledge_records.values()
                        if namespace(r) == namespace(scope)
                        and r.acting_user_id == scope.acting_user_id
                        and r.project.project_id == filters.project.project_id
                        and r.proposal.kind in filters.kinds
                        and r.evidence.source_authority in filters.authorities
                    ),
                    key=lambda r: (-r.created_at.timestamp(), str(r.id)),
                )
            )[:limit]

    def knowledge_sources_current(self, record, *, timeout=5):
        with self._lock:
            return record.owner_id not in self.knowledge_fenced_owners and all(
                self.knowledge_sources.get((*namespace(record), e.resolver_id, e.source_id))
                == (e.epoch, e.fingerprint, True)
                for e in record.evidence.edges
            )

    def revoke_knowledge_source(
        self, *, scope, resolver_id, source_id, expected_epoch, erase=False
    ):
        if (
            not scope_matches(scope)
            or current_request_scope() is None
            or current_request_scope().owner_id != scope.owner_id
        ):
            raise ValueError("knowledge_scope_invalid")
        with self.messages._mutation_lock, self._lock:
            key = (*namespace(scope), resolver_id, source_id)
            current = self.knowledge_sources.get(key)
            if current is None or current[0] != expected_epoch or not current[2]:
                return False
            self.knowledge_sources[key] = (expected_epoch + 1, current[1], False)
            if erase:
                for identifier, record in list(self.knowledge_records.items()):
                    if namespace(record) == namespace(scope) and any(
                        e.resolver_id == resolver_id and e.source_id == source_id
                        for e in record.evidence.edges
                    ):
                        del self.knowledge_records[identifier]
            return True

    def erase_expired_knowledge(self, *, scope, as_of, limit=100):
        if not 1 <= limit <= 100 or not scope_matches(scope):
            raise ValueError("knowledge_retention_scope_invalid")
        with self.messages._mutation_lock, self._lock:
            expired = [
                r
                for r in self.knowledge_records.values()
                if namespace(r) == namespace(scope) and r.evidence.expires_at <= as_of
            ][:limit]
            before = len(self.knowledge_records)
            for record in expired:
                for edge in record.evidence.edges:
                    self.revoke_knowledge_source(
                        scope=scope,
                        resolver_id=edge.resolver_id,
                        source_id=edge.source_id,
                        expected_epoch=edge.epoch,
                    )
                self.knowledge_records.pop(record.id, None)
            return before - len(self.knowledge_records)
