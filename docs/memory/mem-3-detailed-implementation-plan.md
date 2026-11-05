\# Personal AI System — MEM-3 Detailed Implementation Plan

\*\*Phase:\*\* MEM-3 — Selected Completed-Task Episodes    
\*\*Status:\*\* Proposed implementation plan; NOT an implementation authorization or production enablement approval    
\*\*Prepared:\*\* 2026-11-03 (America/Los\_Angeles; repository inspected 2026-11-04 UTC)    
\*\*Pinned repository:\*\* jasonkli21/personal-ai-system, main at 42f00b0f93b0987f615657d4d8b9c145c6c6b016    
\*\*Execution target:\*\* One bounded, default-off E1 experimental implementation by Sol Medium, followed by independent Sol High review.    
\*\*Primary program basis:\*\* Attached Integrated Harness Excellence Roadmap v3.1 (2026-11-03), Part II MEM-3, program-wide ownership/gates; docs/memory/memory-architecture-and-research-roadmap.md, Stage 3\.    
\*\*Authority order:\*\* Current code/contracts/migrations/tests \> dated evidence \> accepted ADRs \> architecture/roadmap \> this plan.

\#\# 0\. Executive decision and authorization boundary

Build a \*\*selected, evidence-linked, metadata-first episodic memory projection\*\* over eligible, already-completed PAS-controlled tasks. It should let an authorized future task locate a previously observed step and understand its operation, normalized outcome, evidence reference, temporal/project limitations, and current validity without archiving private tool input/output or hidden reasoning.

This is not a new agent execution engine, full observability archive, generalized autonomous memory writer, cross-agent memory federation, or offline dreaming service. Episodes are historical/advisory records, never live source authority or independently verified procedures. Existing personal memory, schema-3 project knowledge, MEM-2 controls, PI-5 retrieval/context assembly, HXE-3 workflows, provider admission and memory lifecycle remain canonical.

\*\*Freeze:\*\* The integrated roadmap explicitly freezes MEM-3+ until owner unfreeze, readiness ADR, evidence-aware scope and narrow independent review. Creating this plan and prompts does not itself lift that freeze. A subsequent direct instruction to implement this exact default-off E1 slice may constitute the explicit owner unfreeze \*\*for source-only/offline code and hermetic fixtures only\*\*, if recorded before edits. Otherwise stop for a decision. No such instruction authorizes live user-data capture, broad tool traces, disclosure, automatic promotion, deployed operation or cross-app sharing.

\*\*Desired outcome:\*\* A safe path from a trusted, terminal, provenance-bearing workflow attempt to a durable, revocable episode and bounded scope-safe lookup. Any missing issuer, event, permission, branch, retention or verification fact must result in rejection or an explicitly unverified/unsupported state, not guessed truth.

\#\# 1\. Repository baseline and gap (verified at pinned revision)

\| Boundary \| Present today \| MEM-3 implication \|  
\| \--- \| \--- \| \--- \|  
\| HXE-3 workflow contract \| backend/src/personal\_ai/contracts/workflow.py has workflow-v1 RunSpec/StepSpec, terminal run states, per-attempt states and optional AttemptOperationBinding \| Reuse run/step/attempt IDs and nonsecret digests; no second run/step/attempt state machine \|  
\| HXE-3 storage \| migrations/034\_workflow\_runs.sql and persistence/postgres/workflows.py persist a scoped run/original key, immutable binding, bounded progress tail and durable terminal outcome \| Treat canonical row as evidence origin; progress tail is not a complete event log; never derive full history from it \|  
\| HXE-3 authority \| docs/decisions/0025-workflow-lifecycle-authority.md; default-off foreground, local read-only retrieval DAG; uncertain dispatched attempts do not auto-retry \| Initially accept only the implemented local profile and observed terminal attempts; reserve/dispatch/uncertain are not verified success \|  
\| MEM-1 knowledge \| memory/knowledge.py schema-3 procedure/project\_decision; source guard; source-epoch fences and context revalidation \| Keep episodes separate from verified knowledge and from legacy episodic\_observation; do not auto-create verified-active procedures \|  
\| MEM-2 controls \| Bounded read/propose/review/reject/forget, explicit user forget receipts; revision issuer/atomic replacement and production tool host absent \| Do not graft episode mutation onto unsupported revision path or register model tools by default \|  
\| Memory storage \| Postgres/pgvector canonical memory and provenance; Dynamo conversations/jobs/leases; lifecycle/dependency graph \| Add the smallest scoped Postgres projection and guarded source edges within memory ownership; no second database or scheduler \|  
\| Evaluation \| MEM-0 locked synthetic baselines, MEM-1 paired task fixtures, MEM-2 control suite; HXE-2 trace/evidence packaging \| Add versioned episode-specific fixtures and ablations; preserve all existing locked corpora, digests, graders and nonpromotion decisions \|  
\| Readiness \| docs/current-state.md, MEM-2 blockers and PI cross-phase registry keep independent/live/native gates open \| E0/E1 may be an implementation candidate; production remains NO\_GO \|

Important specifics:  
\- Latest inspected commit 42f00b0 concerns release-evidence hardening, not an acceptance of MEM-0/1/2 or HXE-3.  
\- HXE-3's current source snapshot and operation digest prove binding to a local tool invocation, \*\*not\*\* an issuer-backed future authorization, semantic support for arbitrary claims, or external task success.  
\- HXE-3 author evidence reported native Postgres run tests for the original slice, but subsequent remediation's changed attempt-binding/recovery tests were unable to rerun native Postgres in that session; current-state retains the remaining verification blocker. A new session must inspect exact HEAD, verification reports and actual environment before deciding which test evidence can be claimed.  
\- MEM-2 blockers include source/lease, trusted host retry identity, source-fence/receipt growth, physical erasure, restore, real-model utility and independent acceptance. Do not silently close them by recording episodes.

Primary repository references:  
\- docs/current-state.md  
\- docs/memory/mem-2-blockers.json  
\- docs/memory/mem-2-review-remediation-2026-10-30.md  
\- docs/memory/mem-1-contract-adr.md  
\- docs/decisions/0025-workflow-lifecycle-authority.md  
\- docs/harness-excellence/2026-11-03-hxe3-remediation.md  
\- backend/src/personal\_ai/contracts/workflow.py  
\- backend/src/personal\_ai/persistence/postgres/workflows.py  
\- backend/src/personal\_ai/memory/{knowledge.py,knowledge\_service.py,dependencies.py}  
\- backend/src/personal\_ai/persistence/migrations/028\_verified\_memory\_knowledge.sql, 030\_memory\_control.sql, 034\_workflow\_runs.sql.

\#\# 2\. Scope, non-goals and evidence tiers

\#\#\# In scope for one coherent E1 slice

1\. Author a readiness/ownership/privacy ADR, scope/retention matrix and precise source-eligibility contract.  
2\. Implement typed, versioned \*\*episode metadata\*\* and trusted event eligibility rules for a selected subset of terminal PAS-controlled foreground local read-only workflow attempts.  
3\. Create a minimal Postgres persistence and guarded dependency projection integrated with canonical memory ownership, plus a behaviorally equivalent hermetic repository.  
4\. Capture or materialize only after durable canonical run/attempt receipts exist, with idempotent original keys and a crash-safe reconciliation path. Reuse existing SQL transactions and source guards.  
5\. Add hard-scoped exact/bounded lookup and fetch with current rights, branch/revision, lifecycle/retention and source revalidation at disclosure; expose internally first.  
6\. Provide opt-in bounded adapter invocation and explicit operator diagnostics. No automatic capture for all tasks.  
7\. Enforce privacy budgets, content-free receipts, expiration, source deletion and anti-resurrection tests.  
8\. Add paired task lookup/effectiveness evaluation; preserve locked old baselines and classify synthetic-only evidence accurately.  
9\. Update owning docs, living current state, release gates and rollback instructions.

\#\#\# Out of scope

\- Raw hidden chain-of-thought, prompts, transcript archives, arbitrary tool arguments/results, raw logs/stdout/stderr, secrets, API tokens, PII, health/finance/private domain records or unbounded trace indexes.  
\- Inference/model/provider calls, new embeddings, semantic clustering, topic hierarchy, general document ingestion, user-facing auto-memory, agent self-certification, automatic procedure/lesson promotion, MEM-4 dreaming.  
\- A competing workflow ledger, new background worker, streaming fan-out, universal event bus, generic scheduled workflows, autonomous action permissions, coding-harness terminal/Git sessions, cross-agent or cross-project grants.  
\- Relaxing MEM-1/MEM-2, Phase 36, PI-5/PI-7, HXE-3 or HXE-4 enablement gates.  
\- General-purpose public SDK/API/MCP episode disclosure in this phase absent a separately reviewed issuer-bound physical-send contract.  
\- Production retention, cloud backup deletion, native distributed restore and resource claims without environment evidence.

\#\#\# Evidence classification

E0 \= schema/architecture/security invariants; E1 \= hermetic synthetic and local code; E2 \= separately installed native local storage/real local operations; E3 \= approved live peers/providers/sources; E4 \= deployed identity, privacy, deletion, restore, billing; E5 \= real longitudinal utility. The initial implementation target is \*\*E0/E1 only\*\*. An independently reviewed native PostgreSQL subset may be recorded as E2 for only the exact checks executed. No label may imply higher acceptance.

\#\# 3\. Trust, privacy and episode eligibility

\#\#\# 3.1 Definitions

\*\*Source execution:\*\* An authoritative PAS workflow row containing one terminal run and a bounded attempt history.    
\*\*Observed outcome:\*\* A trusted tool handler returned a known result and the canonical persistence transition recorded it. A run state of succeeded is still not proof of task-level correctness.    
\*\*Verified outcome:\*\* A separate, trusted verifier or exact eligible receipt establishes a narrowly specified claim with issuer, test identity, scope, source revision and time. The verifier must not merely echo model/tool prose.    
\*\*Episode:\*\* A redacted immutable pointer plus bounded descriptive metadata about a selected step; its authority is historical and restricted to the verified facts actually evidenced.    
\*\*Selection:\*\* A trusted opt-in host action that chooses which terminal attempts qualify; not a model decision.    
\*\*Revocation:\*\* A source, grant, project, user or retention change that blocks all future episode retrieval and context reuse.    
\*\*Physical erasure:\*\* Removes permitted payload/index copies, subject to independently evidenced storage/replica/backup semantics; logical tombstones remain for anti-replay.

\#\#\# 3.2 Required eligibility gates, in order

1\. Trusted authenticated owner/application/workspace/acting-user, client/purpose and project mapping from current request context; never model-supplied or inferred from raw UUID.  
2\. Explicit experimental capture enablement, exact source profile and non-sensitive allowlist (initially only local synthetic public test corpus).  
3\. Canonical PAS-owned workflow exists, same actor and source branch, verified original-intent digest, immutable attempt operation binding and trusted registered tool ID/version.  
4\. Run/attempt snapshot is terminal and durable. Only attempts with a \*\*recorded observed result\*\* (succeeded or known failed) are eligible for searchable episode status. Reserved, dispatched-only, abandoned and uncertain attempts are excluded from success; optionally retain a content-free audit rejection reason, not a retrievable lesson.  
5\. Correct step/run causal ordering and dependency completion, with no fabricated predecessor; progress tail cannot establish missing predecessors. Multiple retries must reconcile by attempt ID and original intent.  
6\. Issuer/source IDs, fingerprint/revision/epoch, permission dependencies, grant version and retention terms are resolvable under a lease that fences the relevant mutations across capture commit. In the offline fixture this may be a hermetic lock; in production a recoverable issuer-backed lease is mandatory. If not available, deny.  
7\. Content allowlist and redactor pass before persistence; metadata-only default. The capture service must not accept raw tool payloads, user prose, free-form explanation, arbitrary paths/URLs, secrets or the model's self-reported outcome.  
8\. Per-namespace, per-run and per-day budget checks pass; duplicate idempotent admission must not charge twice; overflow fails closed.  
9\. Captured fields are revalidated at commit and available for every later fetch/packing/send boundary.

\*\*Known failure episodes:\*\* A completed known failure may be represented solely as a historical failed attempt with an observed receipt. It must never be labeled a verified successful procedure. A canceled or uncertain run may contain a prior observed step; unless authorization and causal boundaries are independently proven, initial policy excludes the entire run to simplify correctness. Document this conservative choice and fixtures.

\#\#\# 3.3 Data classification and retention

Define a policy matrix by source kind, sensitivity, actor, destination and expiration. For initial E1: only explicitly fixture-marked synthetic/public local retrieval metadata; no payload references except stable opaque source/receipt IDs. Retention should be short and finite (e.g. \<=30 days, configurable downward within bounded limits) with an immediate block on expiry/revocation. Put strong limits on record size (e.g. \<=2 KiB canonical JSON), episode count per run (\<=8), per scoped namespace ceiling (e.g. \<=128), source-edge fan-out (bounded), query/fetch result size, request deadline and stored diagnostic bytes. These are candidate limits; the ADR must reconcile with actual storage/test costs and justify exact values before freezing.

Content-free anti-replay markers and source-fence tombstones need an explicit durable-capacity policy. Never prune them simply to make quota tests pass. If safe compaction is unavailable, stop admitting new episodes at a bounded limit and record a remediation blocker. Retention must not resurrect an old record from a stale snapshot.

\#\# 4\. Typed contracts and proposed schema (design, not drop-in source code)

Use enduring capability names in production source and test symbols. Historical docs/handoffs may use MEM-3. Consider a new contract module such as memory/episodes.py plus a small source adapter near the workflow boundary; avoid naming active code/tests after phase numbers.

\#\#\# Proposed immutable EpisodeRecord v1

\| Field group \| Required content \| Validation \|  
\| \--- \| \--- \| \--- \|  
\| Identity \| schema\_version, episode\_id, original capture key, policy version, event fingerprint \| Stable/deterministic, strict no-extra-fields, versioned \|  
\| Scope \| owner, exact nullable acting user, app, workspace, project, branch, permitted purpose/client \| Trusted server-only, never from model/tool arguments \|  
\| Canonical execution \| run\_id, original intent digest, step name/id, attempt\_id, tool ID/version, read-only effect, operation binding/source digest \| Must match authoritative workflow row and immutable receipt \|  
\| Outcome \| observed category, observation time, completed time, narrow evidence status, verifier kind/receipt ref, explicit limitations \| No assistant-provided verified-success field; uncertain cannot be success \|  
\| Source rights \| opaque source ID(s), revision/fingerprint/epoch, issuer identity, grant and permission dependencies \| Exact, bounded, linked reverse dependencies, revalidatable \|  
\| Privacy \| classification, redaction policy version, retention deadline, size budget \| Metadata only E1; every field allowlisted \|  
\| Lifecycle \| immutable original plus canonical lifecycle validity state/epoch, tombstone or source suppression reference \| Reuse memory lifecycle/revocation authority, no second independent state machine \|

The physical schema may split immutable episode metadata, normalized source edges and bounded index keys, but avoid a separate memory authority. Use a migration after the current latest migration (034 at the pinned revision; renumber after rechecking HEAD). Do not embed raw tool outputs or snapshots. Add uniqueness on exact scope+original run/step/attempt+policy/capture key, plus an immutable payload fingerprint. Preserve additive readers/migrations and v1/v2/schema-3 compatibility.

If a native lifecycle implementation cannot safely represent the episode's validity semantics, introduce a minimal typed adapter into the \*\*same authoritative lifecycle transition/projection path\*\* with independent tests, or keep episodes as an opaque read-disabled experimental projection until it can. Do not implement a parallel ad hoc active/forgotten state field.

\#\#\# Example normalized view (fictional metadata only)

\~\~\~json  
{  
  "schema\_version": "episode-v1",  
  "tool": "retrieval.query.v1",  
  "effect": "read\_only",  
  "step": "lookup",  
  "observed\_outcome": "succeeded",  
  "verification": "observed\_tool\_result\_only",  
  "source\_snapshot\_digest": "\<64-hex\>",  
  "evidence\_reference": "\<opaque-attempt-id\>",  
  "limitations": \["historical", "local synthetic source"\]  
}  
\~\~\~

This illustration intentionally omits identity and provenance fields that the trusted host must bind.

\#\# 5\. Capture, transaction and recovery design

\#\#\# 5.1 Ownership seam

Recommended flow:

1\. HXE-3 completes and durably commits a PAS workflow transition and nonsecret attempt receipt; it remains the single canonical execution state.  
2\. A separate \*\*trusted opt-in episodic capture service\*\*, owned by MEM, reads an immutable eligible terminal workflow snapshot through a narrow read adapter. The capture service must not accept an untrusted client-supplied copy of a receipt.  
3\. Under a canonical source authorization/lease and PostgreSQL transaction, validate exact attempt binding and source dependencies, compute deterministic capture identity, write immutable episode+edge projection and the content-free idempotency marker together.  
4\. On an uncertain commit, resolve by the original capture key; never generate a new key. On changed intent/payload under the same key, conflict. Re-reading a valid duplicate returns original outcome without modifying provenance or charging capacity.  
5\. Re-check scope/rights/source revision/retention at selection, fetch, context assembly and any eventual physical disclosure. Source withdrawal/forget invalidates all reverse-dependent episodes and cached/indexed projections.  
6\. Operator rollback disables capture and selection separately, preserves canonical HXE-3 receipts, original memory records, tombstones and anti-replay state.

\*\*No silent cross-DB transaction:\*\* Both workflow run and episode projection may use PostgreSQL, but the source issuer's revocation or other records may live elsewhere. A same-database read/lock is not proof of an external issuer lease. For E1, use a known fixture origin with explicit limitations. No new Dynamo worker is required; a bounded, manual/synchronous capture of completed runs is sufficient. If an outbox is necessary for recovery, use an existing canonical durable intent/job pattern, with stable keys and bounded scans, not a new scheduler.

\#\#\# 5.2 Crash/retry state matrix

\| Failure point \| Required behavior \|  
\| \--- \| \--- \|  
\| Before selection or canonical run terminal \| No episode; no inference from in-flight progress \|  
\| Between validation and source-lease acquisition \| Revalidate under lease; deny if revision changed \|  
\| After duplicate check but before commit \| Transaction rollback; same capture key can retry \|  
\| Commit succeeds, ack lost \| Same-key retry reads exact committed record/receipt \|  
\| Same key, altered policy/scope/attempt/body \| Conflict; do not overwrite or mint a new claim \|  
\| After source revoke or user forget \| Future lookup/packing denied; dependent copies erased or quarantined, durable denial marker retained \|  
\| Canceled/uncertain/replayed HXE-3 run \| No verified episode from uncertain dispatch; no duplicate effect \|  
\| Stale database/backup restore \| Quarantine until monotonic revocation/forget/original-key authority reconciles; native restore gate remains open \|

\#\# 6\. Search, fetch and contextual reuse

Expose an internal trusted service first, conceptually:

\- search\_episodes(scope, authorized\_project, query, filters, max\_results, deadline)  
\- fetch\_episode(scope, episode\_id, expected\_source\_revision, deadline)  
\- forget\_episode(scope, episode\_id, expected\_epoch, explicit\_authority) through existing memory lifecycle/erasure

Search should begin with hard scope, purpose, actor, project/branch, current source rights, expiry, origin, lifecycle and verification-state filters. For this phase use narrow exact/lexical metadata lookup (tool, step category, known task labels), not an embedding-driven search that risks indexing forbidden text. Return bounded results with “historical, not current truth” labels, exact source references, age/expiry and a clear partial/truncated status. Do not imply complete search if the query stops at a fixed candidate cap. A guessed episode ID must not reveal foreign record existence.

If an experiment uses episodes in the shared context builder, route through existing MemoryRetriever/ContextBuilder integration and ContextPermissionDependency revalidation; do not independently append context strings. A selected episode occupies a measured token budget and does not outrank fresh domain data or verified user corrections. No default memory selection algorithm change or automatic episode injection is required. A model-facing lookup tool can be added \*\*only\*\* behind a separately trusted host registration with scope binding and robust per-call budget; the first E1 vertical slice may demonstrate the same service from a synthetic operator harness instead.

Memory can suggest checking a prior step; it must never authorize re-running the operation, changing project state, or bypassing HXE-3 permission checks. The consumer always obtains fresh source/tool authority.

\#\# 7\. Deletion, retention and privacy verification

\- Couple source dependency edges to the existing revocation/forget graph so source expiry, branch replacement, project grant loss, user forget, account erasure and source deletion invalidate retrieval before ranking and again at disclosure.  
\- Remove any projected searchable text/index/cache copy on the same effective suppression path. If a purge is asynchronous, immediately hide suppressed rows and retain durable pending-erasure receipts.  
\- For source withdrawal and account deletion, test traversal from source \-\> episode \-\> index/selection \-\> packed context and exports. HXE-4 portability must \*\*not\*\* include episodes by default; any later export requires a separate manifest and consent contract.  
\- Metadata-only must be enforced by strict schema and negative tests, not by a best-effort generic string redactor. Test literal secrets, base64-ish strings, URLs, file paths, tool payload blobs, system-message fragments, Unicode/control chars and nested extras.  
\- Retention must include physical row/edge cleanup on a bounded, existing maintenance seam where safe, with resumption and crash recovery tests. Distinguish local logical deletion from replica/backup physical deletion (E4).  
\- Register a retention/storage blocker for keys/tombstones if monotonic safe compaction cannot be demonstrated.

\#\# 8\. Implementation work packages and sequencing

\#\#\# WP0 — Preflight, readiness and plan hardening

\- Pin current HEAD and git status. Read docs/README.md, AGENTS.md, memory/workflow READMEs, current-state, MEM-0/1/2 evidence, HXE-3 ADR/remediation and the attached integrated roadmap. Reconcile every assumption with code; record differences.  
\- Write a readiness ADR with unfreeze scope, candidate source, trust matrix, data fields, retention budget, unsupported surfaces, error taxonomy, and acceptance tiers. List inherited gates without pretending they are closed.  
\- Independently critique this plan in the same implementation session; simplify or tighten based on current code. Do not spawn subagents. If an irreconcilable authority/lease hole blocks even E1, stop after ADR and a scoped non-mutating proposal.

\#\#\# WP1 — Contracts and deterministic policy

\- Implement strict episode schema/policy and explicit eligibility rejection reasons.  
\- Validate exact immutable run/attempt binding; distinguish observed success from independent verification and historical facts from current source truth.  
\- Disallow arbitrary tool text/hidden reasoning and unknown effect classes.

\#\#\# WP2 — Minimal persistence

\- Add additive migration, normalized source edges, unique original keys, payload fingerprint, hard quotas and lifecycle integration.  
\- Add in-memory fake matching transaction, CAS, cap and suppression semantics; source guard ownership remains canonical.  
\- Ensure old schema-1/2 and schema-3 readers and all historical data are preserved.

\#\#\# WP3 — Capture/reconciliation adapter

\- Read only trusted terminal workflow snapshots; implement a deterministic one-run selection/capture path for the initially supported local read-only profile.  
\- Reuse canonical run/step/attempt evidence and source lease; no generic event bus or new distributed scheduler.  
\- Build duplicate, conflict, cancel, crash-before/after-commit and stale-source tests.

\#\#\# WP4 — Scoped search/fetch/forget

\- Implement server-bound internal lookup with hard filters, currentness, expiry and privacy budget.  
\- Integrate with existing dependency/revalidator and shared context pipeline only where justified by the E1 paired task.  
\- Expose minimal inspection reason codes and explicit truncated/unsupported results. No external public routes by default.

\#\#\# WP5 — Evaluation

\- Freeze a new deterministic corpus \*\*before examining scores\*\* with \>=30 distinct hand-reviewed synthetic cases and holdout split. Families: successful terminal step, known failure/uncertain, retries/partial ordering, wrong actor/project/branch/source rights, poison/sensitive payload, revocation/deletion/retention/storage limits. Include positive/negative twins.  
\- Compare: no episode, eligible full historical context (where safe/feasible), existing fixed MEM-0, MEM-1 verified knowledge, knowledge+MEM-2 controls, and opt-in episodes. A fixture “gold episode” may be diagnostic only.  
\- Measure exact eligible capture precision, unsupported claim rate, lookup recall/precision, task rubric pass/fail, false inclusion, storage bytes/growth, token/prompt budget, p50/p95 lookup latency, query count and zero unauthorized inclusion. Label scripted retrieval E1 proxy, never real agent utility.  
\- Where useful, include a two-session workflow demonstration in which a known past step is found and correctly qualified by version/rights; a changed source causes denial/abstention.  
\- Preserve all old fixture bytes, digests, evaluation locks, thresholds, nonpromotion decisions and comparator behavior. Use additive locks/source identity only.

\#\#\# WP6 — Tests, docs and evidence

\- Add behavior-named unit/security/fixture tests. Add native Postgres migration/transaction/race/erasure tests using the existing isolated database fixtures; if no environment, record BLOCKED, not PASS.  
\- Run focused memory/workflow/security/eval gates and available broad offline fenced checks; no unapproved providers, cloud or external calls.  
\- Update docs/current-state.md, docs/README.md task route if needed, owning memory/workflow READMEs, ADR, evaluation contract, report and blockers with exact commands and results. Keep active filenames, public fields and tests free of phase IDs except immutable compatibility names or historical evidence.  
\- Request separate independent Sol review of both implementation and plan assumptions.

\#\# 9\. Required test and adversarial matrix

\| Area \| Minimum cases \|  
\| \--- \| \--- \|  
\| Capture eligibility \| Missing/forged terminal receipt; reserved/dispatched/uncertain/abandoned, observed known failure, cancellation, wrong or legacy missing operation binding, mismatched source/step digest \|  
\| Provenance \| Wrong tool ID/version/effect, reversed causal order, duplicate attempt, fabricated outcome verifier, unbound source revision, stale project/branch, stale issuer/expiry \|  
\| Isolation \| A vs B vs null actor, cross-owner/app/workspace/project/client/purpose, guessed IDs, revoked membership, same-owner different app \|  
\| Privacy \| Full tool result/secret/stdout/prompt injection in metadata, nested unknown fields, oversized strings, Unicode/control input, untrusted source text treated as instructions \|  
\| Retry/concurrency \| Same-key identical retry, changed-key/body collision, two workers, lost lease, before/after-commit crash, restore replay and no double budget charge \|  
\| Lifecycle \| Source revoke before capture/selection/disclosure, forget, supersede, account deletion, expired purge, cached/packed index invalidation, backup restore blocked \|  
\| Quotas \| Per-event bytes, source-edge cardinality, per-run, namespace count, read deadline, query cap, retained anti-replay ledger saturation \|  
\| Compatibility \| Memory v1/v2 and knowledge schema-3 behavior unchanged, HXE-3 terminal semantics unchanged, MEM-2 forget controls unchanged, legacy records unaffected \|  
\| Evaluation \| Held-out origin and grader audit, counterexample twins, baseline integrity, matched budgets, known failure retained without score laundering \|

Hard security exit is zero unauthorized inclusion, unauthorized writes, forgotten resurrection, trusted-verification forgery and secret payload persistence in all executed E1 tests. Correct denial is success for negative cases.

\#\# 10\. Verification commands and evidence handling

Confirm current Makefile and environment before running; never claim an unexecuted command passed.

Suggested existing commands:  
\- make backend-lint  
\- make naming-policy-check  
\- make workflow-check  
\- make workflow-postgres-check (only with approved disposable PG/pgvector fixture)  
\- make memory-task-eval  
\- make memory-knowledge-eval  
\- make memory-knowledge-causal-eval  
\- make memory-control-eval  
\- make memory-eval  
\- make provider-isolation-check  
\- make backend-test-offline (only under repository-approved native egress fence; note preexisting baseline failures)  
\- git diff \--check

Introduce a small capability-named target such as make memory-episode-eval if warranted. Run focused episode unit and native tests with exact test paths. Report pass/fail/blocked, fixture identity, run configuration, interpreter/DB/runtime, resource values versus estimates and inherited unrelated failures. Do not alter frozen tests, timeouts or expected scores to manufacture green output. Avoid live/paid inference and privacy-bearing transport.

\#\# 11\. Acceptance gates and explicit NO\_GO

\| Gate \| E1 implementation candidate \| Required before enabled product \|  
\| \--- \| \--- \| \--- \|  
\| Readiness ADR \+ explicit narrow authorization \| Recorded and independently challengeable \| Owner approval for actual captured profile \|  
\| Selected terminal provenance \| Hermetic exact run/attempt receipt checks \| Trusted issuer, verified live rights, full source/branch and currentness \|  
\| Privacy/scope/retention \| Metadata-only allowlist, caps, deletion and negative tests \| Authenticated deployed identity, real source issuer, material erasure/restore \|  
\| Atomicity/replay \| SQL/fake idempotency, content-free durable anti-replay, crash negatives \| Monotonic original keys and revocation across restore/workers \|  
\| Retrieval/context \| Hard filter and source recheck, zero simulated leaks \| Physical disclosure linearization with revoke and downstream client limits \|  
\| Utility \| Honest E1 task-proxy comparison \| Real E2/E3 model tasks and E5 longitudinal held-out lift \|  
\| Independent review \| Separate Sol session disposition pending \| Closure of relevant P0/P1 findings and inherited phase gates \|  
\| Deployment \| All new capabilities default-off; no data migration enabled by default \| PI/HXE/MEM/Phase 36 native, cloud, cost, IAM, backup/deletion gates \|

\*\*At the end of implementation, record three different statuses:\*\* (1) code complete or partial, (2) E0/E1 / native evidence actually obtained, (3) independently accepted/production promotable (default: NO\_GO). An E1 candidate may be useful even when production gates remain open; it must be impossible to accidentally enable sensitive capture by setting a single boolean.

\#\# 12\. Rollback, migration and maintenance

Immediate rollback: turn off capture and episode selection independently; remove any host/tool registration; keep the canonical HXE-3 workflow, memory records, source-dependency ledger and anti-replay/tombstone authority. New additive migration should be safe to leave installed; do not destructive-down migrate production data. If data requires purge, use the governed owner/source erasure path and verify it rather than direct delete. Do not restore a stale snapshot into service without reconciling revocation/forget/original keys. Retain a fixed deterministic fallback and preserve old memory retrieval by default.

Longer-term follow-ups belong to MEM-4 (offline extraction), MEM-5 (hybrid retrieval), MEM-6 (promotion evaluation), MEM-7 (sharing/production governance) or HXE-3 (generic effects/background execution). Do not import them to make this phase feel complete.

\#\# 13\. Detailed deliverables and exit checklist

\- \[ \] Readiness ADR, explicit development-only unfreeze or documented stop, privacy/retention and authority matrix.  
\- \[ \] Plan-hardening note identifying accepted/deferred/rejected assumptions and why.  
\- \[ \] Typed episode-v1 contracts with strict server-bound scope, terminal/observed/verification distinction and allowlist.  
\- \[ \] Additive Postgres projection and in-memory equivalent; no rival memory or execution lifecycle.  
\- \[ \] Exact trusted HXE-3 terminal capture seam, idempotency/unknown-commit reconciliation and original-key persistence.  
\- \[ \] Guarded source dependencies, source/branch/actor rights, expiry, lifecycle suppression and bounded physical erasure seam.  
\- \[ \] Internal bounded scoped search/fetch, explicit partial status, safe historical labels, optional shared context-builder path.  
\- \[ \] \>=30 adversarial E1 cases, split holdout, matched baseline comparison, precise result/fixture hashes and measurement limits.  
\- \[ \] Focused and broad test transcript with native/real/external claims marked precisely, unchanged historical fixtures.  
\- \[ \] Docs and current-state update; explicit default-off, separate rollback and retained blockers.  
\- \[ \] Independent reviewer-ready commit/diff summary, known P0/P1 risks and concrete reproducer commands.

\*\*Exit from MEM-3 E1 implementation:\*\* An authorized synthetic local task can locate a prior observed terminal step, inspect its narrow evidence and limitations, and have it immediately suppressed/erased on source revoke/forget, with no durable raw tool payload and no scope leakage. \*\*Not an exit to production or MEM-4:\*\* those decisions require independent review and evidence-specific gate closure.

\#\# 14\. Review priorities and unresolved decisions

1\. Is HXE-3's persisted attempt binding complete and immutable enough to support a meaningful episode without inventing historical correctness? If not, narrow the episode fields or stop; don't silently enhance the generic run engine beyond the bounded need.  
2\. Which canonical memory lifecycle state/edge mechanism can represent episode validity without a second authority?  
3\. Can a source lease truly fence both capture and current-use revocation under the exact E1 profile? Distinguish local fixture proof from deployed issuer guarantees.  
4\. How are original capture keys, source fences and forget tombstones bounded safely without unsafe compaction?  
5\. Which record fields can be indexed without accidentally retaining private or poisoned source content?  
6\. Is separate episode storage warranted versus reconstructing a transient authorized view from the canonical run and retaining only source-index metadata? Choose the smallest architecture based on measured demands.  
7\. How do we prove the source and retention state used for a returned episode is the state valid at \*physical disclosure\*, not a stale preflight?  
8\. Does the episode improve a later task after matching context/token budgets, or merely make an old step easier to find?  
9\. Could an externally controlled coding harness ever be considered an episode producer? Not without its own explicit issuer/consent/evidence contract; defer.  
10\. Does the baseline-to-current change invalidate these instructions? Re-pin and amend the ADR before implementation.

\#\# 15\. Independent-review handoff and future research

After the Sol Medium implementation stops, a \*\*different Sol session\*\* reviews the exact commit, this plan, the code/tests and evidence; it independently challenges the entire proposed architecture, including whether episodic storage was needed and whether privacy/retention can honestly be guaranteed. The review is not a rubber stamp. It should produce a severity-ranked report, a compact evidence matrix and a single self-contained remediation handoff for a subsequent authorized fix session. Do not move to MEM-4 or enable memory in production merely because local tests pass.

Potential later research: precision/utility-based episode selection, learned retention, outcome-conditioned retrieval, causal comparison of procedural vs episodic memory, session dreaming, longitudinal drift and poisoning defense. These are explicitly deferred.

\#\# Sources

\- Latest inspected repository: https\://github.com/jasonkli21/personal-ai-system/tree/42f00b0f93b0987f615657d4d8b9c145c6c6b016  
\- Integrated roadmap v3.1: user-supplied attachment personal-ai-system-integrated-roadmap-11-03.md (2026-11-03).  
\- Repository memory roadmap: https\://github.com/jasonkli21/personal-ai-system/blob/42f00b0f93b0987f615657d4d8b9c145c6c6b016/docs/memory/memory-architecture-and-research-roadmap.md  
\- Current implementation boundary: https\://github.com/jasonkli21/personal-ai-system/blob/42f00b0f93b0987f615657d4d8b9c145c6c6b016/docs/current-state.md  
\- Workflow lifecycle ADR: https\://github.com/jasonkli21/personal-ai-system/blob/42f00b0f93b0987f615657d4d8b9c145c6c6b016/docs/decisions/0025-workflow-lifecycle-authority.md  
\- MEM-2 blocker ledger: https\://github.com/jasonkli21/personal-ai-system/blob/42f00b0f93b0987f615657d4d8b9c145c6c6b016/docs/memory/mem-2-blockers.json  
