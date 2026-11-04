"""Finite synthetic issuer for offline tests. This is not a runtime source adapter."""

import json
from contextlib import contextmanager
from hashlib import sha256
from importlib.resources import files
from threading import RLock

from pydantic import ValidationError

from personal_ai.memory.consolidation.contracts import (
    BACKFILL_GENERATION,
    GENERATION,
    MAX_SOURCES,
    PAGE_SIZE,
    V2_SOURCE_V1_POLICY_GENERATION,
    ConsolidationDenied,
    ConsolidationScope,
    EvidenceEdge,
    SourceEnvelope,
    SourcePage,
    checked,
    edge,
)
from personal_ai.memory.knowledge import digest

CORPUS_SHA256 = "137b432e57ff35a2184c4cc4ace58befd2c27468b01ceadde0dd658c1253becf"
ADVERSARIAL_CORPUS_SHA256 = "ca671aee1b7b21226d147808c41aeae263aa97a558a6fcf42c0372860e436ec7"
GENERATION_COMPATIBILITY = {
    CORPUS_SHA256: frozenset({GENERATION}),
    ADVERSARIAL_CORPUS_SHA256: frozenset({V2_SOURCE_V1_POLICY_GENERATION, BACKFILL_GENERATION}),
}


def generations_for_corpus(corpus_digest):
    return GENERATION_COMPATIBILITY.get(corpus_digest, frozenset())


def generation_matches_corpus(corpus_digest, generation):
    return generation in generations_for_corpus(corpus_digest)


def load_corpus(version="v1"):
    if version not in {"v1", "v2"}:
        raise ConsolidationDenied()
    expected = CORPUS_SHA256 if version == "v1" else ADVERSARIAL_CORPUS_SHA256
    data = (
        files("personal_ai.evaluation")
        .joinpath(f"fixtures/memory/offline-consolidation-{version}.json")
        .read_bytes()
    )
    if len(data) > 262144 or sha256(data).hexdigest() != expected:
        raise ConsolidationDenied()
    return json.loads(data)


class FrozenFixtureSource:
    """Only the exact bundled public synthetic bytes are eligible.

    Mutations model an issuer in tests under one process lock. They establish no
    real consent, source authentication, deletion orchestration or recoverability.
    Reconstructing this object starts a NEW disposable simulation, never a restore.
    """

    def __init__(self, *, clock, corpus="v1"):
        self.clock = clock
        self.lock = RLock()
        records = tuple(SourceEnvelope.model_validate(r) for r in load_corpus(corpus)["records"])
        self.corpus_digest = CORPUS_SHA256 if corpus == "v1" else ADVERSARIAL_CORPUS_SHA256
        if len(records) > MAX_SOURCES:
            raise ConsolidationDenied()
        self._streams = {}
        self._scopes = {}
        self._records = {}
        for source in records:
            key = source.scope.key
            self._scopes[key] = source.scope
            self._streams.setdefault(key, []).append(source)
            identity = (key, source.source_id, source.revision, source.epoch)
            if identity in self._records:
                raise ConsolidationDenied()
            self._records[identity] = source
        for key, stream in self._streams.items():
            if tuple(s.sequence for s in stream) != tuple(range(1, len(stream) + 1)):
                raise ConsolidationDenied()
            if any(
                s.supersedes is not None
                and not any(
                    p.source_id == s.supersedes
                    and p.sequence < s.sequence
                    and p.fact.command == s.fact.command
                    and p.source_id != s.source_id
                    for p in stream
                )
                for s in stream
            ):
                raise ConsolidationDenied()
        self._published = dict.fromkeys(self._streams, 0)
        self._epochs = {}
        for record in records:
            identity = record.scope.key, record.source_id
            self._epochs[identity] = min(self._epochs.get(identity, record.epoch), record.epoch)
        self._withdrawn = set()
        self._forgotten = set()

    def lease_now(self):
        """Synthetic in-memory leases use the hermetic fixture clock."""
        return self.clock()

    def _scope(self, scope):
        try:
            scope = checked(scope, ConsolidationScope)
            if scope.key not in self._scopes or scope.key in self._forgotten:
                raise ConsolidationDenied()
            return scope.key
        except (AttributeError, TypeError, ValueError):
            raise ConsolidationDenied() from None

    @contextmanager
    def guard(self):
        if not self.lock.acquire(timeout=2):
            raise ConsolidationDenied()
        try:
            yield
        finally:
            self.lock.release()

    def publish(self, scope, through):
        """Monotonic publication of a bounded corpus prefix; no caller payload."""
        with self.guard():
            key = self._scope(scope)
            if type(through) is not int or not self._published[key] <= through <= len(
                self._streams[key]
            ):
                raise ConsolidationDenied()
            self._published[key] = through

    def page(self, scope, after, *, generation=None):
        with self.guard():
            key = self._scope(scope)
            if type(after) is not int or not 0 <= after <= self._published[key]:
                raise ConsolidationDenied()
            records = tuple(
                self._streams[key][after : min(after + PAGE_SIZE, self._published[key])]
            )
            options = {"generation": generation} if generation is not None else {}
            return (
                SourcePage(scope=scope, after=after, records=records, **options)
                if records
                else None
            )

    def authentic(self, source, scope):
        """Membership/authenticity is separate from current eligibility."""
        try:
            envelope = checked(source, SourceEnvelope)
            return (
                envelope.scope == scope
                and self._records.get(
                    (scope.key, envelope.source_id, envelope.revision, envelope.epoch)
                )
                == envelope
                and envelope.sequence <= self._published[scope.key]
            )
        except (AttributeError, TypeError, ValueError, KeyError, ValidationError):
            return False

    def current(self, source, scope):
        with self.guard():
            key = self._scope(scope)
            if not self.authentic(source, scope):
                return False
            identity = (key, source.source_id)
            now = self.clock()
            return (
                identity not in self._withdrawn
                and self._epochs[identity] == source.epoch
                and source.observed_at <= now < source.expires_at
                and not any(
                    p.source_id == source.source_id
                    and p.epoch == source.epoch
                    and p.revision > source.revision
                    for p in self._streams[key][: self._published[key]]
                )
                and not any(
                    p.supersedes == source.source_id
                    for p in self._streams[key][: self._published[key]]
                )
            )

    def resolve(self, scope, evidence_edge):
        with self.guard():
            self._scope(scope)
            evidence_edge = checked(evidence_edge, EvidenceEdge)
            source = self._records.get(
                (scope.key, evidence_edge.source_id, evidence_edge.revision, evidence_edge.epoch)
            )
            if source and edge(source) == evidence_edge and self.current(source, scope):
                return source
            return None

    def corrections(self, scope, fact):
        with self.guard():
            key = self._scope(scope)
            return tuple(
                s
                for s in self._streams[key][: self._published[key]]
                if s.evidence == "user_correction"
                and (s.fact.command, s.fact.revision) == (fact.command, fact.revision)
                and self.current(s, scope)
            )

    def correction_barrier(self, scope, fact):
        """Withdrawing a correction cannot implicitly restore an older assertion."""
        with self.guard():
            key = self._scope(scope)
            return any(
                s.evidence == "user_correction"
                and (s.fact.command, s.fact.revision) == (fact.command, fact.revision)
                for s in self._streams[key][: self._published[key]]
            )

    def withdraw(self, scope, source_id):
        with self.guard():
            key = self._scope(scope)
            identity = key, source_id
            if identity not in self._epochs:
                raise ConsolidationDenied()
            # The finite namespace reserves all tombstones up front, so forgetting
            # never needs a new capacity slot or deletes an original-key fence.
            self._epochs[identity] = min(1024, self._epochs[identity] + 1)
            self._withdrawn.add(identity)

    def regrant(self, scope, source_id):
        with self.guard():
            self.withdraw(scope, source_id)
            if self._epochs[scope.key, source_id] >= 1024:
                raise ConsolidationDenied()
            self._withdrawn.remove((scope.key, source_id))
            # Old envelopes cannot assert this new issuer epoch. A new immutable
            # source would need a separately frozen fixture generation.

    def forget(self, *, owner, project=None):
        with self.guard():
            for key, scope in self._scopes.items():
                if scope.owner == owner and (project is None or scope.project == project):
                    self._forgotten.add(key)

    @property
    def scopes(self):
        return tuple(self._scopes.values())

    def diagnostics(self):
        with self.guard():
            return {
                "streams": len(self._streams),
                "withdrawn": len(self._withdrawn),
                "forgotten": len(self._forgotten),
                "corpus_digest": self.corpus_digest,
            }

    def __repr__(self):
        return f"FrozenFixtureSource({digest(self.diagnostics())})"
