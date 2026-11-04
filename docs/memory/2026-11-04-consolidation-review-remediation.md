# Consolidation independent-review remediation

Date: 2026-11-04 (America/Los_Angeles). Reviewed source revision:
`bb490ca9342b2ded6241124b74f249651f0dee5c`. This is author remediation and
verification, not independent acceptance. Full MEM-4 and production remain
**BLOCKED / NO_GO**.

## Changes

- Corpus digests now constrain generation identities. V1 retains its original
  identity. V2 uses either the additive V2-source/V1-policy comparison identity
  or the V2-source/V2-policy backfill identity. Cross-corpus pairings deny at
  repository construction; historical v1/v2 fixture bytes are unchanged.
- PostgreSQL repository transactions validate scopes through the source contract
  before reading `scope.key`. Hostile objects, unsafe model copies, malformed IDs
  and unregistered scopes deny through the content-free error boundary.
- Native SQL lease acquisition and expiry checks use PostgreSQL
  `clock_timestamp()` inside the locked transaction. The fixture clock continues
  to model synthetic source observation and expiry; it is not lease authority.
  The opt-in native test covers independent workers with clocks skewed by ten
  minutes in both directions and stale-lease fencing.
- The PostgreSQL adapter exposes bounded owner inventory and a fenced
  `purge_owner(owner_id)` operation that needs no project lookup. It deletes
  checkpoint payloads across both frozen corpora, updates shared source heads,
  retains scope tombstones and the canonical owner fence, and leaves other owners'
  rows intact. The migration remains part of the global schema sequence, while
  the adapter accepts only the bundled public synthetic fixture sources and is
  not runtime-composed. MVCC history, replicas, backups and full-authority cold
  restore remain outside this local seam.
- The local pilot compares no consolidation, deterministic pending proposals and
  exact eligible source context through the shared chat/admission/attempt path.
  Canonical fixed-memory comparison is explicitly unsupported for these fixture
  facts. Incomplete or unaccounted rows cannot be labeled measured; task rubrics,
  token confidence, latency and local no-charge cost status are reported
  separately. Hosted fallback remains disabled.
- Added an author-visible challenge manifest for unsupported outcomes, poisoned
  claims, language ambiguity and exact source attribution, plus a separate blind
  evaluation plan. Neither is an independent holdout or E5 utility result.
- Living current-state text now distinguishes authorized local synthetic MEM-4
  component work from the E0/E1 terminal-step unfreeze. `diagnostics()` reports
  `processed_source_positions`; the persisted `proposal_count` field is documented
  as the post-batch live proposal total.

R-01 remains an integration gate: no authenticated real-source producer, runtime
consumer, accepted-memory writer, private source use or physical send was added.
MEM-3 capture/read stays disabled. No model was run, no hosted provider was used,
and no feature was deployed or enabled.

## Verification

| Command / check | Result |
| --- | --- |
| `PATH="$PWD/backend/.venv/bin:$PATH" make memory-consolidation-check memory-consolidation-eval` | **PASS** — 107 focused tests; v1 preserved at 12/12 shapes; v2 at 14/14 scripted answers, zero false support and zero cross-scope leakage. V1 digest `137b432e57ff35a2184c4cc4ace58befd2c27468b01ceadde0dd658c1253becf`; v2 digest `ca671aee1b7b21226d147808c41aeae263aa97a558a6fcf42c0372860e436ec7`. |
| `PATH="$PWD/backend/.venv/bin:$PATH" make memory-episode-check memory-episode-candidate-eval memory-knowledge-eval memory-knowledge-causal-eval memory-control-eval memory-eval workflow-check backend-lint naming-policy-check` | **PASS** — episode/service 93 tests; terminal-step evaluation 38/38; workflow/mutation 70 tests; knowledge and control evaluations passed; backend lint and naming-policy check passed (2 tests). |
| `backend/.venv/bin/ruff check` and `ruff format --check` on changed Python files | **PASS**. |
| `backend/.venv/bin/python -m py_compile backend/src/personal_ai/persistence/postgres/consolidation.py backend/tests/persistence/test_consolidation_postgres.py` | **PASS**. |
| `git diff --check` | **PASS**. |
| `cd backend && python -m personal_ai.evaluation.consolidation_quality --local-preflight` | **BLOCKED** — `local_profile_not_configured`; no local model call. |
| `PATH="$PWD/backend/.venv/bin:$PATH" make planning-eval` | **FAIL, preserved historical gate** — v35 rejects the changed source identity before evaluation. Expected source identity remains `4eb58162ae39387382c18b524017886c1be4e4fc27de5203ac064f5c6e889cc9`; recomputed identity is `18aa41f9e99bfa2436ec00a5028b51992106f86aff2a1c9c236f9b6f414eaa03`. No frozen lock or corpus was rebound. |
| Native PostgreSQL consolidation tests | **BLOCKED** — no `PERSISTENCE_TEST_POSTGRES_DSN` was configured. A new isolated PostgreSQL 17 + pgvector cluster was attempted under `/private/tmp`; sandbox startup failed at `shmget` with `Operation not permitted`, before migrations or tests. No existing database was contacted or changed. |
| Broad `make backend-test-offline`, real local model, independent E2–E5, deployed erasure/restore | **NOT RUN / BLOCKED** — see dependency ledger. |

The new challenge manifest digest is
`b50bd0253f316c318f700ec1e31d60522391f3323c68afc9e84d9dab624c1169`. V1 and
v2 source fixtures remain byte-for-byte at their prior hashes. The machine-readable
[remediation receipt](2026-11-04-consolidation-review-remediation.json) records
the changed source hashes and command statuses.

## Rollback and remaining gates

Stop explicit offline callers and keep these adapters unregistered. Migration 036
remains forward-only; do not restore stale checkpoint rows or clear owner fences.
If the code change must be reverted, revert the single remediation commit while
retaining canonical owner fences and the prior migration. Full acceptance still
requires authenticated source authority, independently reproduced native SQL
evidence, deployed physical erasure and restore controls, a pinned local model,
blind longitudinal utility, and separate independent review. Do not promote from
these synthetic results.
