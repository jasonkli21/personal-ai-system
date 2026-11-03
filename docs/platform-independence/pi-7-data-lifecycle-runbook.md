# PI-7 data lifecycle and restore

## Where disclosure can persist

| Copy | Owner | Fence or required recovery action |
| --- | --- | --- |
| Original source records and backups | Source app or external issuer | Keep current owner, actor, app, workspace, recipient, purpose, revision, expiry and use rights under the issuer's authority. Treat missing proof as denial. |
| Local retrieval index and excerpts | Operator installation and derived context | Recheck exact issuer, content, revision and rights epoch. Keep deleted/obsolete installations out of the serving path. |
| Profile and consent, federation grants | Postgres | Reconcile active revisions, archived grants, consent receipts and owner fences with current authority. Old allowlists never confer consent. |
| Memory, embeddings and derived knowledge | Postgres/pgvector | Keep normalized source edges, lifecycle events, validity epochs and tombstones. Review vector and index cleanup as part of erasure. Preserve forget receipts and monotonic epochs. |
| Research/evidence, decision and mutation records | Postgres and owning source/domain app | Revalidate source purpose and current rights before use. Preserve committed command keys, fingerprints and reconciliation receipts. Domain effect and receipt remain the domain app's authority. |
| Conversations, messages, branches, summaries, traces and external turns | DynamoDB and local test equivalents | Preserve retained dependencies and original-key status. Quarantine unknown or stale derived copies before read, reassembly, send, replay or streaming. |
| Usage reservations, provider attempts and search intent | Postgres P19, DynamoDB usage events, local SQLite journal | Reconcile pending, timeout and unknown attempts by original identity. Retain consumed capacity and content-free tombstones until the owning retention contract says otherwise. |
| Artifact metadata and bodies, cached/exported content | Postgres plus configured artifact store, browser/client and recipients | Recheck before issuing/readmitting exports. Invalidate service-side copies and account for independent recipients, signed URLs and already downloaded files. |
| Snapshots, replicas, logs, diagnostics and provider copies | Operators, infrastructure and vendors | Inventory retention, key access and deletion authority per system. Logical denial and backup expiry need separate evidence. |

The account deletion workflow uses an operator fence. Current source/export
and physical deletion restrictions remain in the owning code and phase
gates. A retained status or content-free receipt may remain observable when
its derived text is no longer eligible.

## Synthetic exercise

`make pi7-consumer-smoke PI7_SMOKE_FLAGS=--require-native` runs
`test_pi5_context_pi7_stale_derived_restore_keeps_revocation_and_original_keys`.
It takes an in-memory message snapshot after a real synthetic chat turn,
revokes the local source, keeps its stale installation file quarantined,
reinstates the stale message repository and exercises detail, replay and a
fresh send through the real HTTP service. A separate retained SQLite journal
preserves an original-key uncertain attempt and refuses a changed payload and
capacity exhaustion. The journal is outside the restored message snapshot.
The simulation assumes that current authority survives. Replacing the
current manifest or journal with the old copy can roll back that authority.

## Operator-approved native drill

Record approval naming the operator, exact isolated local Docker context and
store IDs, synthetic input, allowed restores and erasure, retention, time
window and cleanup. Use separate disposable source and destination networks,
store namespaces, credentials and processes. Verify no production routes,
account, disks, keys or backups are reachable. Save image IDs and migration
versions. Obtain explicit owner permission before executing native restore or
destructive steps.

1. Use a dedicated test database/schema and Dynamo table under unique labels.
   Create synthetic grant, message/summary, trace, eligible exported artifact,
   scoped job and an original attempt whose acknowledgement will be lost.
   Record source/dependency revisions and content-free operation identities.
   Capture a consistent stale snapshot per store with the snapshot tooling
   approved for that test target. Record each snapshot's timestamp and hash.
2. Revoke one source and forget or fence another after the snapshot. Verify
   new sends, detail, history, summary reuse, replay and export refuse.
   Capture the current issuer high-water mark, owner fences, tombstones,
   P19 attempts and domain receipts in independently retained authority.
3. Restore the stale data into the second disposable destination, isolated
   from traffic and provider egress. Keep all workers stopped. Do not overwrite
   the current issuer, deletion or receipt authority. Reconcile monotonic
   revisions, committed keys, pending reservations and quotas before opening
   any route. Inject missing and stale authority. Both must deny. Prove a
   parallel worker cannot claim the old attempt after recovery.
4. Run the same read/send/replay tests, including changed payload, capacity
   pressure, expired grants, same-key retry and mixed snapshot times across
   stores. Inspect artifact body access, cache paths, secondary indexes and
   backups. Verify a new authorized operation separately.
5. Perform only the approved disposable erasure, then independently verify
   remaining primary data, index entries, artifact bodies, replicas and
   snapshot copies under their documented retention policies. Preserve
   content-free receipts and tombstones when the owning contract requires
   them. Retain aggregate proof and clean up only the named disposable
   resources.

Stop if current fences cannot be obtained, if any canary discloses or resends,
or if cleanup ownership is uncertain. Keep restored traffic quarantined and
record the failed authority. Native restore, provider retention and verified
physical deletion remain blocked pending this evidence and the inherited
[PI-5 completion gate](pi-5-completion-gate.md).
