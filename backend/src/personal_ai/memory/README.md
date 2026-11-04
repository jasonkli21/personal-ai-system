# Memory

This package owns durable user-memory contracts, extraction, retrieval, disclosure policy, and
lifecycle behavior. Memory remains a separate data class from time-sensitive external evidence.

## project knowledge verified project knowledge

`knowledge.py` defines immutable schema-3 `procedure` and `project_decision`
records. V1 `Memory` and V2 `DerivedMemory` retain their exact contracts.
`knowledge_service.py` resolves trusted evidence, checks scope/content/currentness,
and admits through the existing memory repository. Migration 028 atomically
persists bounded records, complete normalized edges and source-epoch fences.
The first reader uses exact project/revision filters, without embeddings or
provider calls. Limits are 128 records and 1,024 source fences per namespace,
eight edges per record, and 16 KiB per serialized record. Overflow fails closed.
The initial procedure recipe only states historical success for one of three
allowlisted Make commands, with fixed revision preconditions and limitations;
source access plus a successful receipt cannot validate arbitrary claims.
Evidence expiry is capped at 30 days from observation.

`MEMORY_KNOWLEDGE_ADMISSION_ENABLED` and `MEMORY_KNOWLEDGE_SELECTION_ENABLED`
default false and require `MEMORY_ENABLED`. `fixed` stays the legacy default.
Hosts explicitly supply a trusted resolver and a server-built
`MemoryQuery(knowledge=KnowledgeFilter(...))` to
`MemoryRetriever.retrieve_knowledge`. Application composition installs no issuer:
production procedure intake is unsupported even if flags are enabled.
`AuthenticatedCompletedTurnDecisionResolver` additionally requires verified
authentication, exact user and completed assistant references/fingerprints,
registered confirmation, source policy, and a host-supplied source lease.
It is not automatically connected to chat extraction or exposed as a mutation API.

The host resolver owns current application disclosure/project grants and must
fence all source/project/permission mutations across admission and consumption.
Only the stateful hermetic evaluation issuer is provided for workflows; an
in-process mutex cannot substitute for a recoverable deployed source lease.
`KnowledgeService.consume` runs a trusted host action under final source and
canonical DB guards. The host executor owns action authorization, current reads,
idempotency and uncertain external outcomes; memory text never authorizes commands.

Knowledge uses the existing lifecycle projections, events, CAS and `transition`
policy. Explicit developer-test forget/supersede/review events suppress reuse;
automatic personal-memory heuristics/jobs do not process schema 3. Every shared
knowledge permission dependency resolves all edges and current project state at
packing, consumption and supported later history/summary reuse. Source hosts must
call `revoke_knowledge_source(..., erase=True)` when erasing registered sources;
this deletes all reverse-dependent payloads and edges while retaining a tombstone.
`erase_expired_knowledge` is a bounded existing-owner retention seam, with no new
worker. Revoked source identities cannot be reused; a newly verified run needs a
new immutable source identity. Account export inventories include all new families;
deployed source deletion and account deletion orchestration remain external gates.

`inspect_knowledge` requires the existing inspection flag and returns the same
bounded selection/rejection/source metadata. Disable selection for immediate
rollback; records remain stored and old readers ignore them. Knowledge context is
untrusted historical advice, separately labeled by authority and historical
verification. Memory-derived artifact writes remain prohibited.

Run `make memory-knowledge-eval` and the focused `test_memory_knowledge*.py` tests.
Native contracts live in `tests/persistence/test_verified_knowledge_postgres.py`.
See the [ADR](../../../../docs/memory/mem-1-contract-adr.md) and
[implementation report](../../../../docs/memory/mem-1-implementation-report.md).

## Entry points and boundaries

- Root modules own memory identity, extraction, retrieval, and general policy.
- `lifecycle/` owns lifecycle contracts, scoring, transitions, jobs, and lifecycle repositories.
- Backend-neutral memory effect coordination contracts live in `effects.py`; database adapters implement them under `personal_ai.persistence`.
- Lifecycle contracts, jobs, policy, and repositories live under `lifecycle/` and are imported from their owning modules.

Lifecycle and disclosure tests live in `backend/tests/test_memory_lifecycle.py`, `backend/tests/test_memory.py`, and persistence suites. Preserve freshness, source attribution, owner scope, and transactional behavior when changing adapters.

## memory revalidation read and maintenance contracts

`MemoryRetriever` builds a server-owned `MemoryQuery`, checks hard scope, source,
lifecycle and complete embedding-space eligibility before scoring/top-K, and returns
bounded versioned candidate traces. Postgres first loads a capped compatible corpus,
then scores only qualified IDs with exact pgvector and validates numerical parity
against lossless arrays. Oversized or interrupted reads fail explicitly; they do not
establish corpus absence. Original vectors are never rewritten by validation/search.

`fixed` remains the default. All retrieval variants collapse exact repeated
originals to one assertion while retaining their source IDs and immutable records;
the opt-in `compact` variant also removes facts already present in the current
conversation. A selected original is the fallback representation until a valid
derived view exists. The shared builder reduces its optional memory budget when domain
current context or external evidence already occupies the request; final counts and
packing remain endpoint-counted by the same builder. The canonical runtime has no lexical/ANN index,
new embedding space, paraphrase compression, or model adjudicator. The sealed
research experiment described below is separate from that runtime.

Existing bounded lifecycle jobs discover at most four compatible originals within
a one-year observation horizon. A rotating bounded corpus sweep runs after completed
turns when consolidation is enabled, so pre-existing candidates and invalidated
views can be refreshed on later turns. Similarity proposes candidates only.
`support-v1` views can consolidate exact repeated assertions and a narrow positive
preference grammar whose value and complete context clause match exactly after
surface-form normalization. Other semantic differences remain no-op. Views retain
all original excerpts, IDs, source fingerprints, turns and lifecycle dependency
versions. Source-set/version identity changes when a source validity epoch changes.
Older `extractive-v1` and `extractive-v2` views remain eligible only while their
dependencies remain eligible; v1 views are restricted to epoch zero.
Contradictions mark both sides for review; no model resolves authority or uncertainty.

`dependencies.py` registers original/view dependencies with the existing shared
permission revalidator. Each view node validates its full original set. Injection,
later assistant history and summaries reuse this graph. Artifact writes carrying
memory dependencies are explicitly rejected until artifact reuse has a scope-aware
memory revalidation context. Flag-only historical `ai_memory_read/memory-v1` proofs
are retired.
Migration 027 reconstructs epochs for old lifecycle projections using immutable
stored events. Invalid views fail closed; subsequent bounded corpus sweeps enqueue
refresh jobs from current eligible sources. Current validity is computed from the
canonical sources and lifecycle projections; it is not duplicated in the derived
record. Reverse derived-view membership comes from `derived_memory_sources`, not a
capped lifecycle-state list. Stable preferences do not decay with age; episodic
history uses age only as a relevance score, and corrections receive a shorter
relevance half-life without being deleted. Task-conditioned query ranking remains
deferred and is not represented as a supported query contract.

Run `make memory-eval memory-lifecycle-eval memory-optimization-eval`.
The original baseline and paired evaluator are synthetic evidence. Native pgvector
precision/resource tests remain in the intentionally deferred persistence suite.
No experiment coverage is promoted; see the memory revalidation implementation report.

## memory controls default-off controls

`control_contracts.py`, `control_service.py`, `control_repository.py` and
`control_tools.py` add exact actor/project-scoped lexical search, fetch, kind
topics and untrusted pending suggestions. Explicit hosts may register four tools;
no chat/provider dispatcher registers them automatically. `memory_agent_tools_enabled`,
`memory_user_management_enabled` and `memory_user_mutations_enabled` default false,
require memory/schema-3 selection, and do not require admission because proposals
and review never admit knowledge. HTTP control composition additionally requires
an installed `memory_control_host` with a source resolver/lease and project mapping;
none is installed by default. The `/memory` UI uses the existing authenticated proxy
and a separate `MEMORY_USER_MANAGEMENT_ENABLED=false` server gate.

Authenticated recent-user forget uses canonical lifecycle CAS/validity epochs and
one atomic receipt transaction. Current owner/actor/project authorization remains
required, but expired or source-revoked historical knowledge may still be suppressed
without becoming readable. Model tools cannot forget. Review/reject changes only
pending status. Revision always returns `unsupported_evidence_source` until an actual
confirmation issuer and atomic replacement design are supplied. Before registering a
model tool dispatcher, define durable host-owned run/tool-call invocation identity and
same-key recovery; model-supplied IDs remain disallowed.

Pending content expires after 24 hours and the authenticated scheduled-maintenance
pass purges expired bodies in bounded batches. The actor namespace retains at most
32 pending proposals and 256 non-forget operation receipts; forget receipts do not
consume that quota. All operation keys remain durable and are never pruned, so storage
growth and a safe compaction epoch remain operational concerns. Owner inventory/export
includes both tables; `PostgresControlRepository.erase_owner` requires the existing
owner fence for operator erasure. Cloud/backup physical deletion remains unverified.
See the [control ADR](../../../../docs/memory/mem-2-control-adr.md),
[report](../../../../docs/memory/mem-2-implementation-report.md),
[review remediation](../../../../docs/memory/mem-2-review-remediation-2026-10-30.md) and
[independent review handoff](../../../../docs/memory/mem-2-independent-review-handoff.md).
Run `make memory-control-eval`, `test_memory_control*.py` and opt-in native
`tests/persistence/test_memory_control_postgres.py`. Synthetic checks do not close
issuer/identity, physical-send, backup deletion, operation-ledger growth or live-model gates.

## Bounded offline proposals

`consolidation/` accepts only two bundled, hash-pinned synthetic corpora. It has
no runtime factory, episode reader, scheduler, API/tool, acceptance operation or
production enablement. Scope binds owner/application/workspace/project/actor
(including null)/client/purpose/session. Closed command/outcome/revision facts
produce pending procedure/lesson/conflict candidates with exact versioned edges.
Every read checks both current eligibility and typed entailment. Tool completion
is unsupported. A published correction permanently suppresses older inferred
assertions for that subject, even after the correction is withdrawn. Conflicting
user corrections remain unresolved. Supersession never merges unrelated commands.

`OfflineProposalRepository` and the opt-in
`persistence.postgres.consolidation.PostgresProposalRepository` use the same
transition algorithm. Migration 036 stores checkpoints/proposals/original-key
receipts atomically with a separate **synthetic** issuer authority and content-free
checkpoint heads. Native row/advisory locks and canonical owner deletion locks
serialize independent processes. Lost ACK reconciles by the original key; changed
payload conflicts. True process-death tests cover both sides of commit. Restoring
only derived checkpoints is detected against surviving authority heads. A live
source instance also rejects decreasing authority revisions. Restoring the whole
authority and DB across a cold restart still requires an external surviving epoch.
No native result authenticates real sources or establishes deployed erasure.

The fixed v2 generation `synthetic-source-v2:bounded-extractor-v2:pending-policy-v2`
is an explicit backfill namespace: new cursors and keys, no reset of the original
stream. Fresh frozen evidence at a regranted epoch can be proposed; old evidence
cannot revive. Forget and expiry suppress cached output and bounded explicit
maintenance removes proposal bodies while retaining content-free replay barriers.
Canonical owner fences also block the SQL adapter. Public fixture files and SQL
MVCC/backup retention are not private-data physical-erasure evidence.

Limits are four sources/page, 128 sources/corpus, 2 KiB/envelope, 16 KiB/page and
retained proposal content/stream, 64 proposals/receipts and 32 claims/stream,
five-second leases, two-second lock acquisition/commit/SQL budgets, and three
allowlisted generation identities across two corpus digests. Capacity denies
without pruning keys or tombstones.
Pending content expires no later than 24 hours after evidence observation.
No automatic retry, provider call or token use occurs in extraction.

`governance.ProposalReviewPreview` requires the canonical control service's current
project/source lease, exact authenticated request/actor and recent-user check.
It uses the canonical pure propose/review decisions without writing. Procedures have a
canonical content preview; lesson/conflict bodies remain typed beside a bodyless,
never-persisted canonical review ticket. This supports dry-run review CAS without
changing the controls' wire kinds, misclassifying lessons as decisions, or approving
memory. Cached/revoked suggestions cannot authorize a later review preview.

Run `make memory-consolidation-check memory-consolidation-eval`. V1's 12-case
shape benchmark is preserved. Additive v2 has 88 records, 14 scripted consumer
cases, eligible nullable/cross-app/actor scopes, regrant, contradictory corrections
and 65-source capacity pressure. Its four arms use the shared context builder;
the fresh consumer receives serialized cards only. Outcome accuracy, false support,
exact entailment and scope/source leakage are E1 synthetic evidence, not model
or independently held-out utility. The fixed-first arm is a synthetic heuristic,
not legacy fixed retrieval, whose schema cannot represent these project facts.
The local pilot compares no consolidation, deterministic pending proposals and exact
eligible source context through the shared chat/admission/attempt path. A canonical
fixed-memory comparator is explicitly unsupported for these fixture facts. An arm
is only reported measured when the attempt completes without a safety failure and
includes token counts marked reported or estimated; task rubrics, confidence, latency
and local no-charge status remain separate. No hosted fallback is available.

Generation identity is bound to the frozen source digest. V1 uses its original
source/extractor/policy identity. V2 uses either a separate V2-source/V1-policy
identity for explicit comparison or the V2-source/V2-policy backfill identity;
cross-corpus pairings are denied before claim or commit. Existing V1/V2 fixture
bytes and historical receipts remain unchanged. Diagnostics expose
`processed_source_positions`; receipt `proposal_count` is the post-batch live
proposal total.

The additive challenge manifest includes known unsupported tasks, poisoned claims,
natural-language ambiguity and exact source attribution. It is author-visible and
does not count as an independent holdout or task-utility result.

`make memory-consolidation-postgres-check` requires a disposable local
`PERSISTENCE_TEST_POSTGRES_DSN` with CREATEDB and pgvector; it uses the canonical
migration runner and creates isolated databases. Native lease acquisition and
expiry use PostgreSQL `clock_timestamp()` inside the locked transaction, independent
of worker clocks. Source observed/expiry semantics remain tied to the synthetic
fixture clock. `inventory_owner` reports content-free row counts; `purge_owner`
requires the retained canonical owner fence, deletes all of that owner's checkpoint
payloads without project lookup, preserves other owners, and retains shared-source
scope tombstones so stale derived rows fail closed. This does not cover MVCC history,
replicas, backups or cold restore of the full authority database. Do not point it at
user data.
`python -m personal_ai.evaluation.consolidation_quality --local-preflight` reports
local-runtime prerequisites without sending. An explicit `--local-case SESSION`
pilot uses only public synthetic pending cards and eligible source records, the
existing private local profile, normal chat assembler, admission and physical-attempt
accounting. It needs a pinned model/build/private socket and durable usage store; it
never falls back to hosted inference. The three attempted arms share 4,096
context/128 response tokens and a 30-second request limit. The canonical fixed-memory
arm is explicitly unsupported for these fixture facts. Real-model results remain
unmeasured when that infrastructure is absent.

See the [continuation decision](../../../../docs/memory/2026-11-03-consolidation-continuation-decision.md),
[latest evidence](../../../../docs/memory/2026-11-03-consolidation-continuation.md)
and [remaining dependencies](../../../../docs/memory/consolidation-development-blockers.json).


## Owner profile portability

`portability.py` defines a closed, bounded export of explicit profile values and
a read-only import preview. The private API requires recent builtin owner
authentication and `MEMORY_PORTABILITY_ENABLED` with user management enabled.
It reads the canonical profile under its owner deletion fence, rechecks the
snapshot after serialization and uses the existing profile writer for
revision-checked corrections. Export and preview have no model calls or storage
of portable files. Project knowledge export and import commit are unavailable.
See [owner controls](../../../../docs/memory/owner-portability.md).

## Terminal-step candidate inspection

`episodes.assess_terminal_steps` is a pure structural validator for an exact
original workflow plan and a minimal terminal receipt envelope. It returns
`structurally_supported` or a uniform content-free `unsupported` result. It
checks original key, scope/intent/source/step fingerprints, tool/effect, exact
successful attempt cardinality and topological order. It excludes failed,
canceled, uncertain and recovered/abandoned histories. No tool/query text or
step names appear in the projection; each candidate is at most 2 KiB, with at
most eight candidates from two input documents totaling at most 16 KiB combined.

This function cannot authenticate input. Consistent fabricated input can pass.
Candidates explicitly carry `structural_inspection_only`, unavailable completion
time and no independent verification. They must not be persisted or consumed
as authorized memory. There is no issuer, lease, admission, lookup, erasure,
context integration, runtime registration or enablement flag. Existing memory
behavior and fixed retrieval defaults remain unchanged. Run
`make memory-episode-candidate-check` and `make memory-episode-candidate-eval`.
The additive corpus measures consistency only; its reserved split is author-visible.
See the [development decision](../../../../docs/memory/2026-11-03-episode-plan-hardening.md).

## Experimental episode projection

`EpisodeService.capture` and `read` always return `disabled`. Host booleans cannot
enable the projection until a trusted issuer supplies monotonic source epochs and
the data joins the canonical memory lifecycle and deletion path. Migration 035 and
the repository adapters remain read-disabled experimental storage; they are not a
second accepted memory lifecycle. The authenticated local `forget` and `purge`
maintenance operations address only the exact owner/app/workspace/actor/client/
project namespace and do not resolve a live source project. They remove payloads,
retain original-key receipts, and write forgotten lifecycle projections where
available. Account-wide erasure orchestration and restore quarantine are not
registered. No export or model tool is registered. Run
`make memory-episode-check`; native SQL requires
`make memory-episode-postgres-check` with a disposable DSN. See the
[remediation report](../../../../docs/memory/2026-11-03-luna-remediation.md) for
the blocked issuer, lifecycle, producer, native and release gates.

## Sealed memory navigation research

`research/` is a private, default-off experiment over one hash-pinned public
synthetic corpus. Construct `MemoryNavigationResearch(FixtureAuthority(),
enabled=True)` explicitly in offline evaluation; no application factory, API,
agent tool, background worker or environment flag registers it. Its immutable
`ResearchQuery` wraps the server-built `MemoryQuery`; the synthetic source profile
is separate from canonical legacy and schema-3 admission. It never reads episode
projections or pending consolidation proposals. Production source adapters remain
unsupported, and legacy `fixed` code and defaults are unchanged.

The ephemeral cache retains bounded normalized terms, sanitized two-level topics,
leaf IDs and content/record/permission fingerprints. Exact owner, app, workspace,
actor, project, lifecycle, retention, source revision/epoch, sensitivity and
trusted metadata/time filters precede ranking. Complete eligible universes are
capped at the canonical query's candidate limit (at most 100); overflow returns
`incomplete`. Topics are navigation data, never grants. Browse, paged leaf fetch,
packing and locked scripted consumption independently resolve current authority.
Terminal tombstones prevent same-identity regrant. An authority-instance nonce
rejects prior-process caches and dependencies; it does not authenticate a cold
restored issuer. Public fixture bytes remain available after synthetic purge;
no private-data physical erasure is claimed.

Lexical recall is deterministic. The semantic adapter consumes complete canonical
`MemoryRetriever` results with matching universe, scope, content and embedding
identities; it makes no embedding calls. Fusion/reranking have explicit fake-vector
contract tests, excluded from benchmark results. Real semantic/hybrid benchmark
arms are unsupported without genuine embeddings. The corpus's project facts also
make legacy `fixed` unsupported; that denominator is retained. No model utility
is measured.

Fixed, request-aware and adaptive memory allocations narrow existing
`ContextBuildPolicy` ceilings and use `ContextBuilder` with original source refs,
permission dependencies, historical authority labels and atomic conflict groups.
Required current context is packed first. The counter is the local fixture word
estimate, never a provider count. Consumption accepts only matching serialized
source cards and has no model/command dispatch callback. There is no production
physical-send boundary for this experiment.

Limits: 128 corpus records, 256 KiB corpus/cache, 4 KiB/record, 128 terms/record,
64 characters/term, 32 topics, depth two, eight leaves/page and one extra page,
16 selected records, 2 KiB queries, two-second original deadlines, leases capped
at five seconds (and always the remaining request deadline), 1,024 memory and
4,096 total fixture token units. Full eligible context may exceed top-K but must
fit completely under the same builder ceilings. Unknown authority, stale cache,
cancellation and timeout retain explicit statuses without payloads.

Run `make memory-navigation-check memory-navigation-eval`. The separate
`memory-navigation-postgres-check` requires a disposable test DSN and runs existing
canonical pgvector and verified-knowledge contracts; it does not establish a new
native index/source integration. Disable the constructor gate and discard caches
for rollback; no canonical data or migration changes. See the
[hardening decision](../../../../docs/memory/2026-11-04-retrieval-plan-hardening.md)
and [implementation receipt](../../../../docs/memory/2026-11-04-retrieval-implementation.md).

## Longitudinal offline research

`research/experiments/` defines bounded typed manifests, attempt receipts,
content-addressed local packages, an append-only research decision chain and pure
canary/rollback proposals. It has no application registration, environment flag,
provider transport or effective-policy writer. `fixed` remains the runtime default;
episode capture/selection and pending-proposal admission remain unavailable.

Run `make memory-research-check memory-research-eval` with the backend virtualenv
on `PATH`. The explicit offline command writes an immutable package below ignored
`artifacts/memory-research/<run digest>/<invocation id>/`, including the protocol
before measurement, every requested arm/step/repetition, status denominators,
resource observations, report, decision and blocked canary/rollback requests.
Preserve `package.json` and the run digest as external integrity anchors. The local
`decisions/` chain retains unsuccessful hypotheses; it is bounded to 128 entries
and never prunes failures automatically. These public synthetic artifacts contain
no private source payloads and can be archived or removed explicitly. They do not
establish production retention, native durability or owner deletion semantics.

For independent-process reproduction, run
`make memory-research-replay MEMORY_RESEARCH_PACKAGE=/absolute/path/to/package`.
Verification checks the package, complete receipt grid, source/model/environment
identity and scorer, then executes two fresh semantic replays. Hashes are custody
checks, not signatures or authorization. Source drift requires an additive study
generation; never update an earlier accepted lock to obtain a pass.

The source-only and scorer-only fixtures contain 48 author-visible trajectories
across transfer, revision, correction, rights, poison and resource families. Each
has at least three time steps and separate simulated sessions; 24/12/12 splits
include author-visible validation and challenge slots. `inspect_challenge`
validates external source packages of 12–96 tasks without installing a source or
certifying independence. All splits were inspected during implementation.

A later action is observed by the existing hermetic original-intent task host,
not inferred from a driver's success label or historical receipt. The consumer
sees packed cards only. Navigation uses a separately sealed fixture authority and
the existing lexical/topic/adaptive engine and canonical `ContextBuilder`.
Canonical knowledge and control lookup use the existing admission, selection,
packing and final-consumption guards in a separate compatible source cohort.
Legacy fixed, real semantic/hybrid and pending consolidation comparators retain
unsupported rows where their source contracts cannot represent these facts.
Pending diagnostics cannot become trusted context. Existing consolidation
commands remain the separate diagnostic study for its own sealed source profile.

The preregistered six contrasts use final scenario outcomes and fixed-seed paired
cluster bootstrap intervals. Repetitions and setup steps do not inflate sample
size. Explicit lookup calls consume the same task-tool budget; full history must
fit the same context ceilings in full. Failed/unsupported attempts retain work
counters. Reported tokens are fixture word estimates; actual model tokens, billed
costs and native resources remain null. There is no statistical-significance,
blind-acceptance or real-model utility claim.

Decision proposals require verified custody; offline canary eligibility additionally
requires a distinct trusted reviewer supplied by an independent host. No reviewer
issuer is installed here. Imported metadata cannot authorize a review, lower a
veto or change model space. A protocol-only model manifest can describe an intended
owned loopback trial, but executable study manifests reject all transport modes.
See [decision authority](../../../../docs/decisions/0026-offline-memory-research-custody.md)
and [implementation evidence](../../../../docs/memory/2026-11-04-longitudinal-implementation.md).

Retained-byte counters describe serialized synthetic knowledge records and
rebuildable derivative indexes. Common immutable fixture bytes are identified in
the dataset manifest; these counters do not measure process RSS or native database
storage. The initial study source lock is retained unchanged. An additive second
source generation strengthens package-summary/decision verification without
changing corpus bytes, scorer, protocol or semantic outcomes.
