# Research, evidence, and decisions

The research service runs a bounded search over configured sources and records
expiring observations with citations. A research session preserves queries,
attempts, selected evidence, and the answer under owner scope. It does not make
domain records authoritative or turn observations into durable memory.

Decision support accepts validated candidate proposals and attributed evidence.
It verifies ownership, source, excerpt fingerprints, and freshness; resolves
entities conservatively; applies hard constraints before preference ranking;
and stores a decision snapshot with cited results. Decisions do not initiate
searches.

Iterative research is an opt-in bounded workflow. It identifies an evidence gap,
issues a focused follow-up, reuses the same evidence and decision services, and
stops under an immutable budget. It remains separate from the single-pass
default and does not run in the background. See the [iterative research design](decisions/0016-bounded-iterative-research.md).

## Boundaries

- Search adapters return source-native results; they do not choose a
  recommendation.
- Evidence retains source identity, observation time, expiry, and citation
  dependencies.
- Entity resolution requires stable identifiers or sufficiently supported
  fresh attributes. Name similarity alone cannot select an entity.
- Application code evaluates executable constraints before ranking eligible
  candidates.
- Presentation uses persisted results and source links; it does not add
  model-written factual claims.
- Memory-derived preferences are not part of decision ranking.

Domain applications keep authoritative records and rules. They may validate and
use attributed research candidates, but the shared service does not own their
editable itineraries, purchases, or other domain state.
