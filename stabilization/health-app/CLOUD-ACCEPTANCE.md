> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Health app cloud acceptance baseline

**Status:** not staging-accepted.
**Baseline revision:** `7fb84c76217c772b2bce6715744b8294afafa771` (`main`).

The repository’s [Cloud Run runbook](../../../health-app/infra/gcp/README.md) describes reviewable infrastructure, not a deployed environment. It intentionally requires owner-supplied GCP/Firebase/Neon/GCS identifiers, secret versions, image digest, connection budget, state bucket, and billing approval. No staging inputs, Terraform apply, image push, live cloud connection, or service call was made for this baseline.

## Current acceptance matrix

| Area | Repository intent/current implementation | Verified in this baseline | Acceptance state |
| --- | --- | --- | --- |
| CI/Terraform | Terraform 1.13.3 formatting, backend-disabled provider initialization/validation, and container build are CI gates. | The latest hosted run fails formatting at the baseline SHA; current working tree passes the pinned local formatter. Init/validate and image build did not run. Docker is unavailable. | **Local format fixed; hosted CI and remaining infra checks open.** |
| Cloud Run API | Public HTTPS ingress is intentional for Firebase mobile clients; domain APIs must validate Firebase ID tokens. `/healthz` is process liveness; `/readyz` checks only bounded DB readiness. | Static source/runbook review only. Local readiness timeout behavior exercised against disposable PostgreSQL; no Cloud Run behavior. | **Unverified live.** |
| Firebase identity | Cloud mode uses Firebase auth, verified owner mapping, revocation checks for applicable routes, and no client owner ID. | Source/tests and historical deterministic signed-token fixtures only. No live Firebase user/token/revocation call. | **Unverified live.** |
| Neon/PostgreSQL | Runtime uses pooled Neon URL with `sslmode=verify-full`; migration uses separate direct URL/job; online migrations use a DB advisory lock. | Latest CI’s service container is PostgreSQL 17. Local focused run used PostgreSQL 17.11. No Neon TLS, pooler, limit, migration job, or production concurrency evidence. | **Unverified live.** |
| GCS/private objects | GCS bucket is private with uniform access/public-access prevention; runtime and migration service accounts are split. | Terraform/runbook source review; local fakes and historical evidence only. No real bucket/IAM/object round trip. | **Unverified live.** |
| Migration and rollback | Migrations run in a separate job before immutable API deployment; rollback is API-only and forward-compatible. | CI did not pass through provider validation/image build; local focused test fixture applied the current migration head to disposable PostgreSQL. No cloud job, immutable digest, mixed-version rollout, or rollback. | **Partially locally exercised; release gate open.** |
| Backup/restore/deletion | Phase 9 stores a minimal erasure ledger marker; future restore must replay it before data becomes readable. | Evidence explicitly says no replay runner, isolated restore drill, encrypted portable backup, retention configuration, or measured RPO/RTO. | **Not accepted; P1.** |
| Logs/operations | Application logs are bounded/redacted; budgets, alerts, operational access, health checks, outage and reconnect behavior need environment validation. | Static review and historical unit evidence only. No Cloud Logging/Monitoring, cost/billing, quota, or live redaction validation. | **Unverified live.** |
| Mobile release | Firebase-configured native client must complete the owner journey against staging. | Latest CI predates current fixes and skipped mobile checks. Available pnpm 11.25.0 violates the repo's pnpm 9 requirement, so no current generated-client/mobile check ran. No native app build, device login, HealthKit, accessibility, or account-switch session in staging. | **Not accepted.** |

## Required promotion sequence after Gate 1

1. Supply and review an owner-approved staging input set, dedicated project/state/bucket, budget/alerts, least-privilege service accounts, secret IDs/versions, and Neon pooled/direct endpoints. Do not put secret values in shell history, Terraform variables, CI logs, or this handoff.
2. Pass current `terraform fmt -check -recursive infra/gcp`, backend-disabled init/validate with the pinned provider lock, and the CI API-image build at one reviewed SHA.
3. Build/push only through the documented script, pin an immutable digest, and deploy infrastructure with API serving disabled initially.
4. Execute the migration Cloud Run Job using the direct Neon URL; inspect the result and migration head before deploying the serving image.
5. Verify `/healthz` and `/readyz`, Firebase issuer/audience/owner mapping, pooled Neon TLS/reconnect/concurrency bounds, GCS IAM/object round trip, sanitized logs, and recovery from DB/provider outages.
6. Prove API-only rollback against an additive schema and capture Cloud Run revision, migration, connection, privacy, cost, and alert evidence.
7. Restore an encrypted backup to a disposable isolated branch/database, replay deletion fences, prove erased owners remain absent, and record measured RPO/RTO.
8. Run the staging mobile journey matrix with an approved synthetic test account. Keep broad Health↔Personal AI and narrow federation routes disabled until the shared identity and consent gates are independently accepted; do not enable Records upload without its full ingress safety boundary.

## Evidence limits and navigation

- Current Cloud Run infrastructure is a template; no deployed revision exists in the reviewed evidence.
- Phase 3’s Oct 4 Terraform local validation is historical. The Oct 12 GitHub run is newer and currently fails formatting before validate/build.
- PostgreSQL 17 CI and this local disposable PostgreSQL 17.11 run do not prove Neon pooler/TLS or production concurrency.
- Phase 9 local erasure tests do not prove that an old backup restore cannot resurrect deleted data.
- See Health’s [current state](../../../health-app/docs/current-state.md), [Phase 3 release evidence](../../../health-app/docs/implementation/evidence/phase-3-release.md), [Phase 9 release evidence](../../../health-app/docs/implementation/evidence/phase-9-release.md), and the [infra README](../../../health-app/infra/gcp/README.md) for the canonical details.

## Gate 1 infrastructure check — 2026-10-13

The exact CI-pinned Terraform 1.13.3 formatter now passes `terraform fmt -check -recursive infra/gcp`; the only infrastructure formatting change was in `infra/gcp/main.tf`. The binary came from the official HashiCorp release and its published SHA-256 was verified. Provider initialization/validation and the API image build have not run, so the hosted infrastructure gate remains open. No cloud resources or provider behavior were exercised.
