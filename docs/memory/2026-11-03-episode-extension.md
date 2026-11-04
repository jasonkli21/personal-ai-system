# MEM-3 internal local development extension

Date: 2026-11-03. Supersedes the structural-only implementation boundary in the
[initial report](2026-11-03-episode-implementation.md) and the corresponding
[hardening decision](2026-11-03-episode-plan-hardening.md). The owner authorized
implementation of remaining safe work and amendment into the original commit.
No subagents, deployment, model calls or runtime host registration.

## Implemented

`memory/episode_service.py` now supplies internal capture, bounded metadata
listing/search and exact-ID fetch (`read`), explicit trusted-host forget and
expiry/source purge. Capture and selection are independent constructor options,
both false by default. Both require memory enabled, local/test environment,
explicit `synthetic_local` profile, authenticated owner/exact actor, nonexpired
principal, audience/client, project and a host source authority. No authority is
installed by application composition. These options are not environment flags.
Unknown profiles, missing authority and foreign guesses fail closed.

The authority supplies bounded lease/project/resolve/current operations. Resolve
must authenticate the original workflow/spec and original project/branch/source
binding, synthetic-public classification and observation/expiry times. Current
must validate every source and permission dependency. The lease must fence changes
through transaction commit and read return. Neither caller-supplied JSON nor the
structural validator replaces this authority. Canonical
`PostgresWorkflowStore.terminal_evidence` provides a minimal scope-filtered
receipt read without copying spec, events, reasons or tool output. A host still
needs its original submission evidence; this adapter cannot invent timestamps
or project provenance missing from historical rows.

Migration 035 adds a bounded metadata projection in the canonical PostgreSQL
memory domain. A namespace binds owner/app/workspace/exact actor/client audience/
client/project ID/purpose. Project revision and branch are compared before
selection; they do not rekey the original receipt. The bucket retains <=128
candidate states and <=128 original-run receipts. Each run contributes <=8
records, each <=2 KiB, retention <=30 days. At most 128 namespaces may be allocated
per repository/database; overflow denies, never prunes authority. The SQL bucket
has a 512 KiB encoded size constraint. Unknown/missing reads do not allocate rows.

The in-memory repository stages a deep copy, publishing only after successful
exit. PostgreSQL locks canonical owner deletion authority, then namespace; global
new-namespace admission is serialized and all projection/state/receipt updates
commit together. No workflow execution state machine is created. Forget invokes
the existing canonical lifecycle `transition`, retaining the lifecycle event,
advanced validity epoch and original receipt while deleting searchable payload.
Repeated forget succeeds. Original-run retry reconciles an exact fingerprint;
changed evidence conflicts. Lost ACK returns unavailable; exact retry reconciles
the same run key. Purge removes expired/withdrawn payload while retaining keys.

This is a single snapshot source dependency per record, stored in the candidate
source digest; bounded purge scans <=128 records. It deliberately has no separate
index/embedding/cache/edge copy. Source withdrawal suppresses reads immediately
through current authority; explicit purge erases the local projection. The
source host must invoke purge after withdrawal. A normalized multi-source graph
is deferred until a real issuer defines source identity/epoch semantics; indexing
opaque snapshot hashes as fake per-document grants would fabricate authority.

Account erasure has an explicit `PostgresEpisodeRepository.erase_owner` operator
seam that refuses unless the existing durable owner deletion fence is installed.
The fence remains after payload deletion and denies recapture. Episode export,
automatic account orchestration and scheduled purge registration are not installed.
No profile/knowledge export silently includes episodes.

## Evidence and limitations

`make memory-episode-check`: 94 tests pass (77 existing candidate + 17 service).
The service tests cover capture/list/fetch, truncation, forget/replay, source
withdrawal/purge/re-enable without resurrection, project drift, scope/null-actor
and client denial, fail-closed profiles, precommit rollback, lost ACK retry,
capacity, no allocation on misses and erasure after capture/selection shutdown. The source authority and workflow envelopes
are synthetic test fixtures, **not a live authenticated workflow demonstration**.
The 38-case frozen candidate corpus is unchanged; it is not an end-to-end utility
benchmark. The first service test run had fixture NameError errors; corrected
fixture initialization without loosening contracts.

`make backend-lint`, `make naming-policy-check`, and `make workflow-check` pass
(70 workflow tests). The final native network-fenced focused command is `/usr/bin/sandbox-exec -p
'(version 1)(allow default)(deny network*)' backend/.venv/bin/python
backend/scripts/offline_test_runner.py -q backend/tests/test_episode_candidates.py
backend/tests/test_episode_service.py backend/tests/test_workflow_contract.py`.
The final run passed 110 tests with zero forbidden Python network attempts,
including the two capacity/miss-allocation checks. `make memory-episode-postgres-check` is BLOCKED before pytest:
`PERSISTENCE_TEST_POSTGRES_DSN` is unset. Two opt-in native tests are supplied in
`tests/persistence/test_episode_postgres.py`: service capture/forget/replay and
transaction rollback/concurrent connection serialization. No SQL migration,
concurrency, account-erasure or native durability pass is claimed. Original
provider-isolation source-lock failure remains unresolved; adding more package
files changes its source digest again. Historical locks remain untouched.

## Deferred work and rationale

| Remaining item | Reason and dependency; when required |
| --- | --- |
| Real local workflow producer/observation issuer | Current HXE workflow row erases original spec and lacks project/branch/time bindings. A trusted submission host must retain closed original bindings and authenticate observations. Necessary before any automatic capture, even local; historical rows cannot be backfilled by guessing. |
| Distributed source lease and physical disclosure fencing | Depends on inherited MEM-1/MEM-2 source issuer and PI/HXE authority work. The E1 host protocol is not a production issuer. Required before model/external use. |
| Restore-safe durable anti-replay/revocation authority | Inherited PI restore and MEM tombstone-capacity gates remain open. Buckets keep keys and deny saturation but cannot detect mixed-age rollback. Restored stores must remain offline until reconciled. |
| Automatic account/purge orchestration and native erasure evidence | Explicit operator seams exist; scheduler/account-family integration needs native lifecycle, failure and owner-deletion tests. Defer registration rather than expose an unverified data family. |
| Native SQL verification | Requires operator-supplied disposable PG/pgvector DSN. Tests are present; unavailable infrastructure cannot be replaced by a fake pass. |
| Additive planning/source-generation migration | New files invalidate frozen source identity. Needs dependent manifest regeneration and exact-commit release review, preserving prior locks. Release remains NO_GO until completed. |
| Rich search, model tools and context injection | Internal bounded metadata listing and fetch suffice for this component. Model-facing use depends on trusted host registration, shared context permission dependency/send fencing and independent review. No ad hoc context append. |
| Matched task/model utility and independent fixture review | Requires the real producer and permitted model admission. Existing structural fixture cannot establish downstream utility. Add paired end-to-end scenarios before enabling; real E2/E3 and E5 utility remain unrun. |

These are not all completed by other phases: producer integration and native
local verification are concrete unfinished implementation/verification tasks.
They are explicitly deferred here to avoid claiming fixture envelopes are real
workflow evidence. Full MEM-3 acceptance remains partial, independently unreviewed
and production NO_GO. No MEM-4 work is started.

Rollback: disable capture and selection independently and remove host use. Leave
migration 035, original receipts, lifecycle events and owner/source authority in
place. Purge via source/owner-governed operations; do not down-migrate, prune keys
or serve stale restored buckets. Reproduce with the two new Make targets and the
existing candidate targets. Review `episode_service.py`, both repository adapters,
workflow read seam, migration and service/native tests together.
