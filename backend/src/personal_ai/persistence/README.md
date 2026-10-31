# Persistence adapters

This package owns concrete database clients, repositories, migrations, and store composition.
Backend-neutral repository protocols and storage errors remain in `personal_ai.storage`.

## Entry points and boundaries

- Migration 027 reconstructs memory lifecycle validity epochs from immutable events. Canonical originals and derived source edges remain in the existing memory tables; there is no new memory store or vector index.

- `postgres/research_experiments.py` and migration 026 own bounded immutable paired research evaluation summaries. Dispatch/admission stays in P19, snippet/evidence source facts stay in research sessions, and optional bulky numeric batches stay in P20. Account export and scheduled expiry include the new family.

- `postgres/federation.py` owns current federation grant heads, immutable revisions, safe selection audits through existing audit events, and fenced grant cleanup; migration 024 adds the relational grant tables. Runtime/history/artifacts retain typed dependencies, not grant authority.
- `postgres/mutations.py` owns Phase 31 proposal heads and immutable revision audit in one transactional aggregate (migration 025), including CAS execution/reconciliation reservations, scoped reads, export inventory and fenced purge. Domain state and deduplication receipts remain external.
- `factory.py` composes the configured Postgres/Neon and DynamoDB repositories.
- `postgres/` owns Postgres connections, migrations, and Postgres-backed repositories.
- `dynamodb/` owns DynamoDB clients and the conversation, message, summary, trace, job, and usage adapters.
- `postgres/neon.py` provides the direct Neon database adapter used by deployment tooling.
- Postgres and DynamoDB implementations are imported from their semantic packages.

Repository adapters may coordinate multiple writes inside one transaction when their contract requires it. Do not move commit boundaries to match file boundaries. The tests live under `backend/tests/persistence/` and in repository-specific backend test modules.

## MEM-2 migration and operator notes

Migration 030 adds only actor-scoped pending proposals and content-free operation
receipts under the existing Postgres memory owner. Migration 031 adds the global
expiry index used by bounded idle cleanup and backfills stable project IDs onto
legacy receipts where their target rows remain. These follow 027–029 without
rewriting earlier migrations, schema-3 records or lifecycle history. The control
repository locks owner fence → existing knowledge namespace → actor namespace,
then applies canonical lifecycle event/projection plus receipt in one transaction.
Queue review and receipt also share a transaction. User actors are rejected by raw
lifecycle `apply_event`; the narrow control transaction is the only user-write seam.

Rollback disables the three MEM-2 flags and the frontend management gate. Do not
roll back migrations 030/031, undo forget, prune source fences or recycle receipt keys.
TTL hides expired proposals; the bounded scheduled-maintenance pass and later writes
erase expired content. An operator performing account erasure must retain
the owner fence and invoke `PostgresControlRepository.erase_owner(owner_id)` for
both control tables in every scope; it refuses an unfenced owner. Account inventory
and export cover both tables. This is a local SQL erasure seam, not proof of cloud
physical deletion, backups, recovery or a complete account-erasure workflow.

## PI-4 profile consent

Migration 032 adds `profile_consents`, a bounded owner aggregate in the existing
Postgres payload-family inventory, distinct from the unchanged profile schema.
It archives legacy share arrays without granting permission, clears active arrays
and rejects old allowlist writers with a SQL constraint. Consent/profile mutation
locks owner deletion authority -> consent -> profile. At most 32 lifetime grants
and 64 retained operation receipts fit a 128 KiB payload; no replay-key pruning.
Value updates invalidate every grant bound to the prior profile revision.

`PostgresGlobalProfileRepository.purge_owner` is an explicit local operator erasure
seam for both tables and requires a retained owner deletion fence. Exports include
the consent/archive/receipt payload. Deployed physical deletion, backups/replicas,
restore anti-rollback and automatic erasure remain separate gates. Drain old
readers before migration/enablement; rollback keeps strict readers and migration,
and disables `PROFILE_SHARING_ENABLED` for selection **and** persisted dependency
reuse. See [API/operations](../../../../docs/platform-independence/profile-sharing-v1.md).
