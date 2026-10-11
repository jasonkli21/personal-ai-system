# Persistence adapters

This package owns concrete database clients, repositories, migrations, and store composition.
Backend-neutral repository protocols and storage errors remain in `personal_ai.storage`.

## Entry points and boundaries

- `factory.py` composes the configured Postgres/Neon and DynamoDB repositories.
- `postgres/` owns Postgres connections, migrations, and Postgres-backed repositories.
- `dynamodb/` owns DynamoDB clients and the conversation, message, summary, trace, job, and usage adapters.
- `neon.py` provides the direct Neon database adapter used by deployment tooling.
- The former flat module paths remain compatibility shims; new imports should use the semantic packages.

Repository adapters may coordinate multiple writes inside one transaction when their contract requires it. Do not move commit boundaries to match file boundaries. The tests live under `backend/tests/persistence/` and in repository-specific backend test modules.
