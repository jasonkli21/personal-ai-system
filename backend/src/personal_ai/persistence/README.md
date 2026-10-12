# Persistence adapters

This package owns concrete database clients, repositories, migrations, and store composition.
Backend-neutral repository protocols and storage errors remain in `personal_ai.storage`.

## Entry points and boundaries

- `postgres/research_experiments.py` and migration 026 own bounded immutable paired research evaluation summaries. Dispatch/admission stays in P19, snippet/evidence source facts stay in research sessions, and optional bulky numeric batches stay in P20. Account export and scheduled expiry include the new family.

- `postgres/federation.py` owns current federation grant heads, immutable revisions, safe selection audits through existing audit events, and fenced grant cleanup; migration 024 adds the relational grant tables. Runtime/history/artifacts retain typed dependencies, not grant authority.
- `postgres/mutations.py` owns Phase 31 proposal heads and immutable revision audit in one transactional aggregate (migration 025), including CAS execution/reconciliation reservations, scoped reads, export inventory and fenced purge. Domain state and deduplication receipts remain external.
- `factory.py` composes the configured Postgres/Neon and DynamoDB repositories.
- `postgres/` owns Postgres connections, migrations, and Postgres-backed repositories.
- `dynamodb/` owns DynamoDB clients and the conversation, message, summary, trace, job, and usage adapters.
- `postgres/neon.py` provides the direct Neon database adapter used by deployment tooling.
- Postgres and DynamoDB implementations are imported from their semantic packages.

Repository adapters may coordinate multiple writes inside one transaction when their contract requires it. Do not move commit boundaries to match file boundaries. The tests live under `backend/tests/persistence/` and in repository-specific backend test modules.
