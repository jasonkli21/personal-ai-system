# PI-7 storage operations decision

Retain PostgreSQL/pgvector and DynamoDB. Use the credential-free profile for
core and consumer testing and reserve the native topology for disposable
integration and separately approved recovery drills.

| Topology | Correctness and recovery | Operational implications |
| --- | --- | --- |
| Existing split, local PG/pgvector and DynamoDB Local or hosted Neon and DynamoDB | Keeps tested relational locks, vectors, migrations and P19 quota transactions, plus DynamoDB keys, conditional writes, idempotency and job adapters. Coordinated recovery needs independently retained source and receipt authority across stores. | Two stores to bootstrap, observe and recover. Hosted adds OIDC federation, role drift, pooler behavior, cloud egress and separate billing. Native integration is portable through the existing Compose profile. |
| In-memory offline core and synthetic host | Reuses live API composition and contracts with injected stores. State and authorizations are ephemeral. | Small setup and no provider credentials. Suitable for deterministic smoke and regression. Cannot substitute for native transactions, data durability or recovery. |
| Consolidate on PostgreSQL/pgvector | Could reduce cross-store recovery coordination. Requires a replacement for Dynamo access patterns, conditional semantics, replay keys, guards, job state, migration backfill and restore evidence. | A single engine reduces some maintenance and network hops. Query contention, retained receipt capacity, operational cost and failover need measurement. |
| Consolidate on DynamoDB or a single-host store | Loses the current vector, relational transaction and query boundaries or requires new implementations of them. Single-host authority adds rollback and multi-worker constraints. | Operational simplicity depends on a significant migration, compatibility validation and a different recovery model. |

The installed smoke measures only synthetic startup samples and zero remote
provider dispatches under its fence. Cloud, database storage, request,
cross-cloud transfer, backup and operational costs were unobserved. Scale
to zero and a free tier describe possible cost behavior. Use reviewed
account-specific quotas, restore size, retention and traffic measurements
before making a spend or topology claim. See the
[strict-$0 evidence gate](../../infrastructure/policy/strict_zero/strict_zero_release_gate.py).

A separate migration decision would need measured workloads, a backfill and
reconciliation plan, original-key preservation, a safe cutover and rollback,
and native evidence of source and effect fencing across restart and restore.
