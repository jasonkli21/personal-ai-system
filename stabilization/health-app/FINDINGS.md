> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Health app Gate 0 findings

**Baseline:** `7fb84c76217c772b2bce6715744b8294afafa771` (`main`).
**Reviewed:** attached Health audit dated 2026-10-13, repository instructions/router/current-state, workflow and run logs, focused test sources, migrations/models, cloud runbook, and Phase 29/30/9 evidence. The table below records baseline findings; final local working-tree results follow it.

## Reconciled P0 findings

| Finding | Reconciliation against current evidence | Classification | Next action |
| --- | --- | --- | --- |
| CI has six PostgreSQL API failures | Confirmed by baseline run 38286355765: two readiness cases and four context/federation DB cases listed above. | Resolved in the uncommitted working tree; full PostgreSQL 17.11 SCRAM suite passes 272/272. Hosted verification pending. | Run the full workflow at a reviewed source revision. |
| Readiness recovery failures may be due to redacted SQLAlchemy URL | Confirmed as test setup: `str(postgres_engine.url)` masks the password as `***`; the fail-closed/timeout/recovery assertions remain intact. | Resolved locally by accepting/passing the original SQLAlchemy `URL`. | No separate code action; retain the regression tests. |
| Four context DB cases fail on provider identity FK | Confirmed as fixture ordering: `_seed_owner()` added the child and parent before one flush, while the real FK remained enforced. | Resolved locally by flushing `User` before `ProviderIdentity`; no owner auto-creation or constraint weakening. | No separate code action; retain the FK and tests. |
| Terraform formatting fails | Confirmed by the baseline run: `terraform fmt -check -recursive infra/gcp` named only `infra/gcp/main.tf`; Terraform validate and image build were skipped. | `infra/gcp/main.tf` now passes the pinned Terraform 1.13.3 formatter locally. Hosted infra job remains unverified. | Run Terraform init/validate and image build in CI or an equivalent environment. |

### Focused reproduction evidence

The local machine initially had no `TEST_DATABASE_URL` and no listener on port 5432, so the two focused calls skipped 2 readiness DB tests and 4 context DB tests. An isolated temporary PostgreSQL 17.11 cluster was then created on `127.0.0.1:55432`; the repository fixture applied Alembic to head. A first run under trust auth showed that the readiness regression is auth-mode sensitive. The cluster was switched to SCRAM, matching CI’s password-auth condition, and the precise readiness tests were rerun.

- Context DB file: 4 PostgreSQL cases failed with `provider_identities_user_id_fkey`; its one non-database test passed. This was in the combined 11-item run.
- Readiness focused selection under SCRAM: 2 failed, 4 deselected. The first failed with `password authentication failed for user "health"` when the test opened the reconstructed engine; the second returned expected 503 for the injected slow query and then failed recovery with `assert 503 == 200`.
- Initial no-DB context run: 1 passed, 4 skipped with the fixture’s explicit “PostgreSQL integration tests require TEST_DATABASE_URL” reason. This is not DB evidence.

The baseline runner did not change Health source. Temporary DB setup was isolated under `/private/tmp` and is cleaned up after the report is written.

## Audit disposition

| Audit statement | Status | Current evidence |
| --- | --- | --- |
| The latest `main` CI is red with six PostgreSQL test failures and Terraform formatting failure. | **Confirmed** | Latest run is at the exact local HEAD. API: 265 passed/6 failed. Infra: `infra/gcp/main.tf` fmt failure. |
| Readiness recovery tests need reproduction before production changes. | **Reproduced and narrowed** | Both fail only when the reconstructed engine must authenticate; the injected failure still produces sanitized 503 and returns the checked-out connection. No production change is indicated by current evidence. |
| Four Personal AI context/federation DB tests fail around owner/provider identity persistence. | **Confirmed; setup cause localized** | All four fail before the assertions at the helper flush; FK remains enforced. |
| Broad Health↔Personal AI auth is inconsistent. | **Still applies, with a newer narrow path** | Current state says broad Health requires a recent Firebase ID token, while Personal AI currently has Google OIDC. Phase 30 adds a short-lived signed Google identity assertion for a separate narrow export, but the export is default-off and end-to-end deployed identity is unverified. |
| Backup/restore/deletion replay is unproven. | **Confirmed** | Phase 9 retains only an erasure ledger marker and explicitly says no restore-replay runner exists; live backup/restore and RPO/RTO remain open. |
| Document upload is intentionally disabled. | **Confirmed and preserve** | Current state/Phase 9 state no ingress or record routes; malware scanning, isolated parsing, retention, provenance, review, and deletion semantics remain unresolved. |
| Device, cloud, and major journeys remain open. | **Confirmed** | Current-state and phase evidence distinguish local implementation from device/cloud acceptance. Latest CI did not reach frontend checks. |

## Cross-repository risks

- Keep Health as canonical owner for health records, consent, validation, revisions, and writes. Personal AI must not receive Health database credentials or become a second health store.
- Broad context read and narrow federation export have different contracts, identity requirements, and feature gates. Do not treat the Phase 30 signed assertion as approval to enable either route by default.
- Health has a narrow ergonomic-constraint-to-Shopping federation export, but there is no accepted Health → Personal AI → Shopping typed-task path demonstrated here. Shared destination task transport, delegated-user semantics, idempotency, timeout, and version handling remain suite-level decisions.
- Health privacy, freshness, consent, destination binding, and revocation semantics need to remain explicit in any shared envelope; a local adapter must not paper over a shared identity gap.

## Gate 1 local result — 2026-10-13

The complete API suite ran against the owned synthetic PostgreSQL 17.11 SCRAM cluster at `127.0.0.1:55432`: **272 passed, 1 warning**. The working tree also passes CI-scoped Ruff lint/format, strict mypy (70 source files), scaffold verification, and Terraform 1.13.3 formatting. The two projection/test-order issues exposed by the initial SCRAM run were fixed and covered by tests. Ruff's 9 import-order findings and 11 formatting files were corrected. The three mypy errors were narrowed away: the Firebase UID is captured and type-checked before return, and the federation schema constant retains its literal type with `Final`.

The fixes and check commands are recorded in [STATUS.md](STATUS.md) and [QA.md](QA.md). The latest hosted run is still the baseline run 38286355765; it predates these uncommitted changes. pnpm 9.15.0/mobile/generated-client checks, Terraform init/validate, Docker image build, cloud/provider/device, and restore acceptance remain open.
