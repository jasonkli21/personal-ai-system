"""Opt-in synthetic PostgreSQL adapter; shares the offline transition algorithm."""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
from uuid import uuid4

from psycopg.types.json import Jsonb

from personal_ai.memory.consolidation.contracts import (
    GENERATION,
    BatchReceipt,
    ConsolidationDenied,
    DerivedProposal,
    Lease,
)
from personal_ai.memory.consolidation.repository import OfflineProposalRepository, _Stream
from personal_ai.memory.consolidation.sources import (
    FrozenFixtureSource,
    generation_matches_corpus,
    generations_for_corpus,
)
from personal_ai.memory.knowledge import digest
from personal_ai.persistence.postgres.owner_lifecycle import assert_owner_unfenced, lock_owner


def encode_state(state):
    return {
        "cursor": state.cursor,
        "fence": state.fence,
        "claims": state.claims,
        "lease": state.lease.model_dump(mode="json") if state.lease else None,
        "proposals": [p.model_dump(mode="json") for p in state.proposals],
        "receipts": [r.model_dump(mode="json") for r in state.receipts],
    }


def decode_state(payload):
    if set(payload) != set(asdict(_Stream())):
        raise ConsolidationDenied()
    if any(
        type(payload[k]) is not int or not 0 <= payload[k] <= 1024
        for k in ("cursor", "fence", "claims")
    ):
        raise ConsolidationDenied()
    if len(payload["proposals"]) > 64 or len(payload["receipts"]) > 64:
        raise ConsolidationDenied()
    return _Stream(
        cursor=payload["cursor"],
        fence=payload["fence"],
        claims=payload["claims"],
        lease=Lease.model_validate(payload["lease"]) if payload["lease"] else None,
        proposals=tuple(DerivedProposal.model_validate(p) for p in payload["proposals"]),
        receipts=tuple(BatchReceipt.model_validate(r) for r in payload["receipts"]),
    )


def _fixture_sources(clock):
    fixtures = {}
    scopes = {}
    for version in ("v1", "v2"):
        fixture = FrozenFixtureSource(clock=clock, corpus=version)
        fixtures[fixture.corpus_digest] = fixture
        scopes[fixture.corpus_digest] = {scope.key: scope.owner for scope in fixture.scopes}
    return fixtures, scopes


def _fixture_state(fixture, *, forgotten=()):
    return {
        "published": dict(fixture._published),
        "epochs": [
            [scope, source_id, value]
            for (scope, source_id), value in sorted(fixture._epochs.items())
        ],
        "withdrawn": [list(identity) for identity in sorted(fixture._withdrawn)],
        "forgotten": sorted(set(fixture._forgotten) | set(forgotten)),
    }


class PostgresFixtureSource(FrozenFixtureSource):
    """Durable *synthetic* issuer mutations, serialized across processes.

    Restoring only checkpoints is detected by content-free authority heads.
    Restoring this authority itself needs an external surviving fence; no claim
    of production source authority or full database rollback resistance is made.
    """

    def __init__(self, database, *, clock, corpus="v1"):
        if database._environment not in {"local", "test"}:
            raise ConsolidationDenied()
        super().__init__(clock=clock, corpus=corpus)
        self.database = database
        self._connection = None
        self._authority_id = None
        self._heads = {}
        self._minimum_revision = 0

    def _source_state(self):
        return {
            "published": dict(self._published),
            "epochs": [
                [scope, source, value] for (scope, source), value in sorted(self._epochs.items())
            ],
            "withdrawn": [list(k) for k in sorted(self._withdrawn)],
            "forgotten": sorted(self._forgotten),
        }

    def _restore_source(self, state):
        if set(state) != {"published", "epochs", "withdrawn", "forgotten"}:
            raise ConsolidationDenied()
        if set(state["published"]) != set(self._streams):
            raise ConsolidationDenied()
        if any(
            type(v) is not int or not 0 <= v <= len(self._streams[k])
            for k, v in state["published"].items()
        ):
            raise ConsolidationDenied()
        epochs = {(scope, source): value for scope, source, value in state["epochs"]}
        if set(epochs) != set(self._epochs) or any(
            type(v) is not int or not 1 <= v <= 1024 for v in epochs.values()
        ):
            raise ConsolidationDenied()
        withdrawn = {tuple(k) for k in state["withdrawn"]}
        forgotten = set(state["forgotten"])
        if not withdrawn <= epochs.keys() or not forgotten <= self._scopes.keys():
            raise ConsolidationDenied()
        self._published, self._epochs = state["published"], epochs
        self._withdrawn, self._forgotten = withdrawn, forgotten

    @contextmanager
    def guard(self):
        with super().guard():
            if self._connection is not None:
                yield
                return
            original = (self._source_state(), deepcopy(self._heads), self._authority_id)
            try:
                with self._database_guard():
                    yield
            except Exception:
                self._restore_source(original[0])
                self._heads, self._authority_id = original[1:]
                raise

    @contextmanager
    def _database_guard(self):
        with self.database.transaction(timeout_seconds=2) as connection:
            # Canonical lock ordering: owner fences precede source authority.
            for owner in sorted({s.owner for s in self.scopes}):
                lock_owner(connection, owner)
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                ("offline-consolidation:" + self.corpus_digest,),
            )
            row = connection.execute(
                "SELECT revision,payload FROM offline_consolidation_authorities "
                "WHERE corpus_digest=%s FOR UPDATE",
                (self.corpus_digest,),
            ).fetchone()
            if row:
                revision, payload = row
                if revision < self._minimum_revision:
                    raise ConsolidationDenied()
                if set(payload) != {"authority_id", "source", "heads"}:
                    raise ConsolidationDenied()
                if self._authority_id is not None and self._authority_id != payload["authority_id"]:
                    raise ConsolidationDenied()
                self._authority_id, self._heads = payload["authority_id"], payload["heads"]
                if len(self._heads) > 256:
                    raise ConsolidationDenied()
                self._restore_source(payload["source"])
            else:
                if (
                    self._authority_id is not None
                    or connection.execute(
                        "SELECT 1 FROM offline_consolidation_checkpoints WHERE corpus_digest=%s LIMIT 1",
                        (self.corpus_digest,),
                    ).fetchone()
                ):
                    raise ConsolidationDenied()
                self._authority_id, self._heads = str(uuid4()), {}
                revision, payload = 0, None
            self._connection = connection
            original_payload = deepcopy(payload)
            try:
                yield
                updated = {
                    "authority_id": self._authority_id,
                    "source": self._source_state(),
                    "heads": self._heads,
                }
                if updated != original_payload:
                    connection.execute(
                        "INSERT INTO offline_consolidation_authorities VALUES (%s,%s,%s) "
                        "ON CONFLICT(corpus_digest) DO UPDATE SET revision=EXCLUDED.revision,"
                        "payload=EXCLUDED.payload",
                        (self.corpus_digest, revision + 1, Jsonb(updated)),
                    )
            finally:
                self._connection = None
        self._minimum_revision = revision + (updated != original_payload)

    def _scope(self, scope):
        key = super()._scope(scope)
        if self._connection is not None:
            assert_owner_unfenced(self._connection, scope.owner)
        return key

    def lease_now(self):
        """Lease time comes from PostgreSQL, not the worker's wall clock."""
        if self._connection is None:
            raise ConsolidationDenied()
        return self._connection.execute("SELECT clock_timestamp()").fetchone()[0]


class PostgresProposalRepository(OfflineProposalRepository):
    """Same extraction/CAS/lease code, one real transaction for all state."""

    def __init__(self, source, *, generation=GENERATION):
        if type(source) is not PostgresFixtureSource:
            raise ConsolidationDenied()
        if not generation_matches_corpus(source.corpus_digest, generation):
            raise ConsolidationDenied()
        self.generation = generation
        self.source, self._states = source, {}
        self._active = False

    @contextmanager
    def _transaction(self, scope=None):
        with self.source.guard():
            if self._active:
                yield
                return
            connection = self.source._connection
            keys = (
                [self.source._scope(scope)]
                if scope is not None
                else [s.key for s in self.source.scopes]
            )
            states = {}
            for key in keys:
                row = connection.execute(
                    "SELECT payload FROM offline_consolidation_checkpoints "
                    "WHERE corpus_digest=%s AND scope_digest=%s AND generation=%s FOR UPDATE",
                    (self.source.corpus_digest, key, self.generation),
                ).fetchone()
                head = self.source._heads.get(digest([key, self.generation]))
                if (row is None) != (head is None) or row and digest(row[0]) != head:
                    raise ConsolidationDenied()
                states[key] = decode_state(row[0]) if row else _Stream()
            self._states, self._active = states, True
            original = {key: encode_state(value) for key, value in states.items()}
            try:
                yield
                for key, state in self._states.items():
                    updated = encode_state(state)
                    if updated == original[key]:
                        continue
                    # Ensure the source authority exists before its FK-dependent
                    # checkpoint. Both are still inside this same transaction.
                    connection.execute(
                        "INSERT INTO offline_consolidation_authorities VALUES (%s,1,%s) "
                        "ON CONFLICT DO NOTHING",
                        (
                            self.source.corpus_digest,
                            Jsonb(
                                {
                                    "authority_id": self.source._authority_id,
                                    "source": self.source._source_state(),
                                    "heads": self.source._heads,
                                }
                            ),
                        ),
                    )
                    connection.execute(
                        "INSERT INTO offline_consolidation_checkpoints VALUES (%s,%s,%s,%s,%s) "
                        "ON CONFLICT(corpus_digest,scope_digest,generation) "
                        "DO UPDATE SET payload=EXCLUDED.payload",
                        (
                            self.source.corpus_digest,
                            self.source._scopes[key].owner,
                            key,
                            self.generation,
                            Jsonb(updated),
                        ),
                    )
                    self.source._heads[digest([key, self.generation])] = digest(updated)
            finally:
                self._active = False

    def inventory_owner(self, owner_id):
        """Return content-free checkpoint counts while holding the owner lock."""
        _fixtures, fixture_scopes = _fixture_sources(self.source.clock)
        if type(owner_id) is not str or not any(
            owner_id in scopes.values() for scopes in fixture_scopes.values()
        ):
            raise ConsolidationDenied()
        with self.source.guard():
            rows = self.source._connection.execute(
                "SELECT scope_digest,generation,payload FROM offline_consolidation_checkpoints "
                "WHERE owner_id=%s ORDER BY scope_digest,generation",
                (owner_id,),
            ).fetchall()
            states = [decode_state(row[2]) for row in rows]
            return {
                "checkpoint_count": len(rows),
                "scope_count": len({row[0] for row in rows}),
                "generations": tuple(sorted({row[1] for row in rows})),
                "live_proposal_count": sum(len(state.proposals) for state in states),
                "receipt_count": sum(len(state.receipts) for state in states),
            }

    def purge_owner(self, owner_id):
        """Erase synthetic checkpoint payloads under a retained owner fence.

        Shared source authority remains content-free and retains scope tombstones;
        deleting a checkpoint head makes a restored derived row fail closed.
        """
        if type(owner_id) is not str:
            raise ConsolidationDenied()
        with self.source.guard():
            connection = self.source._connection
            if not connection.execute(
                "SELECT 1 FROM owner_lifecycle_fences WHERE owner_id=%s", (owner_id,)
            ).fetchone():
                raise ConsolidationDenied()
            rows = connection.execute(
                "SELECT corpus_digest,scope_digest,generation,payload "
                "FROM offline_consolidation_checkpoints WHERE owner_id=%s "
                "ORDER BY corpus_digest,scope_digest,generation FOR UPDATE",
                (owner_id,),
            ).fetchall()
            fixtures, fixture_scopes = _fixture_sources(self.source.clock)
            corpus_digests = sorted(fixture_scopes)
            authorities = connection.execute(
                "SELECT corpus_digest,revision,payload FROM offline_consolidation_authorities "
                "WHERE corpus_digest=ANY(%s) ORDER BY corpus_digest FOR UPDATE",
                (corpus_digests,),
            ).fetchall()
            authority_by_digest = {row[0]: (row[1], row[2]) for row in authorities}
            owner_scope_keys = {
                corpus_digest: {
                    key for key, scope_owner in scopes.items() if scope_owner == owner_id
                }
                for corpus_digest, scopes in fixture_scopes.items()
            }
            if not any(owner_scope_keys.values()):
                raise ConsolidationDenied()
            self.source._forgotten.update(owner_scope_keys.get(self.source.corpus_digest, set()))
            rows_by_corpus = {}
            for corpus_digest, scope_digest, generation, payload in rows:
                if (
                    corpus_digest not in fixture_scopes
                    or fixture_scopes[corpus_digest].get(scope_digest) != owner_id
                    or generation not in generations_for_corpus(corpus_digest)
                ):
                    raise ConsolidationDenied()
                decode_state(payload)
                rows_by_corpus.setdefault(corpus_digest, []).append(
                    (scope_digest, generation, payload)
                )
            for corpus_digest, target_scopes in owner_scope_keys.items():
                if not target_scopes:
                    continue
                authority = authority_by_digest.get(corpus_digest)
                if authority is None:
                    if rows_by_corpus.get(corpus_digest):
                        raise ConsolidationDenied()
                    if corpus_digest != self.source.corpus_digest:
                        connection.execute(
                            "INSERT INTO offline_consolidation_authorities VALUES (%s,1,%s)",
                            (
                                corpus_digest,
                                Jsonb(
                                    {
                                        "authority_id": str(uuid4()),
                                        "source": _fixture_state(
                                            fixtures[corpus_digest], forgotten=target_scopes
                                        ),
                                        "heads": {},
                                    }
                                ),
                            ),
                        )
                    continue
                revision, payload = authority
                if (
                    type(revision) is not int
                    or revision < 1
                    or type(payload) is not dict
                    or set(payload) != {"authority_id", "source", "heads"}
                    or type(payload["source"]) is not dict
                    or set(payload["source"]) != {"published", "epochs", "withdrawn", "forgotten"}
                    or type(payload["heads"]) is not dict
                ):
                    raise ConsolidationDenied()
                fixture = fixtures[corpus_digest]
                fixture._restore_source(payload["source"])
                expected_head_keys = {
                    digest([scope_key, generation])
                    for scope_key in fixture_scopes[corpus_digest]
                    for generation in generations_for_corpus(corpus_digest)
                }
                if (
                    not target_scopes <= set(payload["source"]["published"])
                    or not set(payload["heads"]) <= expected_head_keys
                    or any(
                        type(value) is not str
                        or len(value) != 64
                        or any(char not in "0123456789abcdef" for char in value)
                        for value in payload["heads"].values()
                    )
                ):
                    raise ConsolidationDenied()
                heads = dict(payload["heads"])
                for scope_digest, generation, checkpoint in rows_by_corpus.get(corpus_digest, ()):
                    head_key = digest([scope_digest, generation])
                    if heads.get(head_key) != digest(checkpoint):
                        raise ConsolidationDenied()
                for scope_digest in target_scopes:
                    for generation in generations_for_corpus(corpus_digest):
                        heads.pop(digest([scope_digest, generation]), None)
                source_state = dict(payload["source"])
                source_state["forgotten"] = sorted(set(source_state["forgotten"]) | target_scopes)
                updated_payload = {
                    **payload,
                    "source": source_state,
                    "heads": heads,
                }
                if corpus_digest == self.source.corpus_digest:
                    self.source._forgotten.update(target_scopes)
                    self.source._heads = heads
                else:
                    connection.execute(
                        "UPDATE offline_consolidation_authorities SET revision=%s,payload=%s "
                        "WHERE corpus_digest=%s",
                        (revision + 1, Jsonb(updated_payload), corpus_digest),
                    )
            connection.execute(
                "DELETE FROM offline_consolidation_checkpoints WHERE owner_id=%s", (owner_id,)
            )
