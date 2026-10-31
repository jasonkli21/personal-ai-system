# Current implementation state

Updated 2026-10-30. This is the living implementation boundary. Code, contracts,
migrations and tests control behavior; dated evidence controls acceptance. The
[suite handoff](../stabilization/FRESH-REVIEW-HANDOFF.md) records this change and its
verification. Independent final review and external acceptance remain open.

## Delivered locally

The Next.js frontend proxies the FastAPI API. Services own chat, active message
branches, token-budgeted context assembly, summaries, durable memory, research,
time-sensitive evidence, decisions and domain contributions. Provider SDKs stay
inside inference adapters. Summaries remain lossy branch context; memory and
external evidence retain different authority and freshness semantics.

| Area | Implemented boundary | Remaining acceptance |
| --- | --- | --- |
| Context and inference | Shared assembler, deterministic planner, bounded inspection, field/sensitivity policy, provider-neutral gateway and LiteLLM transport | Immutable source/policy references and deployed membership/revocation; live provider token/account/privacy semantics |
| Persistence and artifacts | PostgreSQL/pgvector adapters, DynamoDB adapters, private artifact tier, owner lifecycle and retention operations | DynamoDB engine, cloud object storage, physical deletion and cloud recovery beyond the exercised PostgreSQL subset |
| Routing and evaluation | Endpoint admission, physical-send accounting, deterministic routing, bounded tasks, shadow experiments and paired evaluators | Workflows remain gated; no adaptive, memory or search coverage is promoted by synthetic evidence |
| External and domain context | Typed Travel, Shopping and Finance reads; separate broad Health read and narrow signed Health exports; owner-scoped grants and opaque choices | Broad Health still requires a Firebase user token; native linked identity, cloud IAM, domain/browser and grant UX acceptance |
| Delegated Shopping tasks | Canonical closed wire, signed source ingress, domain capability metadata, existing confirmation/reservation/reconciliation lifecycle; budget and append-note adapters | Default-off, deployment-managed single-owner origin trust; actual cloud identity and browser/device acceptance |
| Application hosts | Shared sidecar and user-local external-turn composition behind their existing gates | Shopping sidecar, general Shopping AI generation/research transport and connected workflow routing remain incomplete |
| MEM-2 controls | Default-off bounded schema-3 search/fetch/topics with explicit partial-result status, proposal-only host tools, authenticated pending review/reject and atomic user forget with durable receipts; bounded idle proposal purge in scheduled maintenance; opt-in API/UI; no live tool registration | Narrowed phase: no evidenced revision issuer/atomic replacement or production host; independent review and inherited gates remain open; forget receipts are permanently retained outside the proposal/review quota, so operational storage growth and physical-send fencing remain unresolved |
| MEM-1 project knowledge | Default-off schema-3 procedures/confirmed decisions; actor-bound source fences in migration 029; final context and model-send permission checks; preserved 20-case stateful proxy plus a 16-pair deterministic packed-content consumer | No-go for acceptance: permanent tombstone capacity blocker, independent fixture review, production issuer/lease and app-grant policy, deployed identity/source deletion, real-model utility and cloud acceptance |

The new source paths are Finance monthly budget → Shopping budget, Travel
consented destination/dates → Shopping note, and Health consented ergonomic
constraint → Shopping note. Domain apps retain canonical data, UI, revisions,
validation and consent. Personal AI persists only orchestration intent and
outcomes. Tasks do not invoke model providers or automate purchases.

## Platform Independence / freeze status

[PI-0](platform-independence/pi-0-implementation-report.md) establishes a local
architecture/documentation/dependency-diagnostic baseline with no runtime change;
the [2026-10-30 review remediation](platform-independence/pi-0-independent-review-remediation-2026-10-30.md)
adds explicit facade-import diagnostics and strict waiver validation. Independent
PI-0 acceptance remains pending. [PI-1](platform-independence/pi-1-implementation-report.md) is a user-directed
implementation candidate pending independent review: separately built core and
optional reference distributions, explicit catalog selection, core HTTP/lifespan
physical-absence probes and retained-task startup refusal. [PI-2](platform-independence/pi-2-implementation-report.md) adds a user-directed
local candidate: verified OAuth client/app binding with revocable operator policy,
a narrow v1 HTTP contract, canonical continuation-key status, a separately built
history-only Reading Logbook host and a dependency-free HTTP client with its own
local records/journal. Independent PI-0/1/2 acceptance remains pending. [PI-3](platform-independence/pi-3-implementation-report.md)
adds a user-directed local candidate: closed operator-selected normal inference,
two exact local fake profiles, explicit strict-free legacy composition, ancillary
privacy/admission and physical-reservation rechecks, neutral summary/memory/worker
composition, and unconditional paid-mode denial. Remote Groq/Cloudflare generation
and new memory embeddings remain unavailable without approved exact input counters;
this is not live non-Gemini or billing acceptance. The inspected OS/Python-fenced PI-3 suite passed 780 tests with zero forbidden
network attempts; installed core/reference/task/Reading Logbook checks passed.
The 2026-10-30 [PI-3 review remediation](platform-independence/pi-3-review-remediation-2026-10-30.md)
binds source checks through chat assembly and research synthesis, denies in-process
credential rotation under an old admission, and reports unavailable memory
embedding before retrieval/extraction. Initial credential-to-account proof,
independent PI-3 review, installed Linux/Python 3.12 checks, and provider/cloud
acceptance remain open. [PI-4](platform-independence/pi-4-implementation-report.md) adds a user-directed
local candidate: default-off owner/actor/destination/purpose/expiry and whole-profile
revision/value-bound grants, native PG/in-memory CAS and retained original-key
receipts, legacy re-consent migration, canonical projection and inherited
count/summary/history/reservation/SSE/replay and external detail denial. The unrelated Reading Logbook
recipient has a separate opt-in manifest policy. Exact-record memory sharing is
explicitly unavailable and browser consent UX remains incomplete. Native synthetic
SQL and installed synthetic identity/provider checks do not establish cloud,
physical erasure/restore anti-rollback, live identity/provider or independent
acceptance. External detail rechecks current client/workspace authority and
profile source snapshots before serialization; stale or unprovable output receives
a content-free 409, and fully unattributed external assistant history is
quarantined. Unmarked legacy text still cannot be classified and must remain
quarantined during rollout until reviewed. Built-in owner history remains visible.
See the [consent API/operations](platform-independence/profile-sharing-v1.md) and
[review remediation evidence](platform-independence/pi-4-independent-review-remediation-2026-10-30.md).
Local verification: 12 signed HTTP cases passed for revoke, profile revision,
expiry, kill switch, source failure, owner deletion fence, old/missing provenance,
missing validator, workspace/client loss, stable continuation status, no second
send, and builtin-owner display. The post-remediation full PI-4 run reports
891 passed / 2 failed: provider-matrix and Phase 36 synthetic counts are 73
instead of 80. A focused provider-matrix/Phase 36 run had 21 passed / 3 failed,
including the reviewed resume-count failure. The v23 planning check passes after
its source-only digest was refreshed; no count assertion or held-out lock changed.
The final offline PI-2 consumer check passed its contract, installed core,
reference, retained-task and HTTP/client probes. These PI-4 matrix failures
remain verification gaps; see the [remediation evidence](platform-independence/pi-4-independent-review-remediation-2026-10-30.md).
PI-5 through PI-8 remain undelivered. The user-directed memory feature freeze stops at MEM-2:
MEM-3+ is frozen, MEM-2 is not promoted, and all existing default-off memory
semantics and independent/security/production gates remain in force.
The 2026-10-30 PI-1 review remediation fixes the eight reproduced CI failures,
the stale reference-evaluation module invocation, and the platform-specific
artifact-check temporary path. Offline wheel/sdist and installed-profile checks
pass locally; see the [remediation evidence](platform-independence/pi-1-review-remediation-2026-10-30.md).
PI-1 independent review, Linux/Python 3.12 CI, provider/cloud, and native-storage
acceptance remain open.

## MEM-0 research baseline

MEM-0 remains an opt-in offline benchmark. The active v2 corpus has 30 synthetic
cases across six families and preserves v1 as historical evidence.
`make memory-task-eval` runs four arms twice through shared context packing, with
real fixed retrieval/revalidation for legal v1 assertions. Current scripted task
proxy results are none 19/30, fixed 22/22 with eight unsupported cases, full
eligible history 29/29 with one truncated case, and gold 30/30. On the 22 paired
fixed-versus-none cases there are three wins, 19 ties and no regressions. These
curated denominators do not measure model quality.

The earlier remediation's full offline run failed: 1,833 passed, three
provider-matrix tests failed, and 90 were deselected; isolated retries passed.
A fresh serial run on the MEM-1 entry base passed **1,836 tests**, with 90
deselected. This supplies a clean rerun, not a demonstrated fix or root cause for
the timing failures. The original focused command again passed 281 tests;
the final expanded memory/artifact regression passed 484. See the
[entry verification attempt](memory/mem-0-entry-reverification.md) for exact
commands, F1–F4 probes, intermediate failures and the preserved result digest.

The [MEM-0 report](personal-ai-chapter-2/memory/mem-0-baseline-report.md) binds the
tested source on base `987bba5f6479791b54ac626d9959b1b39e23fbb3` plus source and
fixture identities, commands, results and remaining gaps. The independent
review and its separate remediation record are linked from the [report](personal-ai-chapter-2/memory/mem-0-baseline-report.md).
Fresh independent MEM-0 acceptance remains unclaimed. The user explicitly
authorized MEM-1 continuation after attempting MEM-0 re-verification. Existing
v1/v2 memory contracts, source-policy semantics and fixture bytes remain unchanged.

## MEM-1 verified procedural and project memory

The narrow source-verified Task A → durable knowledge → fresh Task B loop is
implemented behind separate default-off admission and selection flags.
Schema-3 `procedure` and `project_decision` records belong to the existing
Postgres memory repository. Migration 028 adds scoped admission identity,
normalized provenance and source-epoch tombstones; migration 029 adds exact
acting-user identity to source fences and reverse edges while preserving old
knowledge rows. Existing lifecycle state/events remain authoritative. Selection uses exact project/revision filters without new
embeddings or provider calls. Shared assembly enforces query budgets and preserves
historical authority/verification/expiry labels, references and permission
dependencies through supported later history/summary reuse. Artifact writes with
memory dependencies remain prohibited. The review remediation rechecks permissions
and expiry after final token counts and at the actual model handoff.

The procedure recipe states only an observed historical success for three
allowlisted Make commands. An authenticated completed-turn decision remains a
user assertion. Production has no workflow receipt issuer or automatic intake
path; enabling flags alone cannot supply one. Hosts need current application and
project authorization plus source leases that fence mutations through commit and
consumption. No public memory tools, new scheduler or default routing change.

The preserved `mem1-paired-v1` 20-case hermetic proxy has six tagged holdout cases
and two matching semantic replays. It remains structural/stateful safety evidence,
not a content-causal measure: the scripted Task B can access typed proposal data.
The new `mem1-consumer-v1` companion uses 16 paired cases and passes only packed
messages plus narrow read/execute handles to a deterministic parser. It scores
16/16 for knowledge and eligible history, 0/16 for no memory, and 16 ties between
knowledge and history; this is a content-causal synthetic consumer check, not
model utility evidence. Fixture review remains independent-pending.

The [MEM-1 remediation evidence](memory/mem-1-review-remediation-evidence.md)
records the review dispositions, final offline/native counts, new fixture identity,
and residual blockers. The [tombstone follow-up](memory/mem-1-tombstone-capacity-follow-up.md)
quantifies the 1,024-fence quota and holds production promotion until safe replay
compaction is proven. The earlier provider-matrix failure remains in the
implementation report; its clean rerun is not a claim that the clock issue was fixed.
The remediation full offline run passed **1,923 tests**, with 99 deselected; local
PostgreSQL/pgvector checks passed 32 with eight DynamoDB skips. Exact commands,
fixture identities and gates are in the
[remediation evidence](memory/mem-1-review-remediation-evidence.md).
The [ADR](memory/mem-1-contract-adr.md) records ownership/rollback, and
the [separate review handoff](memory/mem-1-independent-review-handoff.md) makes no
review verdict. Native PostgreSQL results do not establish DynamoDB, deployed
source revocation/physical deletion, cloud recovery, provider or production safety.

## MEM-2 authorized memory controls

The [MEM-2 control ADR](memory/mem-2-control-adr.md) records the preflight gates and
trust/transaction decisions. The [2026-10-30 review remediation evidence](memory/mem-2-review-remediation-2026-10-30.md)
records fixes for review findings F1–F5, F7 and F8, with F6 kept as a production-host
prerequisite. User forget remains available after proposal/review receipt quota
exhaustion; all operation keys remain durable and are never pruned. The maintenance
worker physically removes expired proposal content in bounded batches when scheduled
maintenance is enabled. Expired or source-revoked history can be suppressed by the
same currently authorized owner/actor/project without making it readable again.
The implementation still stops at unsupported revision because no production
confirmation issuer and recoverable source lease are installed. Review never admits
a proposal. All new flags default false and require schema-3 selection; API composition
additionally requires an explicit host resolver and project mapping. The host tools
are exercised hermetically, with no generic provider execution loop or automatic
registration.

Search/fetch/topic results require exact owner/app/workspace/actor and current
project/source/lifecycle authorization. User forget requires verified recent
identity, explicit intent and expected version; its lifecycle event, validity epoch
and content-free operation receipt commit atomically. Exact-key retries reconcile
actual durable outcome; uncertain commit remains unknown. Pending proposals expire
at 24 hours and the scheduled-maintenance hook purges expired proposal bodies in
bounded batches. The 256 receipt quota applies only to proposal/review operations;
forget receipts remain durable and do not consume it. Source tombstones retain their
independent 1,024 namespace cap. Export inventory and fenced local operator purge
include both new control tables. No automatic physical account eraser or production
source/identity/provider acceptance is added.

See the [implementation report](memory/mem-2-implementation-report.md) for exact
original implementation checks, resource measurements and blockers, the
[review remediation evidence](memory/mem-2-review-remediation-2026-10-30.md) for the
follow-up changes and tests, and the
[independent review handoff](memory/mem-2-independent-review-handoff.md) for separate
review. Implementation of this narrowed slice is not full phase completion or
production promotion. Historical MEM-0/MEM-1 reports, fixtures and acceptance gates
remain unchanged. Planner v18 is a source-only non-promoting rebind of v17.

## Identity and effect boundaries

Deployed requests require independently verified service IAM plus a bounded,
request-bound Ed25519 delegated Google identity. Authentication time comes from
the verified upstream event, never token issue time or a local session timestamp.
Source/destination mappings are explicit; email and UUID similarity never link
accounts. Shopping and Health recheck current linked Google provider membership,
disabled status and Firebase revocation time. Local identity is test-only.

Grants retain issuance, revision, purpose, destination and source policy. Source
consent/revision and target permission are checked before reservation and again
by the Shopping receiver. Confirmation binds immutable intent. One execution key
owns one reserved send. Receipt and effect commit together in Shopping. Lost
acknowledgements become uncertain; reconciliation observes the original key and
never resends. Retained fingerprints support observation of known receipts;
retirement does not reinterpret an old payload as a new write.

For a reserved write, Shopping's successful live execution-authority callback is
the authorization linearization point: revocation before the receiver gets an
allow blocks the effect; revocation after the response blocks later effects but
does not cancel the in-flight transaction. Shopping's local owner-deletion fence
is still serialized with its write and receipt. Read-only target choices expose
only owned active project IDs, titles and current revisions; apply rechecks the
destination revision.

The source apps now use that target-choice seam instead of asking users to paste
project IDs and revisions. Travel and Health persist distinct create, submit,
confirmation, and effect-uncertain phases so recovery keeps the original command
and execution identity. These are local UI flows behind existing default-off
gates; rendered browser/device acceptance remains open.

## Verification and rollout

On the reviewed re-review base `20ef41ae6b76de691c003ae6a345fdb91b3ecd02`, the
final fix source passed **1,749 offline tests**, **75 native PostgreSQL tests**
(14 unavailable DynamoDB cases skipped), and the all-five loopback HTTPS matrix
passed **40 cases**. The matrix uses real migrations, PostgreSQL state,
signatures and HTTP listeners; Google/Firebase lookups remain synthetic. Exact
fix commits, commands, source identities, counts and limitations are in
[verification](../stabilization/VERIFICATION.md).

Planner locks v10-v21 remain historical. MEM-2's v18, PI-1's v19 and the initial
PI-2 candidate's v20 retain their dated source bindings. The PI-2 review
remediation added source-only, non-promoting v21, preserving v20's
deterministic planner configuration, 30 held-out cases, corpus and fixture
dependencies. All prior lock bytes remain unchanged. PI-3 adds active source-only v22 after the inference composition changes, retaining
all v21 planner/corpus/fixture/configuration bytes and non-promotion. The strict
current-or-direct-child source guard remains; production replay still rejects
source, runtime and unrelated revision changes. PI-4 appends source-only v23,
retaining the original planner configuration/corpus/fixture bytes and all v10–v22
history; synthetic profile fixtures now issue explicit grants and bind the actor.
Portable tests use an explicitly
test-only lock. Nothing is promoted from this freeze. See the
[PI-2 review remediation evidence](platform-independence/pi-2-review-remediation-2026-10-30.md)
for the external creation and streaming disclosure fixes and local verification.

Phase36 retains its earlier **24 passed offline rows**; its exact soak counts
remain in the generated evidence. These rows do not establish cloud, provider
or production acceptance.

Keep task, context, connected inference, private ingress and experimental gates
off until their owning acceptance evidence is complete. Provider SDK mocks,
synthetic IAM and JS bundles do not establish deployed security, live identity,
native device behavior or production readiness. No cloud deployment was run.
The prior suite authorization covered its dated five-repository patch set.
PI-4 authorizes one local commit only, without push, merge or deployment. Hosted CI outcomes
remain separate evidence and are never inferred from local checks.

## Minimum context and history

Use [the router](README.md), the owning package README, its executable contract,
and focused tests. Use [operations](../stabilization/OPERATIONS.md) for the
synthetic suite and future staging prerequisites. Use [review handoff](../stabilization/FRESH-REVIEW-HANDOFF.md)
for cross-repository review and [roadmap](../stabilization/ROADMAP.md) for remaining
acceptance and maintenance priorities. Plans authorize no new product work.

The [previous status snapshot](history/stabilization/current-state-before-2026-10-14.md)
preserves detailed phase history. The existing Chapter2 phase guides/evidence and
ADRs remain historical records at their tested revisions; this shorter status
does not revoke their unresolved gates.
