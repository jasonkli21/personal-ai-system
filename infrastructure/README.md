# Infrastructure

Deployment and local-environment definitions belong here. Keep provider-specific configuration isolated from application code.

- `gcp/` for Cloud Run, Pub/Sub, Secret Manager, and release deployment.
- `aws/dynamodb/` for table infrastructure, capacity policies, and static config validation.
- `aws/identity/` for AWS workload identity trust policy templates.
- `neon/` for Postgres role grants.
- `policy/strict_zero/` for strict-$0 release evidence validation.
- `../docker-compose.persistence.yml` for local Postgres/pgvector and DynamoDB
  Local. Firestore emulator/index assets are retired from the active setup.
