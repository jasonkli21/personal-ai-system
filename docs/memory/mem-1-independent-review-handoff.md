# MEM-1 independent review handoff

Date: 2026-10-29 (America/Los_Angeles). Implementation base:
`293a5910827d9a1f70e1342ee3b98f24ab615e4d` plus the single implementation commit.
This is a handoff, not a review verdict. Read the [ADR](mem-1-contract-adr.md)
and [implementation report](mem-1-implementation-report.md) first.

## Entry and acceptance boundary

The user requested an attempt to resolve MEM-0 first, then explicitly authorized
continuing if acceptance remained incomplete. The implementation session reran
MEM-0 checks and a full suite; see [entry verification](mem-0-entry-reverification.md).
That evidence is implementation QA, not a replacement independent review.
Do not infer production readiness, real-agent lift, or independent fixture review.
The 20 MEM-1 cases carry `author_reviewed_independent_review_pending` explicitly.

## Review ownership and trust

- `memory/knowledge.py`, `knowledge_service.py`, `knowledge_sources.py`: strict
  kinds, exact historical procedure recipe, authenticated completed-turn
  confirmation, source leases, separate authority/verification/outcome, original-key
  reconciliation, server scope/project filters, final consumption guards.
- `memory/knowledge_repository.py`, `persistence/postgres/knowledge.py`, migration
  `028_verified_memory_knowledge.sql`: existing memory repository ownership,
  scoped admission uniqueness, complete normalized edges, source tombstones,
  budgets, retention and source erasure. No production workflow issuer is installed.
- `memory/lifecycle/repositories.py`, `persistence/postgres/lifecycle.py`: schema-3
  support using the existing state/event tables and pure transition policy.
  Automatic personal-preference maintenance is not broadened to knowledge.
- `memory/contracts.py`, `services.py`, `dependencies.py`, `inspection.py`,
  `context/assembler.py`: explicit default-off selection, complete dependency
  authority, historical context labels/expiry and shared token-cap enforcement.
- `auth/owner_data.py`, `persistence/postgres/auth.py`: new families in the owner
  inventory and bounded account export. Deployed source-erasure/account-deletion
  orchestration remains an external obligation.
- `artifacts/service.py`, `tests/test_artifacts.py`: all `ai_memory_` dependencies,
  including knowledge, must reject writes before metadata/body reservation until
  artifact reuse has a valid owner/actor revalidation context.
- `evaluation/knowledge_runtime.py`, `memory_knowledge.py`,
  `fixtures/memory/mem1-paired-v1.json`: actual stateful synthetic Task A and fresh
  Task B, separate result IDs, finite tool authority and causal trace validation.
  Review that rubric/split/case faults cannot become driver input.
- `settings.py`, `.env.example`, Makefile, package/experiment READMEs: separate
  disabled admission/selection controls. `fixed`, v1/v2 data and old corpus bytes
  stay compatible. Planner freeze v17 rebinds source identity without promotion;
  v16 and all earlier locks are retained.

## Reproduce and challenge

Use the report's exact environment and commands. New offline tests are
`test_memory_knowledge.py` and `test_memory_knowledge_evaluation.py`; native tests
are `persistence/test_verified_knowledge_postgres.py`. Reproduce both benchmark
semantic digests, mixed legacy/native tests, source revocation after selection,
forgotten-record retry, expiry erasure, incomplete provenance, owner fencing,
concurrent admissions/CAS, partial insert rollback and lost commit acknowledgement.
Keep all provider/emulator/cloud checks opt-in and never weaken timeouts.

Questions requiring independent judgment:

1. Is the exact command recipe narrow enough to avoid turning successful tests
   into unsupported general claims? Is confirmed user intent always labeled as
   an assertion rather than canonical project truth?
2. Does every new reader and supported later history/summary path fail closed
   on any missing edge, actor/grant change, stale branch/revision, owner fence,
   source erasure or missing lifecycle projection? Try malicious repository rows.
3. Do admission, source tombstones, explicit lifecycle events and final use
   serialize correctly under native concurrency and uncertain SQL outcomes?
   There is no claimed cross-store atomicity or deployed source-lease issuer.
4. Are fake benchmark arms comparable, and are unsupported legacy denominators,
   repeat discovery, safety failures and target outcomes graded honestly? The
   tagged holdout is not a blind model study. Independently review all 20 cases.
5. Does disabling selection restore only the old reader immediately, including
   already packed dependencies? What additional native/cloud/identity/deletion
   evidence is needed before wiring any production host or promoting flags?

Independent acceptance, fixture sign-off and any production issuer integration
must be recorded separately. This implementation enables no production flag.
