> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Travel Gate 0 findings

Baseline inspected: `09584976d46c67c97a19c72d173b2ee88dbcb31c`; latest observed CI: [run 38286358285](https://github.com/jasonkli21/travel-app/actions/runs/38286358285).

| Priority | Finding and classification | Evidence and action |
| --- | --- | --- |
| P1 | Baseline CI is red: backend formatter, secrets scanner, and recovery smoke. | Ruff found two format-only changes. Detect-secrets found two `google_oauth_client_secret` values in tests; both are the literal synthetic fixture value and are not usable credentials. Both lines carry an inline allowlist. The baseline was refreshed only for four already-known findings whose code locations moved; all 29 stored fingerprints are unchanged and no new fingerprint was added. Recovery failure came from a hard-coded expected revision `0015` while the repository head is `0017`; the guard now derives the Alembic head and retains mismatch rejection. See [QA](QA.md). |
| P1 | The recovery smoke had a second fixture defect hidden behind the stale revision guard. | After deriving head, local execution reached `_seed_source` and failed because it tried to hard-link `<key>.tmp` from a nonexistent `<key>`. The link direction is corrected. Encrypted backup, verification, isolated restore, SQL/blob integrity, Alembic/ORM parity, application read/write probe, and JSON export then passed on synthetic PG17 databases at `0017`. This is local synthetic evidence, not RPO/RTO or deletion acceptance. |
| P1 | The current branch still has no green remote CI result. | Local format, mypy, all 334 backend tests, package build, and synthetic encrypted restore pass. No commit or push was made; the exact baseline workflow remains red until a new CI run proves the working tree on its supported runner. |
| P1 | Phase 9 deletion and hosted recovery gates remain open. | Owner-wide deletion and restore-time deletion fencing are not implemented. No approved RPO/RTO, retention, hosted object store, Cloud Run/Neon identity, or cloud restore evidence exists. Keep private attachments/imports disabled in hosted mode. |
| P2 | Some tests pinned prior behavior/revisions rather than current accepted semantics. | The route-family test expected authentication `401` on a default-off Personal AI context route; middleware intentionally hides that route with `404`. The migration rollback test expected `0015` after an aborted transaction despite starting at `0017`; it now asserts the original starting revision. |
| P2 | Large handwritten modules and tests deserve later maintainability review. | The largest source/test files are inventoried in [CODE-QUALITY.md](CODE-QUALITY.md). This Gate 1 pass did not refactor them; broad decomposition is not needed to restore the baseline and would require separate behavioral review. |

The attached audit is a useful backlog reference, but its backend `travel_api` paths are stale; the package is `personal_travel`. Its formatter file list also differs from the actual CI log: the files flagged by run `38286358285` were the Personal AI context route and its test. The latest run was inspected directly through workflow job status and decoded logs rather than inferred from the audit.

## Security-scanner disposition

The scanner’s two current findings were on test configuration arguments named `google_oauth_client_secret`; both values are explicitly synthetic fixtures. No credential was printed or copied into a baseline. The source lines use the scanner’s `pragma: allowlist secret` for those two fixture values. The baseline update retains exactly the original 29 fingerprints; four existing findings have corrected line numbers (`config.py` 45→48, `test_auth_sessions_postgres.py` 40→42, `test_personal_ai_client.py` 132→223, and `test_review_migrations.py` 210→216). Each updated entry matched an existing fingerprint. No new fingerprint was added.
