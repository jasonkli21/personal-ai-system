"""Hash-sealed public fixture authority. Never authenticates runtime memory."""

import json
from contextlib import contextmanager
from datetime import datetime
from hashlib import sha256
from importlib.resources import files
from threading import RLock
from time import monotonic
from uuid import uuid4

from pydantic import ValidationError

from personal_ai.auth.scope import ApplicationScope
from personal_ai.contracts.context_references import (
    ContextEntityReference,
    ContextPermissionDependency,
)
from personal_ai.memory.research.contracts import (
    MAX_BYTES,
    MAX_RECORDS,
    ResearchFailure,
    ResearchQuery,
    ResearchRecord,
    ResearchScope,
    digest,
)

CORPUS_SHA256 = "d7cf41366fa77e01fb9480eed0d617048d9abcfd468dca014417d91492b95d7a"


def fixture():
    path = files("personal_ai.evaluation").joinpath("fixtures/memory/memory-navigation-v1.json")
    payload = path.read_bytes()
    if len(payload) > MAX_BYTES or sha256(payload).hexdigest() != CORPUS_SHA256:
        raise ResearchFailure("unavailable", "fixture_identity_changed")
    return json.loads(payload)


class FixtureAuthority:
    """A single synthetic issuer with terminal tombstones and a bounded lock lease.

    Cache snapshots may be copied; authority state cannot be restored through this
    interface. Cold replacement of this entire simulator is not anti-rollback proof.
    """

    def __init__(self, *, clock=None):
        data = fixture()
        self._records = {r.id: r for r in map(ResearchRecord.model_validate, data["records"])}
        if len(self._records) != len(data["records"]) or len(self._records) > MAX_RECORDS:
            raise ResearchFailure("incomplete", "corpus_cap")
        self._grants = frozenset(
            (digest(ResearchScope.model_validate(g["scope"])), g["project"]) for g in data["grants"]
        )
        self._clock = clock or (lambda: datetime.fromisoformat(data["clock"]))
        self._lock = RLock()
        self._revision = 1
        self._instance = uuid4().hex
        self._tombstones = set()
        self._purged = set()
        self._available = True
        # Corrections retain their suppression after later withdrawal.
        self._superseded = frozenset(i for r in self._records.values() for i in r.supersedes)

    def now(self):
        return self._clock()

    @contextmanager
    def lease(self, query, *, cancelled=lambda: False):
        deadline = min(query.canonical.deadline, monotonic() + 2)
        if cancelled():
            raise ResearchFailure("cancelled", "cancelled")
        if monotonic() >= deadline:
            raise ResearchFailure("timed_out", "deadline")
        if not self._lock.acquire(timeout=max(0, deadline - monotonic())):
            raise ResearchFailure("timed_out", "lease_timeout")
        lease_end = min(deadline, monotonic() + 5)
        try:
            self.check(query, cancelled=cancelled)
            yield
            if monotonic() >= lease_end:
                raise ResearchFailure("timed_out", "lease_expired")
            self.check(query, cancelled=cancelled)
        finally:
            self._lock.release()

    def check(self, query, *, cancelled=lambda: False):
        try:
            ResearchQuery.model_validate(query.model_dump(mode="python"))
        except ValidationError as exc:
            raise ResearchFailure("denied", "query_invalid") from exc
        if cancelled():
            raise ResearchFailure("cancelled", "cancelled")
        if monotonic() >= query.canonical.deadline:
            raise ResearchFailure("timed_out", "deadline")
        scope = ResearchScope.from_request(query.canonical.scope)
        if not self._available:
            raise ResearchFailure("unavailable", "issuer_unavailable")
        if (
            (digest(scope), query.project) not in self._grants
            or scope.owner_id in self._purged
            or query.canonical.as_of > self.now()
        ):
            raise ResearchFailure("denied", "authority_denied")

    def eligible(self, record, query):
        return (
            record.scope == ResearchScope.from_request(query.canonical.scope)
            and record.project == query.project
            and record.lifecycle == "active"
            and record.sensitivity == "public"
            and record.id not in self._tombstones | self._superseded
            and record.scope.owner_id not in self._purged
            and record.observed_at <= self.now()
            and record.effective_at <= query.canonical.as_of
            and record.expires_at > self.now()
            and (not query.kinds or record.kind in query.kinds)
            and (not query.source_classes or record.source_class in query.source_classes)
            and (query.observed_after is None or record.observed_at >= query.observed_after)
            and (query.effective_before is None or record.effective_at <= query.effective_before)
            and (query.source_revision is None or record.source_revision == query.source_revision)
        )

    def universe(self, query):
        self.check(query)
        records = tuple(
            sorted(
                (r for r in self._records.values() if self.eligible(r, query)), key=lambda r: r.id
            )
        )
        if len(records) > min(MAX_RECORDS, query.canonical.candidate_limit):
            raise ResearchFailure("incomplete", "candidate_cap")
        return records

    def generation(self, query):
        records = self.universe(query)
        return digest(
            [
                CORPUS_SHA256,
                self._instance,
                self._revision,
                self.query_identity(query),
                [(r.id, digest(r), self.dependency(r).version) for r in records],
            ]
        )

    @staticmethod
    def query_identity(query):
        # Request deadlines/IDs do not change immutable cache content or rights.
        return digest(
            [
                ResearchScope.from_request(query.canonical.scope).model_dump(),
                query.project,
                query.kinds,
                query.source_classes,
                str(query.observed_after),
                str(query.effective_before),
                query.source_revision,
                str(query.canonical.as_of),
                query.canonical.embedding_space.identity,
            ]
        )

    def dependency(self, record):
        return ContextPermissionDependency(
            permission_id="synthetic_memory_navigation",
            version=digest([digest(record), self._instance, self._revision]),
            purpose="public synthetic navigation only",
            owner_id=record.scope.owner_id,
            acting_user_id=record.scope.acting_user_id,
            source_scope=ApplicationScope(
                application_id=record.scope.application_id, workspace_id=record.scope.workspace_id
            ),
            entity_ref=ContextEntityReference(
                entity_type="synthetic_memory",
                entity_id=record.id,
                application_id=record.scope.application_id,
                workspace_id=record.scope.workspace_id,
            ),
            source_revision=record.source_revision,
        )

    def is_current(self, dependency):
        with self._lock:
            if not self._available or dependency.entity_ref is None:
                return False
            record = self._records.get(dependency.entity_ref.entity_id)
            return bool(
                record is not None
                and record.lifecycle == "active"
                and record.sensitivity == "public"
                and record.expires_at > self.now()
                and record.id not in self._tombstones | self._superseded
                and record.scope.owner_id not in self._purged
                and self.dependency(record) == dependency
            )

    def fetch(self, index, query, ids):
        with self.lease(query):
            return self._fetch(index, query, ids)

    def _fetch(self, index, query, ids):
        self.check(query)
        if len(ids) > 16 or len(set(ids)) != len(ids):
            raise ResearchFailure("incomplete", "fetch_cap")
        if index.generation != self.generation(query):
            raise ResearchFailure("denied", "generation_changed")
        entries = {e.record_id: e for e in index.entries}
        result = []
        for identifier in ids:
            record = self._records.get(identifier)
            entry = entries.get(identifier)
            if (
                record is None
                or entry is None
                or not self.eligible(record, query)
                or entry.fingerprint != digest(record)
                or entry.dependency_version != self.dependency(record).version
            ):
                raise ResearchFailure("denied", "leaf_changed")
            result.append(record)
        return tuple(result)

    def transition(self, action, identifier):
        """Synthetic invalidation only; never adds records, grants or source IDs."""
        with self._lock:
            if identifier not in self._records:
                raise ResearchFailure("denied", "unknown_source")
            if action in ("forget", "revoke", "correct", "expire", "regrant"):
                # Regrant cannot rehabilitate an old source identity.
                self._tombstones.add(identifier)
            elif action == "purge":
                self._purged.add(self._records[identifier].scope.owner_id)
            elif action == "unavailable":
                self._available = False
            else:
                raise ResearchFailure("unsupported", "transition_unsupported")
            self._revision += 1
