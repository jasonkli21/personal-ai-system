"""Reuse complete canonical retrieval results without invoking an embedding provider.

A host must supply current canonical retrieval evidence for the *same* universe.
The sealed fixture benchmark has no such real-vector issuer. Fake-vector evidence
can exercise the adapter only under an explicit contract-test opt-in.
"""

from hashlib import sha256
from math import isfinite
from typing import Literal

from pydantic import Field

from personal_ai.memory.contracts import embedding_space_for
from personal_ai.memory.research.contracts import ResearchFailure, Strict, digest


class CanonicalSemanticRanks(Strict):
    version: Literal["canonical-semantic-ranks-v1"] = "canonical-semantic-ranks-v1"
    origin: Literal["canonical", "fake_vector_contract"]
    generation: str = Field(pattern=r"^[0-9a-f]{64}$")
    query_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    query_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    embedding_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    universe: tuple[str, ...] = Field(max_length=128)
    ranking: tuple[str, ...] = Field(max_length=128)

    @classmethod
    def from_retrieval(cls, result, query, index, id_map, *, fake_vectors=False):
        trace = result.trace
        if (
            trace is None
            or not trace.complete
            or result.diagnostics
            or trace.query.scope != query.canonical.scope
            or trace.query.query_fingerprint != query.canonical.query_fingerprint
            or trace.query.embedding_space != query.canonical.embedding_space
            or trace.query.as_of != query.canonical.as_of
        ):
            raise ResearchFailure("unsupported", "semantic_evidence_incomplete")
        universe = tuple(e.record_id for e in index.entries)
        candidates = tuple(result.candidates)
        canonical_ids = {str(row.memory.id) for row in candidates}
        if (
            canonical_ids != set(id_map)
            or set(id_map.values()) != set(universe)
            or len(canonical_ids) != len(candidates)
            or len(id_map) != len(universe)
            or {str(t.memory_id) for t in trace.candidates if t.provenance_state == "eligible"}
            != canonical_ids
        ):
            raise ResearchFailure("unsupported", "semantic_universe_mismatch")
        entries = {e.record_id: e for e in index.entries}
        if any(
            not isfinite(row.similarity)
            or embedding_space_for(row.memory) != query.canonical.embedding_space
            or entries[id_map[str(row.memory.id)]].content_fingerprint
            != sha256(row.memory.content.encode()).hexdigest()
            or (row.memory.owner_id, row.memory.application_id, row.memory.workspace_id)
            != (
                query.canonical.scope.owner_id,
                query.canonical.scope.application_id,
                query.canonical.scope.workspace_id,
            )
            for row in candidates
        ):
            raise ResearchFailure("unsupported", "semantic_source_mismatch")
        # A provider label is part of the immutable space, never proof of real
        # embeddings. The caller must still carry independently issued evidence.
        if query.canonical.embedding_space.provider_id == "fake" and not fake_vectors:
            raise ResearchFailure("unsupported", "real_embeddings_unavailable")
        return cls(
            origin="fake_vector_contract" if fake_vectors else "canonical",
            generation=index.generation,
            query_identity=index.query_identity,
            query_fingerprint=query.canonical.query_fingerprint,
            embedding_identity=query.canonical.embedding_space.identity,
            universe=universe,
            ranking=tuple(
                id_map[str(row.memory.id)]
                for row in sorted(candidates, key=lambda row: (-row.similarity, str(row.memory.id)))
            ),
        )

    def validated(self, query, index, *, allow_fake=False):
        universe = tuple(e.record_id for e in index.entries)
        if self.origin == "fake_vector_contract" and not allow_fake:
            raise ResearchFailure("unsupported", "real_embeddings_unavailable")
        if (
            self.generation != index.generation
            or self.query_identity != index.query_identity
            or self.query_fingerprint != query.canonical.query_fingerprint
            or self.embedding_identity != query.canonical.embedding_space.identity
            or self.universe != universe
            or set(self.ranking) != set(universe)
            or len(self.ranking) != len(universe)
        ):
            raise ResearchFailure("unsupported", "semantic_universe_mismatch")
        return self.ranking

    @property
    def identity(self):
        return digest(self)
