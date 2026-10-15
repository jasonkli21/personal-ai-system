# Local suite and staging operations — 2026-10-14

Use synthetic data and disposable storage. Preserve user files, application
databases, private stores and credentials. Test runners require loopback admin
URIs and create/drop only their own UUID suite_*_test databases.

## Reproduce local all-five integration

Prerequisites: five sibling checkouts and locked environments, PostgreSQL 17 with
pgvector, a dedicated CREATEDB test role and the integration environment. This
run used `/tmp/suite-task-integration-venv` (Python 3.12, PAI locked dependencies and
the domains' resolved dependencies). Restricted sandboxes need loopback sockets.
No provider key or personal login is needed.

From the PAI checkout:

```sh
backend/.venv/bin/python backend/scripts/sync_task_contracts.py --check
backend/.venv/bin/python stabilization/scripts/run_native_tests.py tasks \
  --admin-dsn postgresql://suite_stabilization@127.0.0.1:55439/postgres \
  --log /tmp/suite-task-matrix.log
```

Port 55439 and role suite_stabilization describe this patch's owned cluster;
create a fresh isolated cluster after it is stopped. Never attach to a personal
cluster. Replace tasks with personal-ai/finance/shopping/travel/health for native
checks. The runner overrides domain DB/storage settings; Shopping's runtime URI
is a separate synthetic URI, retaining its destructive-test refusal. Finance
imports, generators and direct checks always need an explicitly synthetic
PRIVATE_FILE_DIR. Skipped DynamoDB/provider/account tests remain unaccepted.

For actual encrypted Travel recovery, put compatible age and PostgreSQL tools on
PATH, then run:

```sh
backend/.venv/bin/python stabilization/scripts/run_travel_recovery.py \
  --admin-dsn postgresql://suite_stabilization@127.0.0.1:55439/postgres \
  --log /tmp/travel-recovery.log
```

The runner owns two UUID DBs, migrates/seeds, encrypts SQL/private bytes, validates
schema/hashes, replays a deletion requested after backup, checks pending-upload
recovery/export and drops those DBs. Synthetic keys/private stores are temporary.
For standalone UIs, follow each root README and Makefile/package scripts. The
all-five API harness is not a persistent production launcher. Source panels are
default-off and require verified source identity, linked Shopping owner, explicit
grant choice and current target revision outside this harness.

## Configuration and staging

Each source task_control pins HTTPS PAI URL/audience, its own IAM account,
Ed25519 issuer/kid/private key, PAI public key/issuer/kid and actual operation
fingerprint. Finance uses explicit TASK settings; Travel/Health settings carry
the shared model. PAI separately pins source endpoints, origin trust and current/
retained destination fingerprints. Shopping pins PAI IAM, user delegation,
callback IAM and an existing explicit Firebase↔Google owner binding. Keys belong
in Secret Manager/untracked env, never responses, logs, fixtures or this report.
Read service-only contract manifests before enabling writes. Registration never
grants access. The reference trust is single-owner; do not infer multi-owner
linking. Actual verified auth_time, current provider membership and revocation
epoch are required.

This is a runbook, not deployment evidence or authorization. Use each owning
repository's existing deployment/security guidance:

- PAI root README/infra and Phase9/36 acceptance records.
- [Shopping runbook](https://github.com/jasonkli21/shopping-assistant/blob/main/docs/deployment/runbook.md).
- [Finance security/deployment](https://github.com/jasonkli21/personal-finance-and-investments/blob/main/docs/06-security-and-deployment.md), Stage4 and PostgreSQL/Neon evidence contracts.
- [Travel operational hardening](https://github.com/jasonkli21/travel-app/blob/main/docs/releases/phase-9-operational-hardening.md).
- [Health deployment](https://github.com/jasonkli21/health-app/blob/main/docs/deployment/technology-deployment.md) and infra/gcp/README.md.

1. Obtain approved synthetic staging records, resource names/budgets, identities,
   private invocation, least-privilege accounts and secrets.
2. Complete hosted CI/image/native upgrade checks at exact revisions. Preserve
   backups and deploy gates off.
3. Prove real HTTPS/IAM, linked identity/revocation, readiness/reconnect and private
   storage. Travel private imports stay closed with local hosted storage.
4. Pin manifests, authorize explicit grants/consent, then enable destination
   receipt/observation, PAI adapters and source panels in that order.
5. Rehearse revocation, lost ack, process restart, original-key observation,
   mixed-revision draining and multi-instance failure using synthetic users.
6. Rehearse independent encrypted cloud restore with current deletion markers,
   private objects, downloaded exports/retention, metrics and approved RPO/RTO.
7. Complete rendered browser/device journeys and separate final review before
   production or personal-data acceptance.

## Erasure, restore and rollback

Travel exports current minimal markers independently with
`python -m scripts.secure_backup erasure-ledger --output <new-private-file>` using
the current authoritative DATABASE_URL. Restore requires --erasure-ledger, a
separate empty DB and new private-store path. Marker observation must postdate
the backup; pending owner/upstream cleanup blocks promotion. Old-schema backups
need a separately reviewed isolated upgrade; the tool never skips schema parity.
Stop writers and preserve the current ledger separately from historical backups.

Health application/restore_erasure.py replays completed/requested deletion intent
into an isolated restore, freezes owners and reuses canonical cleanup. It reports
completed/pending and does not promote a cloud restore. Require pending=0 and
inventory evidence. Minimal retained identity/user fence policy needs review.
Shopping receipts survive project deletion and participate in owner erasure.
Finance recovery/erasure remains domain-owned. All apps need separately accepted
cloud backup and downloaded-export retention policy.

Disable new PAI writes before draining. Retain old keys/trust, fingerprints,
receipts and observation endpoints until uncertainty is reconciled. Never retry
a mutation send or replace its execution key. Populated recovery tables/erasure
markers refuse downgrade; prefer a compatible roll-forward fix.

The successful Shopping live execution-authority callback is the authorization
linearization point for one already-reserved execution key. A source consent,
grant or linked-account revocation that reaches PAI before Shopping receives
`allowed=true` blocks that write. A revocation after the successful response
blocks later writes but may not cancel the in-flight transaction; the committed
receipt remains observable under current destination read authority. This does
not make the two databases globally serializable. Shopping's owner deletion
fence is local and is locked in the same transaction as the project write and
receipt, so operators must preserve that lock ordering and must not treat source
revocation as a substitute for destination erasure.

## Observability

Use bounded request IDs, proposal/execution identifiers, transition/error codes,
revision/fingerprint references and timing. Do not log private payloads, keys or
tokens. Domain receipts and PAI control state are authoritative; logs support
them. One bounded HTTP request owns each transport, with no implicit retry;
the controller owns observation/reconciliation. Cloud dashboards, cost alerts,
multi-instance lifecycle and SLAs remain unaccepted until exercised.
