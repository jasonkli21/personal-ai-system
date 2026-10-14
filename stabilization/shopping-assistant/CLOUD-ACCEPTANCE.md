> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Cloud acceptance boundary

Date: 2026-10-13. Baseline revision: `2268b944ffa8fe5c2e6f2787c88dea616160e398`.

## Status

Cloud staging and production are unverified; Phase 9 is not accepted, and the runbook does not authorize deployment until its release gates are met. No cloud resources were changed in this baseline. Local deployment scripts, container configuration, and documentation prove tooling exists, not that identity, database, providers, recovery, or hosted behavior works.

The current main CI run is red. Container build succeeds, but its smoke step invokes Alembic from `/tmp` without the packaged `/app/apps/api/alembic.ini` config and fails with “No 'script_location' key found.” Resolve the main CI failures before using a release candidate. This CI smoke does not substitute for a hosted migration or deployment check.

Gate 1 now updates the smoke invocation to use `/app/apps/api/alembic.ini`. The Dockerfile copy places the file at that path, and a local PostgreSQL 17 check successfully ran the explicit-config Alembic upgrade and drift check from `/tmp`. Docker is unavailable here, so the actual image smoke and a hosted CI rerun remain open; no cloud deployment or cloud acceptance was performed.

## Identity and integration limits

- Local development uses a fixed Shopping owner and is not a deployed identity.
- Cloud API access requires a verified Firebase token and an allowlisted UID mapped to the stable local owner. This is a single-owner deployment mapping, not multi-tenant authorization.
- The Personal AI context endpoint separately verifies Google service and user identity, exact audiences and configured identities, and the Shopping application scope. It is read-only, requires an explicit mapping reference, and defaults off in both systems.
- Shopping's external generation mode selects an unavailable client and makes no network call. There is no accepted typed-task destination path, delegated-user grant envelope in queued jobs, or cross-app idempotency/result lifecycle.
- Shopping remains authoritative for projects, requirements, catalog, research/evidence, decisions, and preferences. A future task host must invoke Shopping's domain command/application layer and preserve its authorization, revision, validation, and idempotency rules.

These boundaries mean a green container or enabled context read cannot be represented as Finance/Travel/Health task execution.

## Required acceptance evidence

1. Verify the Gate 1 repair diff in hosted CI, including CI Node 20, the DB contract suite, discovery retry/corrupt-state behavior, and the actual image smoke. Local checks now pass: 129 PostgreSQL tests, 69 frontend tests, and the explicit-config Alembic run from `/tmp`; these do not establish hosted CI or container-image success.
2. Close predecessor phase gates. Phase 6 needs PostgreSQL migration/model/concurrency evidence and manual browser/visual review. Phase 7 needs real multi-instance leases, hard termination/restart, cancellation/idempotency, mixed-revision and provider-timeout checks. Phase 8 needs preference lifecycle and first-use concurrency behavior. Phase 9 cannot imply these gates passed.
3. Record the staging identity and owner binding; verify Firebase login/logout, expired/revoked token handling, and foreign UID denial for every private resource type.
4. Verify Cloud Run ingress/IAM/service identity, immutable image revision, runtime secrets, CORS/origin, bounded instances/concurrency/timeouts, Neon pooled runtime and direct migration connections, quota/cost alerts, and online Alembic upgrade/check.
5. Exercise the hosted shopping journey, authenticated streaming/reconnect, provider partial failure, cancellation, cross-request replay, process restarts and stale-worker fencing, export/purge, log redaction, and SSRF limits.
6. Restore a protected backup into a disposable database, apply migrations, compare integrity/provenance counts, and complete a restored project journey. Record measured restore time and recovery point.
7. Keep the Personal AI typed-task destination separately gated until shared delegated identity, contract/version authority, destination capability, task idempotency/result semantics, and Shopping authorization are implemented and tested end to end.

Follow the [Shopping deployment runbook](../../../shopping-assistant/docs/deployment/runbook.md), [Phase 9 plan](../../../shopping-assistant/docs/planning/phase-9-implementation-plan.md), and [Phase 9 verification record](../../../shopping-assistant/docs/deployment/phase-9-verification.md). Record each check as passed, failed, or not run against its actual environment; local fakes and CI fixtures do not establish hosted acceptance.
