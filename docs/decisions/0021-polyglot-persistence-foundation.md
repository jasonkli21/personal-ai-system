# ADR 0021: Polyglot persistence foundation

- Status: accepted; local runtime code cutover implemented; external acceptance remains open (status updated 2026-10-07)
- Date: 2026-10-06
- Reviewed repository revision: `e17ebd76afd1feb90fe47d959c43ab23eb553499`
- Supersedes: [ADR 0002](0002-firestore-native-persistence.md) for the target architecture after local storage cutover

## Context

The [local persistence guide](../local-persistence.md) is authoritative.
Adjacent completed work and prior design history remain intact. This decision changes persistence beneath existing contracts;
it does not deliver new product behavior or establish cloud readiness.

At the time this decision was reviewed, the repository named 34 Firestore
collections. Several transactions join records that broad labels such as
"events" or "idempotency" would otherwise assign to different stores. Store
selection must preserve those correctness boundaries and
owner/application/workspace isolation.

## Decision

1. DynamoDB owns conversations, branchable messages, working summaries,
   memory-lifecycle execution jobs and owner-wide fixed-window request counters.
   It also owns retained operational timeline families explicitly assigned by
   the [storage module README](../../backend/src/personal_ai/storage/README.md).
2. Postgres owns knowledge, memory embeddings/provenance/lifecycle effects,
   research, decisions, proposals, extraction results, account/control metadata
   and compact usage state. Research runs/sessions/replay keys stay together;
   knowledge lifecycle events/state/applied-operation receipts stay together.
3. GCS artifact bodies remain part of private-artifact handling; compact artifact metadata belongs
   in Postgres. Authoritative domain application state stays external.
4. Use one initial DynamoDB runtime table, no LSI, transactional base-table
   recent-conversation/catalog entries and one sparse job-publication GSI.
   Listings that preserve immediate visibility cannot depend on a GSI.
5. Use ordinary versioned Postgres migrations, typed columns/relations and
   bounded JSONB, behind existing or extended backend-neutral repositories.
6. Limit cross-store coordination to memory mutations whose current Firestore
   transaction validates chat sources or a lifecycle job. Reuse conversation/job
   records for bounded guards and a Postgres receipt for effect application.
   An unknown effect outcome cannot release guards until serialized recovery
   determines applied or aborted. No general saga engine, distributed
   transaction, mirrored job store or DynamoDB Streams is introduced.
7. Preserve original embedding values in one lossless `double precision[]`
   representation and cast to pgvector for exact search. Do not persist a second
   vector projection by default. This preserves stored-value compatibility while
   reducing storage relative to the earlier review's two-copy proposal. Query
   CPU and numerical boundary behavior must be measured before vector search. ANN/index
   acceleration requires explicit evaluation, not implicit migration changes.
8. Migrate through idempotent backfill, logical reconciliation, a bounded freeze
   of every writer and deletion-aware final delta. No permanent dual writes.
   Post-cutover rollback must preserve all new mutations; if reverse replay cannot
   do so, use forward repair.
9. Use local Postgres/pgvector and official DynamoDB Local for persistence
   integration. Keep Cloud Run/Pub/Sub/Google authentication; add only DynamoDB
   and its required AWS IAM/STS surface. Cloud activation requires current
   account/region/credential/network and strict-$0 verification.

## Consequences and alternatives

- There is exactly one canonical store per durable family. Execution checkpoints
  and knowledge-effect receipts are different families, connected by stable IDs.
- Independent "check source, then write memory" operations are rejected because
  a concurrent branch cut or lease replacement could authorize an obsolete effect.
  Keeping research transaction groups in Postgres avoids unnecessary coordination.
- GSI-only recent listings are rejected because eventual propagation would change
  existing immediate create/list behavior. Directories add bounded transactional
  writes and index metadata, not full authoritative copies.
- A single float32 pgvector column would save more bytes but cannot guarantee
  the existing lossless stored-vector read contract. Two stored representations
  preserve values but consume extra Neon storage without an initial index need.
  One lossless array plus a transient cast is the selected baseline; storage and
  compute must both fit strict-$0 limits. No silent truncation, half-precision
  conversion or re-embedding is authorized, including for 2,001–2,048 dimensions.
- Recovery can temporarily block a conversation/job when one store is unavailable.
  This is preferable to violating provenance or applying duplicate knowledge effects.
  Optional memory retains its existing advisory failure behavior for chat.
- Export consistency and deletion inventory span stores; this decision does not
  complete existing physical deletion, owner migration or deletion-aware restore.
- The local runtime no longer uses Firestore. If a Firestore dataset is
  later identified, treat it as a potential legacy source and follow the
  conditional inventory/cutover contract; no real data migration is claimed.
  Historical ADRs/evidence retain their original meaning.

## Implementation and verification references

Detailed keys, schema tradeoffs and the minimal recovery protocol belong in the
[storage module README](../../backend/src/personal_ai/storage/README.md).
Migration, local/cloud checks, rollback and retirement belong in the
[local persistence guide](../local-persistence.md).
At decision acceptance, these were planned requirements; no database, provider,
emulator or cloud checks were claimed by accepting the ADR, and later migration work had not
started. That is historical acceptance context; see the dated implementation
status below. The root README now reflects the locally implemented runtime.

## Implementation status update — 2026-10-07

The local database cutover switched normal API/worker wiring to Postgres/DynamoDB and removed
Firestore runtime and migration dependencies. This updates implementation
status only; it does not revise this decision's original acceptance date or
claim real data migration, live cloud cutover, target-engine verification, or
strict-$0 eligibility. See [current state](../current-state.md) and
[local persistence guide](../local-persistence.md).
