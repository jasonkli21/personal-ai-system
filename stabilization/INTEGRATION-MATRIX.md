# Integration matrix — 2026-10-14

| Path/case | Local executable coverage | External acceptance |
| --- | --- | --- |
| Finance → PAI → Shopping | Native budget source, opaque choice, immutable command, validation/confirmation, budget write and original status | Real OIDC/IAM, linked account and rendered browser |
| Travel → PAI → Shopping | Native trip consent/revision, destination/dates note, shared task lifecycle; all-five HTTPS case | Hosted identity, source lifecycle and rendered browser |
| Health → PAI → Shopping | Native ergonomic consent/revision, existing Firebase/Google link, minimized note; all-five HTTPS case | Actual linkage/revocation, IAM and native device |
| Identity/contracts | Wrong issuer, audience, signing key/kid, subject, destination, workspace, expiry, stale auth and unsupported command | Real certificate/key rotation and deployed revocation |
| Current linked owner | Unlinked provider, disabled user and revoked/unknown revocation epoch deny before effect | Actual SDK/IAM and multi-instance behavior |
| Grant/source/target | Consent/grant/source/target revision rejection; grant revoked after reservation rejected by receiver callback | Deployed membership and immutable policy obligations |
| Duplicate/uncertainty | Exact replay, lost ack after commit, unavailable destination, one effect/receipt, original-key observation without resend | Process kill/restart and real deployed network failure |
| Source restart recovery | Original confirmation ID recovered from server status | Browser storage/session restart |
| Retirement/rollback | Known exact receipt observation; unknown retired contract refuses writes; populated recovery-table rollback refuses | Mixed deployed versions and drain rehearsal |
| Domain privacy/recovery | Shopping inventory/fence; Finance local recovery; Travel age/SQL/blob restore with current marker replay; Health isolated marker replay | Cloud backups/exports, retention and approved RPO/RTO |

Run `stabilization/scripts/run_native_tests.py tasks` with an explicitly owned
loopback admin DSN. It applies real domain migrations and PAI schema, creates
synthetic canonical records, and starts five ephemeral TLS/Uvicorn listeners for
HTTPS cases. Other cases use explicit in-process transports. Setup lives in
`tests/task_harness.py`, source hosts in `tests/source_hosts.py`, TLS in
`tests/loopback_https.py`, and behavior cases in `tests/test_suite_tasks.py`.
Finalizers close resources even when construction/assertions fail; the runner
drops only its own UUID test database.

Google tokens, Firebase verification/certificate lookups and linked SDK records
are fake. Signatures, request binding, HTTPS verification, handlers, grants,
PostgreSQL transactions and receipts are real. This is not cloud, real identity,
provider, browser/device or process-crash acceptance. Exact final counts/source
identities are in [verification](VERIFICATION.md).
