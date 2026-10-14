> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Finance cloud acceptance baseline

Date: 2026-10-13
Baseline SHA: `495c21186b68215bf110ab6ab3115cd67190cc67`
Status: **Prepared tooling; no cloud deployment accepted.**

Finance documentation describes a Firebase Hosting SPA with same-origin `/api` proxy to a Cloud Run API, Neon PostgreSQL, private GCS storage, and bounded Cloud Run job workers. The Stage 4 configuration, runbooks, and recovery tooling exist. Current state and release evidence say no GCP resources, Firebase deployment, Neon branch, or GCS resource was created. Local fakes/offline checks do not establish cloud behavior.

## Acceptance sequence

1. Restore green CI on an immutable candidate SHA. Preserve its generated API/client checks.
2. Create an isolated staging GCP/Firebase environment and Neon branch; record project/region/branch references without credentials.
3. Configure service identities, Secret Manager, Artifact Registry, private GCS, and distinct pooled runtime versus direct migration database URLs.
4. Run Alembic migration against the actual Neon branch before traffic; record revision, duration, TLS verification, pool settings, reconnect, concurrency, and rollback behavior.
5. Deploy the API by immutable image digest and the SPA with Firebase `/api` routing. Verify HTTPS/OIDC/PKCE, server-managed session cookies, CSRF/origin checks, and that direct unauthenticated Cloud Run access is denied.
6. Seed synthetic data only. Exercise portfolio, planning, transaction review, research, and the default-off Finance context endpoint through the hosted path.
7. Verify private object access: anonymous denial, authorized preview, size/type bounds, and deletion behavior. Do not publish object URLs.
8. Exercise bounded worker lease/retry/restart/cancel paths with DB reconnect and ensure idempotency after interruption.
9. Export encrypted backups and perform an isolated restore of both Neon data and GCS objects. Record achieved recovery objectives and a rollback rehearsal.
10. Confirm structured logs redact finance values/tokens, alerts and quotas are active, and actual cost/limit assumptions are documented.

## Evidence required to pass

- Candidate commit SHA and green workflow links; deploy image digest and hosting release identity.
- Sanitized migration, TLS, connection-pool, reconnect, concurrency, and migration rollback evidence from real Neon.
- Hosted identity/session/authorization checks including negative cases and owner isolation.
- GCS IAM/privacy/deletion evidence and Cloud Run worker failure/retry results.
- Backup artifact metadata, disposable restore results, recovery time/data-loss measurements, and operator runbook record.
- Observability, alert, quota, cost, and rollback evidence tied to the staging environment.

No acceptance artifact for these live controls was present in Finance `docs/stage-4-release.md`, `docs/current-state.md`, or `docs/gcp-neon-migration.md` at the baseline. Do not report staging, provider, or production readiness until the above evidence is captured. See Finance `docs/06-security-and-deployment.md`, `docs/adr/0002-gcp-neon.md`, `docs/07-postgres-neon.md`, and Stage 4 operations/recovery runbooks for the canonical guardrails.
