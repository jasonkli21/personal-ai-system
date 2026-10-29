# MEM-1 knowledge ownership and verification contract

Date: 2026-10-29 (America/Los_Angeles). Implementation base:
`293a5910827d9a1f70e1342ee3b98f24ab615e4d`. Status: implementation decision,
pending independent review and native/external acceptance described in the report.

The implementation prompt's MEM-0 entry gate was initially open. The user
explicitly authorized continuing without acceptance, then requested an attempt
to resolve MEM-0 first and continuation if incomplete. This overrides sequencing,
not evidence: MEM-0 review findings and suite results retain their own status.
See the implementation report for this session's verification.

## Decision and alternatives

Choose A: immutable `KnowledgeRecord` schema 3 in the existing memory domain,
with typed `procedure` and `project_decision` content. B, extending `Memory` or
`DerivedMemory` by subtype, would reinterpret the exact user assertion grammar
or schema-2 two-to-four-source `support-v1` guarantee. Both old readers stay
unchanged. New tables are owned by `PostgresMemoryRepository`, with a matching
in-memory adapter and narrow protocol. There is no new datastore or scheduler.

The first selector uses exact project/revision/kind/authority filters and bounded
deterministic ordering, explicitly without embeddings. Project-local verified
workflows do not need semantic ranking to establish the first vertical slice.
The server-built `MemoryQuery` carries an optional knowledge filter; an explicit
`MemoryRetriever.retrieve_knowledge` path returns the existing retrieval envelope.
Legacy `retrieve` and the `fixed` default remain unchanged. Selection and admission
have separate default-off flags, both subordinate to the existing memory gate.

## Authority and sources

Authenticated request scope and a trusted project resolver supply owner, actor,
application, workspace, project, branch and current revision. Candidate content
cannot supply grants, authority, success, source epochs or project identity.
Only a resolver can turn an opaque reference into evidence. Procedure content
must match the independently resolved completed run, including all steps, exact
command/tool, task/run/attempt, issuer, scope, revision, result and UTC times.
Only a historical success qualifies. An applied memory-effect receipt and an
assistant's success claim are never external execution evidence.

No production-worthy workflow issuer exists at the inspected base. The default
resolver denies all intake. A stateful hermetic resolver lives in evaluation
support, never application composition. Production procedure intake therefore
remains unsupported even if flags are enabled. The authenticated completed-turn
decision resolver requires server-established confirmation, an exact user claim,
a completed active assistant turn, source policy and an explicit source lease.
It is not automatically wired to chat extraction or exposed by an API. Missing
authentication, confirmation, source lease or project authority denies admission.

Every normalized edge carries a scoped opaque source ID, fingerprint, epoch,
relation, and resolver identity. One to eight edges are required; no truncation.
One knowledge permission dependency binds the complete record, lifecycle epoch,
actor and current project. Its shared revalidator resolves every source edge;
grants alone cannot establish semantic support. Raw stdout, credentials, logs
and execution payloads are not persisted. A conservative bounded metadata policy
rejects sensitive text and instruction injection before any durable write.
Existing sensitive personal-memory extraction rules are unchanged.

The first procedure support recipe is deliberately exact: a historical success
claim for `make backend-lint`, `make backend-test-offline`, or `make memory-eval`,
with fixed project-revision preconditions and limitations. A successful command
does not validate arbitrary accompanying claims. Evidence expiry is capped at
30 days from observation. Context retains verified/expiry times and uses the
server query's token cap in the shared assembler. Selection exposes a normal
memory retrieval trace plus bounded inspection metadata.

## State, effects and races

Admission is resolve → validate → acquire source lease → revalidate → canonical
transaction. The lease must fence all source mutations until the transaction's
outcome is known. The hermetic resolver shares its mutation lock with its tools;
the completed-turn adapter requires the existing source-guard authority supplied
by its host. No read/check callback alone is a production lease. No atomicity
between Dynamo and Postgres is assumed. Missing distributed fencing denies
production intake. Cancellation before commit writes nothing; an uncertain SQL
outcome is reconciled using the original admission key, never a fresh identity.

The key binds scope, actor, project, evidence identities/epochs, policy, kind and
claim. Payload fingerprint additionally binds all bounded fields. Equal retries
return one record; changed payloads or expected lifecycle epochs conflict.
Forgotten/reviewed/superseded records cannot be reactivated by retry. Canonical
record and all edges commit together; source revocation/erasure traverses the
complete reverse relation. Source tombstones prevent same-epoch resurrection.
Source validity updates and admission serialize in Postgres as well as under
the required external lease. Account export/deletion includes all new families.

Lifecycle authority remains `MemoryLifecycleState`, `MemoryLifecycleEvent` and
the existing pure `transition` policy, using the same projections/event tables.
No second lifecycle status field or independent maintenance worker is added.
Knowledge operations are explicit developer operations with epoch CAS, rather
than automatic personal-preference contradiction/forgetting heuristics.

Selection, shared packing, consumption and later history/summary reuse check
the same dependency. A fresh project read is mandatory at use. A record at an
old revision or branch, unavailable source, expired/effective-future evidence,
revoked permission or changed lifecycle epoch is suppressed. Actual Task B
execution occurs under a final authority lease and rechecks revision before
action. Context text is historically scoped, untrusted advice with limitations;
it never grants tool authority or proves current repository truth. The existing
prohibition on memory-derived artifact writes remains.

## Migration, rollback and verification

Migration 028 follows inspected migration 027. It adds scoped knowledge records,
source fences and normalized provenance edges, foreign keys, uniqueness, bounds
and reverse indexes. V1/v2 tables and applied migrations are untouched. Native
tests cover ordered forward migration, concurrent admissions, lifecycle CAS,
reverse erasure and legacy reads when a local pgvector engine is available.
Offline fakes cannot establish these database guarantees.

Rollback disables selection immediately, then admission; legacy reads ignore
schema 3 data. No destructive down migration or production flag enablement.
The new paired benchmark issues a Task A result, persists knowledge, destroys
session state, then checks a distinct Task B effect/outcome. Safety-invalid traces
fail execution; low task quality is reported separately. Synthetic observations
establish neither model lift nor deployed identity, cloud, retention or recovery.

## 2026-10-29 independent-review remediation addendum

The review of `2df112bf04b8d817c2cfee9c807786161d2fec4f` led to a forward-only
actor binding for source identities. Migration 029 maps retained schema-3 edges
to the record's exact actor, clones each referenced pre-migration fence for
that actor, and retains orphan legacy fences under a non-authorizing `L` key as
global replay denies. New actor-specific fences use lossless `N`/`V<actor>` keys,
and lookup, CAS revocation, reverse deletion, retention, listing and consumption
require the bound owner/application/workspace/actor request. Account deletion
remains owner-wide through its existing inventory family. Shared actor access is
not inferred from equal owner, workspace or source ID.

The shared context builder now rechecks expiry and every permission dependency
after all final and marginal token counts. Optional items that expire during
counting are removed and recounted; late permission loss or expiry fails the
build closed. Chat revalidates source snapshots again immediately before model
handoff. The `ai_memory` header describes untrusted historical source data,
per-item authority/verification/time scope, possible staleness, and no current
fact or action authority.

The original `mem1-paired-v1` stateful suite and fixture remain unchanged and
are now described as structural/safety-proxy evidence. A distinct
`mem1-consumer-v1` suite exercises the shared packer and a deterministic
consumer whose interface accepts only packed messages and narrow read/execute
handles. Its 16 paired cases are synthetic and author-reviewed; independent
fixture review and real-model utility remain unverified. It does not establish
agent lift.

No safe source-fence compaction was available without a durable issuer
watermark or versioned namespace epoch. The 1,024-row fence limit and permanent
replay tombstones are therefore an explicit production blocker documented in
the [capacity follow-up](mem-1-tombstone-capacity-follow-up.md). Both knowledge
flags remain false by default. No production issuer, recoverable distributed
lease, public mutation path, application-grant adapter or cloud deletion path
was added. See the [review remediation evidence](mem-1-review-remediation-evidence.md)
for test results and the no-go acceptance status.
