# GCP deployment

## Runtime architecture

```text
Browser
  |
  v
Cloud Run: public personal-ai-web (Next.js; Google sign-in shell)
  |  server-side /api proxy; web service identity plus end-user ID token
  v
Cloud Run: private personal-ai-api (FastAPI)
  |-- TLS transaction pooler --> Neon Postgres + pgvector
  |-- Google OIDC token -> AWS STS -> DynamoDB
  |-- hosted model/search providers
  '-- Pub/Sub --> private personal-ai-worker (bounded memory lifecycle jobs)
```

Neon/Postgres owns query-rich records, memories and vectors, research and
decision aggregates, account controls, and provider throttles. DynamoDB owns
conversations, messages, summaries, lifecycle job/guard state, and idempotency
records. Cloud Run, Pub/Sub, Google end-user authentication, and Secret Manager
remain on GCP. The application has no Firestore runtime path or migration
command.

P10.6 runtime wiring and Firestore dependency removal are implemented locally.
The user reports that Firestore was never deployed and no source data exists;
no cloud-account inventory independently verified that report, and no data
migration occurred. See the [P10.6 evidence](personal-ai-chapter-2/phase-10-p10.6-implementation-evidence.md)
for code checks, skipped target-engine/cloud checks, and remaining release gaps.

## Static preflight

Run `make cloud-plan-check` for the checked-in synthetic manifest. Use a local
proposal and approved baseline for a redacted review of policy and drift.
The [deployment runbook](platform-independence/pi-7-operations-runbook.md#static-cloud-plan)
describes the profile, identity, ingress, IAM, storage and cost requirements.

The current `deploy.sh` entrypoint runs the static planner. It refuses
`apply` and the predecessor positional deployment command. The historical
script remains in the parent revision for audit. A separately authorized
deployer must bind the reviewed plan to live IAM, network and resource state,
verify image provenance and secret version references, and apply scoped
changes with a rehearsed rollback. Hosted and production operations remain
blocked.

Use the [DynamoDB template](../infrastructure/aws/dynamodb/dynamodb-cloudformation.yaml),
[Google-to-AWS trust template](../infrastructure/aws/identity/aws-google-oidc-trust-policy.json.tmpl)
and [runtime policy](../infrastructure/aws/dynamodb/dynamodb-runtime-policy.json.tmpl)
as topology references. Schema/bootstrap permissions and runtime access are
separate. Secret references must pin numeric versions. Store the values in the
authorized secret service.

## Local and release verification

For local application use, configure `backend/.env` from
[`backend/.env.example`](../backend/.env.example), then run:

```bash
make persistence-up
make persistence-bootstrap
```

This starts local Postgres/pgvector and DynamoDB Local. Run `make persistence-test-up`
and `make persistence-test` for the isolated integration stack when Docker is
available. `make persistence-clean` is destructive to local persistence volumes.

After a deployment, use the [identity controls release checklist](phase-9-release-checklist.md)
for authentication, safeguards, and account workflows, and the
[persistence boundary migration/cutover verification plan](personal-ai-chapter-2/phase-10-migration-cutover-and-verification-plan.md)
for target-store persistence, recovery, IAM, and release evidence. The conversation API
deployment checklist is a historical Firestore procedure and must not be used
for current deployments. A successful `/api/health` response confirms only
server-side web-to-API reachability; it does not exercise either database or
the model.

Cloud Run can scale to zero, but that does not establish a zero-cost deployment.
Review current account-specific Neon plan limits, DynamoDB table/GSI capacity,
cross-cloud egress, GCP quotas, external providers, and model usage. The
[strict-$0 validator](../infrastructure/policy/strict_zero/strict_zero_release_gate.py)
needs current reviewed evidence; fake/unit tests and local DynamoDB do not prove
cloud IAM, production capacity, GSI behavior, or free-tier eligibility.

## Security boundary

The public web service exposes the sign-in shell. The API is private to the web
runtime service account and separately validates the end-user Google ID token.
Development `local` identity is allowed only in local/test configurations.
Cloud Run IAM and application identity are separate checks. Google-to-AWS
federation must bind the exact configured audience and runtime service-account
subject. Production remains blocked until staged identity, database, provider,
recovery, export/deletion, cost, and operational release checks have evidence.

Earlier phase guides and Firestore ADRs are historical records of the prior
implementation; they are not current deployment instructions.
