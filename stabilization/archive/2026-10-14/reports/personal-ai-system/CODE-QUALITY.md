> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Personal AI code-quality baseline

Revision: `c029194156c570ec55f8173af969702f0265e57b`; date: 2026-10-13. Tracked files only; line metric is nonblank physical lines (a reproducible proxy for logical lines, not statements). Categories are path-based and require manual review before refactoring. No files removed or behavior changed.

## Largest files by bytes

| File | Bytes | Nonblank lines | Category |
| --- | ---: | ---: | --- |
| `backend/uv.lock` | 711285 | 3038 | lock/vendor/build |
| `docs/personal-ai-chapter-2/phase-36/receipts.json` | 329521 | 5031 | fixtures/evaluation data |
| `backend/src/personal_ai/evaluation/fixtures/routing/adaptive-observations-v1.json` | 324136 | 9490 | fixtures/evaluation data |
| `frontend/tsconfig.tsbuildinfo` | 186265 | 1 | configuration/manifests |
| `docs/personal-ai-chapter-2/phase-36/matrix-results.json` | 159366 | 3875 | fixtures/evaluation data |
| `backend/tests/test_context_sources.py` | 114305 | 2792 | handwritten tests |
| `frontend/pnpm-lock.yaml` | 113630 | 2648 | lock/vendor/build |
| `backend/src/personal_ai/agents/research/iterative/service.py` | 93870 | 2172 | handwritten production |
| `docs/releases/phase-4-memory-lifecycle-evaluation.json` | 87974 | 3219 | configuration/manifests |
| `backend/src/personal_ai/evaluation/fixtures/routing/provider-matrix-fixtures.json` | 81511 | 2541 | fixtures/evaluation data |
| `backend/tests/persistence/test_local_persistence.py` | 77386 | 1584 | handwritten tests |
| `backend/src/personal_ai/evaluation/provider_matrix_runner.py` | 73185 | 1590 | handwritten production |
| `backend/tests/test_external_turns.py` | 63393 | 1431 | handwritten tests |
| `docs/current-state.md` | 62656 | 201 | documentation |
| `backend/src/personal_ai/routing/service.py` | 62110 | 1269 | handwritten production |
| `backend/src/personal_ai/evaluation/verification/matrix.json` | 60095 | 1346 | configuration/manifests |
| `backend/tests/test_context_planner.py` | 59347 | 1496 | handwritten tests |
| `backend/tests/test_litellm_gateway.py` | 57323 | 1449 | handwritten tests |
| `backend/src/personal_ai/persistence/postgres/auth.py` | 54747 | 1131 | handwritten production |
| `backend/src/personal_ai/context/assembler.py` | 53676 | 1175 | handwritten production |
| `backend/src/personal_ai/services/chat/service.py` | 50383 | 1091 | handwritten production |
| `backend/src/personal_ai/persistence/postgres/usage/accounting.py` | 49710 | 1030 | handwritten production |
| `backend/tests/test_phase36_integrated.py` | 48742 | 1095 | handwritten tests |
| `backend/tests/test_federation.py` | 47376 | 1073 | handwritten tests |
| `backend/tests/test_chatgpt_bridge_transport.py` | 44961 | 1032 | handwritten tests |

## Largest handwritten files by nonblank lines

| File | Bytes | Nonblank lines | Category |
| --- | ---: | ---: | --- |
| `backend/tests/test_context_sources.py` | 114305 | 2792 | handwritten tests |
| `backend/src/personal_ai/agents/research/iterative/service.py` | 93870 | 2172 | handwritten production |
| `backend/src/personal_ai/evaluation/provider_matrix_runner.py` | 73185 | 1590 | handwritten production |
| `backend/tests/persistence/test_local_persistence.py` | 77386 | 1584 | handwritten tests |
| `backend/tests/test_context_planner.py` | 59347 | 1496 | handwritten tests |
| `backend/tests/test_litellm_gateway.py` | 57323 | 1449 | handwritten tests |
| `backend/tests/test_external_turns.py` | 63393 | 1431 | handwritten tests |
| `backend/src/personal_ai/routing/service.py` | 62110 | 1269 | handwritten production |
| `backend/src/personal_ai/context/assembler.py` | 53676 | 1175 | handwritten production |
| `backend/src/personal_ai/persistence/postgres/auth.py` | 54747 | 1131 | handwritten production |
| `backend/tests/test_phase36_integrated.py` | 48742 | 1095 | handwritten tests |
| `backend/src/personal_ai/services/chat/service.py` | 50383 | 1091 | handwritten production |
| `backend/src/personal_ai/llm/litellm/gateway.py` | 44890 | 1084 | handwritten production |
| `backend/tests/test_federation.py` | 47376 | 1073 | handwritten tests |
| `backend/tests/test_chatgpt_bridge_transport.py` | 44961 | 1032 | handwritten tests |
| `backend/src/personal_ai/persistence/postgres/usage/accounting.py` | 49710 | 1030 | handwritten production |
| `backend/tests/persistence/test_routing_decisions.py` | 41261 | 957 | handwritten tests |
| `backend/src/personal_ai/context/finance.py` | 43912 | 943 | handwritten production |
| `backend/tests/test_endpoint_registry.py` | 44164 | 941 | handwritten tests |
| `backend/tests/test_routing_phase21.py` | 38971 | 934 | handwritten tests |

## Largest directories (recursive totals overlap)

| Directory | Bytes | Nonblank lines | Files |
| --- | ---: | ---: | ---: |
| `backend` | 7030027 | 147537 | 516 |
| `backend/src/personal_ai` | 4380215 | 100432 | 396 |
| `backend/src` | 4380215 | 100432 | 396 |
| `docs` | 2591145 | 33925 | 230 |
| `backend/tests` | 1920229 | 43591 | 114 |
| `docs/personal-ai-chapter-2` | 1729658 | 20985 | 145 |
| `backend/src/personal_ai/evaluation` | 1135957 | 30907 | 62 |
| `backend/src/personal_ai/persistence` | 715050 | 15170 | 74 |
| `frontend` | 705513 | 10066 | 115 |
| `backend/src/personal_ai/evaluation/fixtures` | 620661 | 19484 | 29 |
| `docs/personal-ai-chapter-2/phase-36` | 529495 | 9572 | 6 |
| `backend/src/personal_ai/context` | 481535 | 10219 | 25 |
| `docs/personal-ai-chapter-2/personal-ai-next-scope-detailed-implementation-plans` | 463163 | 5068 | 46 |
| `backend/src/personal_ai/persistence/postgres` | 445476 | 9549 | 28 |
| `backend/src/personal_ai/evaluation/fixtures/routing` | 440389 | 13106 | 4 |
| `docs/personal-ai-chapter-2/personal-ai-next-scope-detailed-implementation-plans/plans` | 398053 | 4115 | 34 |
| `frontend/src` | 257927 | 4744 | 77 |
| `backend/src/personal_ai/routing` | 249855 | 5196 | 14 |
| `backend/tests/persistence` | 246296 | 5478 | 19 |
| `backend/src/personal_ai/memory` | 200705 | 4389 | 22 |

## Review priorities

- Preserve frozen evaluation semantics and all meaningful cases. Inspect large receipts/manifests for generated representation before altering them.
- Inspect largest handwritten tests for repeated setup and mixed invariants; select bounded changes only after green baseline.
- Use `docs/README.md` → `docs/current-state.md` → owning subsystem README. Phase documents are historical or scoped evidence, not a second living status.
- No reduction or decomposition is yet accepted; inventory is diagnostic.
