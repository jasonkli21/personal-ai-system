# MEM-4 continuation implementation and verification

Date: 2026-11-03 (America/Los_Angeles). Author implementation and in-session
assessment only; no subagents or independent acceptance. Full MEM-4 remains
**PARTIAL/BLOCKED** and production **NO_GO**. The safely isolated development
work now includes real native PostgreSQL component evidence.

## Revision and plan reassessment

Original entry: `e906bfc1007d27bc75e97b4ad852bac901da931c`.
Continuation entry: `08dd5f0f1d61b29491e02095501515ce49a0bddf`.
Delivery is the amended single commit containing this report; obtain its exact SHA
with `git log -1 --format=%H -- docs/memory/2026-11-03-consolidation-continuation.md`.
The final delivery message supplies that SHA. The seven pre-existing untracked
user plans remain excluded. No push, deployment or production enablement.

The [continuation decision](2026-11-03-consolidation-continuation-decision.md)
reassesses the original deferrals before implementation. Missing production
authorization did not prevent an isolated SQL adapter, native testing, canonical
review dry runs, backfill, adversarial fixtures or model-pilot infrastructure.
Those are now implemented. The [initial report](2026-11-03-consolidation-implementation.md)
and its original hashes/failures remain historical evidence, rather than being
rewritten as results of this continuation.

## Changes and architecture

| Files (under `backend/` unless noted) | Delivered responsibility |
| --- | --- |
| `src/personal_ai/memory/consolidation/{contracts,policy,repository,sources}.py` | One shared transition; exact entailment on reuse; correction barriers after withdrawal; contradictory user corrections; source revisions and fresh regrant; legitimate nullable actors; two explicit generation namespaces |
| `src/personal_ai/persistence/migrations/036_offline_consolidation.sql` | Separate synthetic issuer authority and bounded derived checkpoint/proposal/receipt aggregate; no accepted memory or runtime registration |
| `src/personal_ai/persistence/postgres/consolidation.py` | Native transactions using the existing database deadlines and canonical owner locks; independent-process CAS; atomic issuer/head/checkpoint writes; stale derived-restore detection and live-process issuer revision floor |
| `src/personal_ai/memory/consolidation/governance.py` | Recent authenticated user/current project/client-bound source-checked previews using canonical control decisions; procedure content mapping and typed lesson/conflict review-only tickets; no writes or admission |
| `src/personal_ai/evaluation/fixtures/memory/offline-consolidation-v2.json` | Additive frozen 88-record, 14-task corpus with multiple eligible scopes, epoch/revision regrant, contradictions, withdrawal, expiry and 65-source capacity pressure |
| `src/personal_ai/evaluation/consolidation_quality.py` | Four-arm shared-builder/fresh-consumer quality benchmark and optional existing-local-profile three-arm model pilot |
| `tests/test_consolidation_adversarial.py`, `tests/persistence/test_consolidation_postgres.py` | Adversarial, governance, quality, resource, actual SQL and abrupt process-death coverage |
| `tests/persistence/test_episode_postgres.py`, `tests/persistence/test_workflow_postgres.py`, `tests/test_application_lifecycle.py` | Correct prerequisite/fault fixtures for disabled episode maintenance, observed workflow results, and explicit synthetic restore grants; original safety assertions retained |
| `Makefile`, owning READMEs, `docs/current-state.md`, blocker/evidence documents | Commands, bounds, native setup, current boundary and exact remaining prerequisites |

No runtime memory selector, episode reader, app feature, worker, scheduler,
provider SDK, dependency or automatic approval was added. The new SQL adapter
must be explicitly constructed with a local/test database and fixed public
synthetic corpus. MEM-3 capture/selection remains unconditionally disabled.

The reference repository's transition is reused by the PostgreSQL adapter through
one transaction seam. It stages candidates, checkpoint, and original-key receipt;
SQL serializes canonical owner locks before the synthetic issuer row and scoped
checkpoint rows. The source authority and content-free checkpoint heads commit
in that same transaction. Original-key replay cannot mutate content or reset a
cursor. An ambiguous acknowledgement reconciles by that key; changed payload
conflicts. There is no outbox because there is no dispatched downstream effect.

Native tests terminate a child process with `os._exit` after writes but before DB
commit, and after commit without sending an ACK. Recovery observes the surviving
original receipt or takes over a fenced lease and applies the original batch once.
Independent processes cannot both claim the same stream. Separate worker facades
and reconnects share durable state.

Restoring a stale checkpoint row is denied against its separately surviving
authority head, including its replay ledger. A surviving process also rejects a
decreasing issuer revision. Restoring **both** authority and derived data across
a cold restart is explicitly unverified; no local row can prove its own freshness
against a rollback of the entire authority. This needs an external surviving epoch.

## Source, lifecycle, governance and bounds

Eligibility now resolves exact source ID/revision/epoch; fact, kind and authority
must be entailed by the resolved evidence. Two distinct opposing facts are
required for a conflict. Observed tool completion cannot support a candidate.
An active or withdrawn published correction suppresses lower-authority assertions
of the same command/revision; withdrawal never implicitly restores an old cache.
Contradictory user corrections remain pending conflicts, not last-writer wins.
Explicit supersession can replace an older source revision without merging
unrelated commands or scopes.

Regrant does not rehabilitate an old envelope. The additive fixture supplies a
new frozen revision at the new epoch, which an explicit generation can process.
`synthetic-source-v2:bounded-extractor-v2:pending-policy-v2` has a separate cursor,
lease, keys and pending output. It cannot overwrite the original generation's
receipts or accepted memory (there is no acceptance method).

Read, cached validation, final commit and governance release all revalidate
sources. Pending output expires at the earlier of source expiry or 24 hours after
observation. Explicit maintenance erases derived bodies and retains content-free
receipts and deletion fences. Canonical owner fences block the SQL adapter;
project/owner forget still works at capacity. Public fixture bytes remain in the
bundle. PostgreSQL MVCC/replica/backup erasure is not claimed.

The fixed limits remain four sources/page, 128 sources/corpus, 2 KiB/envelope,
16 KiB/page and retained proposal bytes/stream, 64 proposals/receipts and 32
claims/stream, five-second leases, two-second acquisition/commit/SQL deadlines,
bounded object validation and two allowlisted generations. Synthetic fixture
documents are hash-pinned and capped at 256 KiB; SQL authority/checkpoint JSON is
capped at 64 KiB. Capacity exhaustion denies the entire batch without pruning
original keys or tombstones. Finite denial completes this contract; unsafe
unbounded compaction is not an unfinished required feature.

Governance requires the canonical service's current project/source lease,
matching server request/owner/application/workspace/actor/project, verified client
and audience, and its recent-user authorization. Procedures use the canonical
content/propose decision. Lesson/conflict bodies remain explicitly typed beside
a bodyless **never-persisted** canonical review ticket; canonical review CAS,
rejection and expiry can thus be tested without changing old wire kinds or
inventing a project decision. No preview is a queue submission, memory approval
or permission for a later write. Revoked/cached candidates are denied on release.

## Evaluation and optional local model

V1 bytes and initial scores are preserved. V2 was reviewed and frozen before its
first quality scoring; pre-score review corrected one expected outcome to honor
the explicit user correction rather than the later lower-authority statement.
No measured failure or historical digest was edited to obtain a pass.

V1 SHA-256: `137b432e57ff35a2184c4cc4ace58befd2c27468b01ceadde0dd658c1253becf`.
V2 SHA-256: `ca671aee1b7b21226d147808c41aeae263aa97a558a6fcf42c0372860e436ec7`.
V2 has seven development and seven author-visible reserved tasks; reserved is
not independent holdout. Its 65-source pressure stream is an adversarial quota
fixture, not a scored quality case.

| Scripted fresh-consumer arm | Correct/14 | False support | Cross-scope leakage |
| --- | --- | --- | --- |
| No consolidation | 3 | 0 | 0 |
| Fixed first-record heuristic | 5 | 7 | 0 |
| Deterministic pending | 14 | 0 | 0 |
| Full eligible-source oracle | 14 | 0 | 0 |

The consumer sees only serialized cards from the shared context builder and a
narrow query; it cannot read candidate objects, source registries or scorer
expectations. Drop controls cause abstention. Fifteen candidate edges were
checked, with zero ineligible edges or entailment failures. The first-record arm
is a deliberately simple synthetic comparator, **not** canonical legacy fixed
retrieval; the latter cannot represent these typed project facts. These scores
are E1 consumer evidence, not real task success or measured longitudinal utility.

The optional local pilot uses the existing `ChatTurnService`, shared assembler,
`compose_pair`, local admission and canonical physical-attempt/usage accounting.
Three arms have the same model and 4,096 context/128 response-token, 30-second
request bounds, with no hosted fallback or tools. Only public synthetic cards
are sent when explicitly invoked. Infrastructure/orchestration tests use fakes
and do not count as provider evidence. This host has no `llama-server`,
`llama_cpp`, configured private socket, pinned GGUF hash or pinned build.
`--local-preflight` reports `blocked/local_profile_not_configured`. No real
model/provider call, model token use, new grant or external disclosure occurred.

## Verification and preserved failures

macOS arm64; Python 3.11.15. The initially unset DSN was resolved by creating a
disposable UTF-8 PostgreSQL 17 cluster under `/private/tmp`, with pgvector and
loopback port 55491. Native tests used the canonical migration runner and
`isolated_postgres_dsn`, creating/dropping separate synthetic databases. Sandbox
socket/shared-memory restrictions required scoped tool escalation, which was
approved. The cluster is stopped after verification. No existing database or
private data was used. No emulator was fabricated.

Make commands used `PATH="$PWD/backend/.venv/bin:$PATH"`; adjacent/broad checks
also set `LITELLM_LOCAL_MODEL_COST_MAP=True`. Native commands explicitly set
`PERSISTENCE_TEST_POSTGRES_DSN=postgresql://consolidation_test@127.0.0.1:55491/postgres`.

| Command/check | Result |
| --- | --- |
| `make memory-consolidation-check` | PASS, 103 focused tests |
| `make memory-consolidation-eval` | PASS, preserved v1 12/12 shapes; v2 14/14 scripted answers and zero deterministic false support/leakage |
| `make memory-consolidation-postgres-check` | PASS, 21 native tests, including actual process death |
| `make memory-episode-postgres-check` | PASS, two native tests with capture/read still disabled |
| `make workflow-postgres-check` | PASS, 35 native tests |
| Full `pytest backend/tests/persistence -m persistence_integration` | PASS, 161 passed, 14 unavailable DynamoDB cases skipped, 29 deselected; collected before the final two process-death tests, which pass in the final 21-test target |
| Adjacent control/context/API, local inference, database deadline and knowledge unit files | PASS, 157 tests |
| `make memory-episode-check memory-episode-candidate-eval` | PASS, 93 tests and 38 structural scenarios |
| Knowledge/causal/control/memory/workflow Make targets | PASS; 20 proxy cases, 16 causal pairs, 36 control cases, existing memory fixture runner, 70 workflow tests |
| `make backend-lint naming-policy-check` | PASS; checker includes two tests |
| Loopback application restore + retrieval tests | PASS, 35 tests; all original source-withdrawal/restore assertions retained |
| Broader `make backend-test-offline` with local consumer source paths and socket escalation | FAILED, 2,678 passed, 27 failed, one skipped, 176 deselected, 246.59 seconds; breakdown below |
| Final focused planning v35 source-lock assertion | FAILED against unchanged historical digest; exact observation in additive evidence receipt |
| Local model preflight | BLOCKED, actual runtime/model prerequisites absent; no real model test counted |
| Changed docs/JSON/hashes, formatting and `git diff --check` | PASS |

The broad invocation supplied SDK and both Checklist source paths in `PYTHONPATH`,
without installing/changing dependencies. Its 27 failures were 25 preserved
`frozen_protocol_mismatch` rejections, the inherited v35 source digest assertion,
and one application restore fixture that lacked its initial synthetic grants.
The latter was fixed and the unchanged safety assertions pass in the final
35-test loopback run. The full invocation was not repeated after the final
read-only governance/client preview additions and fixture fix; no full green-gate
claim is made. The remaining frozen identities require additive review, not
rewriting old expected hashes. All old lock/corpus bytes remain unchanged.

Discovered defects/faults are retained: the first native episode test expected
enabled capture; the workflow deadline fixture expired inside the invocation
before a trusted result was observed; and the application restore fixture depended
on test-name-prefix feature grants. These test setups now model the intended
boundaries without weakening their assertions. A new native initial-issuer-crash
test failed (17 passed/one failed): a shallow publication snapshot retained an
uncommitted mutation. Copying that snapshot fixed rollback; the final native
21-test target passes. Early local-pilot tests/preflight also exposed missing
required neutral Settings fields; explicit synthetic provider/model values fixed
the harness, without enabling model access.

## Remaining dependencies, evidence tiers and rollback

Every remaining deferral in the [dependency ledger](consolidation-development-blockers.json)
states its exact prerequisite, why this session cannot establish it, completed
independent work and concrete unblocking steps. No SQL/native, read-only review,
bounded backfill, quota policy or synthetic evaluation work is deferred merely
because production is unauthorized.

E0/E1 and **E2 native component** evidence are supplied. E2 does not establish
live source authenticity or full integrated phase completion. E3 live
identity/model/disclosure evidence, E4 deployed recovery/physical erasure and
release acceptance, E5 independently held-out longitudinal improvement, and the
requested separate Sol High review remain unverified. Real source provenance
cannot be reconstructed from missing original metadata, nor can a rolled-back
database authenticate its own former epoch. Those are concrete source/restore
dependencies. Private model execution waits on actual pinned local infrastructure.
Canonical runtime queue/selection waits on a versioned source-aware mapping and
the trusted producer, not a permissive preview.

Review the exact amended commit with the focused and native targets, then inspect
source-vs-derived restore heads, owner/source/SQL lock ordering, original-key
recovery, observed-versus-certified outcomes, correction barriers, typed review
tickets and the local pilot's existing admission path. The
[additive evidence receipt](2026-11-03-consolidation-continuation-evaluation.json)
pins code, migration, fixtures, results and unresolved release bindings for review.
It is author evidence, not independent acceptance. MEM-5 must not index or select
these pending fixtures as trusted memory.

Rollback stops explicit offline callers and keeps runtime consumers absent.
Keep migration 036 forward-only and preserve its original keys, authority heads
and owner/source fences; do not restore stale derived rows as eligible or prune
replay barriers. Keep MEM-3 hard disabled. No accepted memory, default-on feature,
external effect, release profile or deployment needs reversal.
