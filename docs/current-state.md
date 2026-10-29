# Current implementation state

Updated 2026-10-29. This is the living implementation boundary. Code, contracts,
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
| MEM-1 project knowledge | Default-off schema-3 procedures/confirmed decisions in existing memory ownership, normalized source fences, shared lifecycle/context revalidation and a 20-case paired-session proxy; native PostgreSQL subset exercised | Independent implementation/fixture review, production workflow issuer and recoverable source leases, deployed identity/source deletion and cloud acceptance |

The new source paths are Finance monthly budget → Shopping budget, Travel
consented destination/dates → Shopping note, and Health consented ergonomic
constraint → Shopping note. Domain apps retain canonical data, UI, revisions,
validation and consent. Personal AI persists only orchestration intent and
outcomes. Tasks do not invoke model providers or automate purchases.

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
normalized provenance and source-epoch tombstones; existing lifecycle state/events
remain authoritative. Selection uses exact project/revision filters without new
embeddings or provider calls. Shared assembly enforces query budgets and preserves
historical authority/verification/expiry labels, references and permission
dependencies through supported later history/summary reuse. Artifact writes with
memory dependencies remain prohibited.

The procedure recipe states only an observed historical success for three
allowlisted Make commands. An authenticated completed-turn decision remains a
user assertion. Production has no workflow receipt issuer or automatic intake
path; enabling flags alone cannot supply one. Hosts need current application and
project authorization plus source leases that fence mutations through commit and
consumption. No public memory tools, new scheduler or default routing change.

The separate 20-case hermetic proxy has six tagged holdout cases and two matching
semantic replays. Verified knowledge and eligible history each pass 20/20 tasks;
no-memory passes 19/20; legacy fixed has zero evaluable and 20 unsupported cases.
Verified knowledge uses history in five cases and reduces workflow rediscovery
from 16 to 12. This is finite scripted-tool behavior, not measured real-agent lift.
All 20 fixtures are author-reviewed; independent fixture review remains open.

The [MEM-1 report](memory/mem-1-implementation-report.md) records final offline and
native counts, source/fixture/result identities, retry and erasure tests, commands
and gaps. The final full offline run passed **1,911 tests**, with 99 deselected;
the relevant native PostgreSQL run passed **32 tests**, with eight unavailable
DynamoDB cases skipped. The earlier provider-matrix failure remains recorded;
the clean rerun is not a claim that its intermittent clock issue was fixed.
The [ADR](memory/mem-1-contract-adr.md) records ownership/rollback, and
the [separate review handoff](memory/mem-1-independent-review-handoff.md) makes no
review verdict. Native PostgreSQL results do not establish DynamoDB, deployed
source revocation/physical deletion, cloud recovery, provider or production safety.

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

Planner locks v10-v16 remain historical. MEM-1 adds active non-promoting v17,
preserving v16's deterministic planner, configuration, runtime, fixture dependencies
and 30 held-out cases while rebinding the changed backend source identity.
The strict current-or-direct-child source guard remains.
Production replay still rejects source, runtime and unrelated revision changes.
Portable tests use an explicitly test-only lock. Nothing is promoted from this
freeze.

Phase36 retains its earlier **24 passed offline rows**; its exact soak counts
remain in the generated evidence. These rows do not establish cloud, provider
or production acceptance.

Keep task, context, connected inference, private ingress and experimental gates
off until their owning acceptance evidence is complete. Provider SDK mocks,
synthetic IAM and JS bundles do not establish deployed security, live identity,
native device behavior or production readiness. No cloud deployment was run.
The user authorized commits in all five repositories and pushes to each
repository's remote `main` after the commits are complete. Hosted CI outcomes
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
