# MEM-4 bounded offline consolidation implementation

This initial receipt describes revision `08dd5f0f1d61b29491e02095501515ce49a0bddf`.
Its findings and failed attempts are retained. The [continuation report](2026-11-03-consolidation-continuation.md)
supersedes its deferrals and current implementation boundary.

Date: 2026-11-03, America/Los_Angeles. Author implementation and in-session
self-review only; no subagents or independent acceptance. **PARTIAL/BLOCKED**
for full MEM-4, production **NO_GO**.

## Revision and scope

Entry revision: `e906bfc1007d27bc75e97b4ad852bac901da931c`.
Delivery revision is the single commit containing this receipt. Resolve its exact
SHA with `git log -1 --format=%H -- docs/memory/2026-11-03-consolidation-implementation.md`;
the delivery message also records that SHA. A committed receipt cannot embed its
own final content-addressed commit hash without changing it. There is no push,
deployment, new worktree or second commit.

The seven user-owned untracked planning files present at entry are excluded from
the commit. The supplied MEM-4 detailed plan was read in full, challenged and
narrowed in the same session in the [pre-implementation decision](2026-11-03-consolidation-plan-hardening.md).
The authorization covers hermetic synthetic development, not enabling MEM-3.

## File map and package architecture

| Files | Responsibility |
| --- | --- |
| `memory/consolidation/contracts.py` | Closed versioned scope, fact, envelope, exact edge, pending proposal, page, lease and content-free receipt contracts; hostile object-copy revalidation |
| `memory/consolidation/sources.py` | Only hash-pinned fixture membership; finite synthetic issuer, ordered publication, current epoch/revision/time checks, corrections, withdrawal/regrant and forget fences |
| `memory/consolidation/policy.py` | Deterministic proposal, exact duplicate, supersession, unresolved conflict and user-correction precedence |
| `memory/consolidation/repository.py` | Shared disposable per-issuer store; scoped cursor CAS, lease fencing, single-assignment proposal/checkpoint/original-key transaction, replay and maintenance |
| `evaluation/consolidation.py` and additive `fixtures/memory/offline-consolidation-v1.json` | Frozen four-arm structural comparison; 26 records in 12 streams with seven development/five author-visible reserved cases |
| `tests/test_offline_consolidation.py` | Unit, finite permutation/property, thread-contention, fault-injection and hostile-input tests |
| `Makefile` | `memory-consolidation-check` and `memory-consolidation-eval` |
| Memory README, current state, decision, report, additive evaluation receipt and blocker ledgers | Usage, evidence and deferred integration rationale |

Paths in the table are relative to `backend/src/personal_ai/` except tests,
Makefile and docs. There are no new dependencies, settings or migrations.
Migration 035 and all old schema contracts are unchanged. Nothing imports this
component in runtime composition. User-visible behavior is unchanged.

The fixture source and repository share a bounded reentrant lock. Worker facades
share one store; creating another facade cannot reset the cursor or ledger. A
page is exactly the next published source page in a scope and fixed generation.
The original key binds scope, generation and cursor interval, while a separate
digest binds all input bytes. The lease token is deliberately absent from that
key. Under the source lock, commit rechecks current source eligibility, derives
only typed pending content, then assigns checkpoint/proposals/receipt together.
The native DB transaction, canonical outbox and distributed source lease are
**not implemented** by this local contract.

Duplicate delivery returns a content-free original outcome. Changed payload
under the same key is denied. A simulated failure before assignment leaves all
three parts unchanged; failure after assignment requires observing/replaying the
original key. No blind retry creates a fresh operation identity. Revoked or
expired authentic input receives an explicit terminal skip; forged input denies
the whole transaction. A later regrant cannot revive a skipped old epoch.

Pending output retains exact source fingerprint/revision/epoch edges. The fixed
grammar expresses historical synthetic check outcomes, not generalized recipes
or task-success certification. Observed tool completion yields no candidate.
User corrections take precedence even between publication and checkpointing;
conflicting assertions become pending conflicts and withhold ordinary proposals.
Exact duplicates conservatively retain the original edge rather than merging
independent sources; revoking that edge may remove the duplicate suggestion until
a future explicit backfill. This favors denial over unsupported reuse.

## Resource and lifecycle boundaries

Four sources/page; 128 total source slots (26 in this corpus); 2 KiB/envelope;
16 KiB/page and retained proposal bytes/stream; at most 64 proposals, 64 original
receipts and 32 claims/stream. The actual corpus has 12 streams. Leases last five
seconds; lock acquisition and commit work have two-second bounds. Object-copy
validation has fixed nesting/node/fanout/byte bounds. Provider calls/tokens,
automatic retries and external sends are zero. Unknown fields and unsafe copies
are denied without payload-bearing serializer warnings. Diagnostics contain
counts and hashes, never source/proposal text.

The fixture identity set reserves source-fence capacity up front. Synthetic
epochs saturate with denial of regrant; capacity cannot evict a tombstone or
original receipt. Forget does not consume write quota. Source withdrawal,
supersession, expiry and owner/project forget suppress pending and cached objects;
bounded explicit maintenance removes derived bodies. Content-free receipts and
deletion barriers remain. The immutable **public synthetic fixture file** is not
erased. This does not claim physical deletion of private source data.

There is no restore/import API. Replaying a stale repository object against the
current synthetic issuer stays denied after forget/revoke. Reconstructing the
issuer creates a new disposable simulation; restoring both issuer and storage
would bypass these local barriers and requires the deferred external monotonic
authority. There are no accepted proposals, selection cache, context consumer,
provider path or runtime job to enable.

## Evaluation identity and interpretation

The source records, expected pending shapes, reserved split, comparator arms and
metric were frozen before scoring. SHA-256 of the complete additive corpus:
`137b432e57ff35a2184c4cc4ace58befd2c27468b01ceadde0dd658c1253becf`.
Adapter/policy/extractor generation is
`synthetic-source-v1:bounded-extractor-v1:pending-policy-v1`.
See the [machine-readable evaluation receipt](2026-11-03-consolidation-evaluation.json)
for code/file hashes, observed resource counters and elapsed time.

| Exact pending-shape arm | Development | Reserved (author-visible) |
| --- | --- | --- |
| No consolidation | 1/7 | 1/5 |
| Fixed first assertion | 4/7 | 3/5 |
| Deterministic pending proposals | 7/7 | 5/5 |
| Full eligible-source shape oracle | 7/7 | 5/5 |

The fixed-first arm is a synthetic stand-in, **not existing production fixed
retrieval**. The oracle scores the eligible closed fixture facts independently
of the extractor; expectations enter only the scorer. Exact kind/count matching
is narrow structural evidence and does not measure claim precision over arbitrary
language, successful agent actions, token savings, or longitudinal utility.
The reserved cases are author-visible, not independently held out. No real-model
arm ran. Existing knowledge/control evaluators were run separately; they do not
make these proxy arms an end-to-end integration benchmark.

All historical corpora, frozen digests, release locks, scoring thresholds and
historical failures remain unchanged. No additive release source-identity rebind
is claimed here; inherited release binding failures remain blocked.

## Verification

Commands run on macOS arm64, Python 3.11.15. Make commands used
`PATH="$PWD/backend/.venv/bin:$PATH"`; adjacent/broad checks also used
`LITELLM_LOCAL_MODEL_COST_MAP=True`. No native/emulator/cloud/provider test is
inferred from fakes.

| Command | Result |
| --- | --- |
| Entry `make memory-episode-check workflow-check` | PASS, 93 + 70 tests |
| Final `make memory-consolidation-check` | PASS, 74 tests |
| `make memory-consolidation-eval` | PASS, 12/12 exact synthetic pending shapes; no utility claim |
| `make memory-episode-check` | PASS, 93 tests |
| `make memory-episode-candidate-eval` | PASS, 38/38 structural cases |
| `make memory-knowledge-eval` | PASS, 20-case hermetic proxy, invariant failures zero |
| `make memory-knowledge-causal-eval` | PASS, 16 paired packed-consumer cases, invariant failures zero |
| `make memory-control-eval` | PASS, 36/36 cases, unauthorized operations zero |
| `make memory-eval` | PASS, existing synthetic fixture runner |
| `make workflow-check` | PASS, 70 tests |
| `make backend-lint` | PASS |
| `make naming-policy-check` | PASS, policy plus two checker tests |
| Changed Python `ruff format --check` | PASS after formatting |
| `make memory-episode-postgres-check workflow-postgres-check` | BLOCKED at prerequisite guards: disposable `PERSISTENCE_TEST_POSTGRES_DSN` unset |
| Original `make backend-test-offline` | FAILED collection: local `personal_ai_sdk` not installed |
| Broad run with SDK source path | FAILED collection: local `project_checklist` not installed |
| Broad run with SDK and both Checklist source paths | FAILED: 2,549 passed, 36 failed, 92 errors, one skipped, 157 deselected, 214.60 seconds; source imports are not installed-package evidence |
| Final focused planning v35 source-lock assertion | FAILED, one preserved release-identity assertion; final code digest below |
| Changed docs local links/JSON/content and `git diff --check` | PASS |

The completed broad invocation supplied
`PYTHONPATH="$PWD/sdk/python/src:$PWD/examples/project-checklist/client/src:$PWD/examples/project-checklist/host/src"`
without installing or changing dependencies. Its 36 failures consist of 25
`frozen_protocol_mismatch` PI-6 rejections, ten socket `PermissionError` failures,
and the inherited planning v35 source-identity assertion. All 92 setup errors are
socket `PermissionError` from the managed sandbox. The broad run began before
the final shared-worker-facade and staging-expiry hardening; the final 74-test focused run and
machine-readable hashes cover the delivery code. No broad green-gate claim.

The broad planning assertion compared frozen expected
`4eb58162ae39387382c18b524017886c1be4e4fc27de5203ac064f5c6e889cc9`
with then-computed worktree source digest
`047f52a8faa46c4ce077b48ab19da16705395eff840a2668ace55823156781a3`.
That dirty-worktree observation is not the final committed-tree identity. The
source-lock failure was already recorded on the entry revision in the
[prior remediation](2026-11-03-luna-remediation.md). Old locks remain byte-for-byte
unchanged. Native provider-isolation was not re-established; its OS-fence/socket
prerequisite was already unavailable in that remediation.

After the final code changes, the same focused source-lock test was run as
`cd backend && .venv/bin/python -m pytest -q tests/test_planning_experiment.py::test_current_planning_lock_binds_owner_portability_source_without_promoting`.
It failed with computed digest
`7378b4e8731f523f23bb964e5419370396a9d39c57fde3f66f1bac9534309c05`
against the unchanged frozen expectation above. This is recorded as a release
blocker, not repaired by rebinding a historical lock.

The first new targeted run failed one unknown-field test (66 passed). It exposed
`model_copy` keys silently dropped by serialization and a warning that could
contain poisoned input. Boundary validation now rejects unknown copied fields,
cycles, wrong nested types and oversized input before silent normalization or
payload-bearing warnings. A final fault test also verifies source expiry during
receipt staging is rechecked before the atomic assignment. Final focused checks
pass; tests were not weakened.

## Deferred work, evidence tiers and review

The [blocker ledger](consolidation-development-blockers.json) owns each remaining
gate and rationale; the [episode ledger](episode-development-blockers.json)
retains every inherited blocker. E0 contract/code and E1 local synthetic behavior
are demonstrated. E2 native transactions/processes, durable issuer and deletion
fences; E3 live identity/provider/disclosure and operational resources; E4 deployed
recovery, replica/backup erasure and release acceptance; E5 independently held-out
longitudinal task improvement are **unverified/BLOCKED**. No phase exit, release
promotion or independent acceptance is claimed.

Review the exact delivery commit with the two new Make targets, adjacent memory
and workflow targets, and native prerequisites when genuinely available. Focus on
source membership versus authentication, final source/lease checks, one-assignment
CAS/replay, correction precedence, conservative dedupe, payload-free failure
surfaces and the unsupported both-issuer-and-store rollback case. Review frozen
fixtures independently before treating them as acceptance evidence.

Runtime integration waits for MEM-3 original provenance and source epochs, plus
a canonical transaction/lifecycle mapping. MEM-2 review needs an explicit typed
lesson/conflict mapping and final source checks before it can expose these
proposals. A model adapter waits for strict-free admission, source disclosure at
physical send and attempt accounting; adding a fake permissive adapter would
not establish those prerequisites. Backfill/compaction waits for durable epochs
and recovery. MEM-5 may reuse this proposed reference contract after review, but
must not index or select the pending fixture output as trusted knowledge.

Rollback is removal of the offline caller/component. No runtime flag, worker,
accepted memory or migration changes need reversal. Keep existing MEM-3 capture
and selection disabled and preserve old release/source locks. A future durable
integration must retain its original-key and deletion fences during rollback.
