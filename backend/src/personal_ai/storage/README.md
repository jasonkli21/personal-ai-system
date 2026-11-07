# Storage boundary

`repositories.py` defines backend-neutral contracts for owner-scoped conversations and append-only branchable messages. `fake.py` supplies deterministic in-memory implementations for offline tests. Concrete persistence adapters and composition live in `personal_ai.persistence`.

## Current implementation

The active factory composes Postgres/pgvector repositories with DynamoDB timeline and runtime repositories. Local/test use explicit local Postgres and DynamoDB Local endpoints; deployed settings target Neon and federated AWS DynamoDB. Firestore adapters and migration tooling have been removed from runtime. See [ADR 0002](../../../../docs/decisions/0002-firestore-native-persistence.md) and [ADR 0021](../../../../docs/decisions/0021-polyglot-persistence-foundation.md).

## Correctness concerns

- Services depend on repository protocols, not SQL, DynamoDB clients, or concrete persistence adapters.
- Preserve owner/application/workspace scope and immediate list behavior required by existing contracts.
- Conversation turn preparation preserves active-branch selection, parent/supersedes provenance, and atomic conflict handling. Superseded messages remain stored.
- Cross-store changes preserve bounded guards, receipts, and recovery rules. Do not split a transactional correctness boundary to align broad data labels.
- Local DynamoDB does not establish real AWS capacity, IAM, index propagation, or strict-free behavior.

## Entry points and verification

Start with `repositories.py`, `fake.py`, and `personal_ai.persistence.factory`. Relevant checks live in `backend/tests/test_storage_repositories.py` and `backend/tests/persistence/`; use `make persistence-test` for the isolated local-engine integration suite when Docker is available. The [current state](../../../../docs/current-state.md) records native and external gates.
