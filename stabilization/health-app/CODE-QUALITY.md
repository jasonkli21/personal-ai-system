> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Health app code-quality inventory

**Inventory date:** 2026-10-13. **Basis:** 376 tracked files at `7fb84c76217c772b2bce6715744b8294afafa771`. Bytes are exact tracked file sizes; “nonblank lines” counts UTF-8 text lines containing non-whitespace. Binary files contribute bytes and zero text lines. This is a diagnostic inventory, not an LOC target.

## Repository totals by category

| Category | Files | Bytes | Nonblank lines |
| --- | ---: | ---: | ---: |
| Handwritten production code | 179 | 1,423,377 | 37,998 |
| Documentation | 83 | 706,784 | 6,880 |
| Generated contracts | 2 | 633,213 | 22,648 |
| Handwritten tests | 65 | 472,093 | 12,514 |
| Configuration/manifests | 18 | 384,004 | 8,626 |
| Lock/vendor/build output | 2 | 125,968 | 1,739 |
| Migrations | 19 | 108,298 | 2,543 |
| Fixtures/evaluation | 1 | 6,835 | 252 |
| Other | 7 | 7,100 | 196 |

Classification is path/name-based and should be read with the file list. The OpenAPI JSON and generated API client are classified as generated contracts; `pnpm-lock.yaml` and `requirements-runtime.lock` are lock artifacts. No tracked vendor tree or evaluation corpus dominates this snapshot.

## Largest tracked files

| Bytes | Nonblank lines | Category | File |
| ---: | ---: | --- | --- |
| 499,464 | 18,472 | Generated contract | `contracts/openapi/openapi.json` |
| 363,370 | 7,956 | Lock/config | `pnpm-lock.yaml` |
| 133,749 | 4,176 | Generated contract | `packages/api-client/src/generated.ts` |
| 124,130 | 1,653 | Lock/config | `services/api/requirements-runtime.lock` |
| 66,346 | 1,337 | Production | `services/api/src/health_api/persistence/models.py` |
| 46,998 | 1,226 | Production | `services/api/src/health_api/application/analytics_artifacts.py` |
| 44,696 | 956 | Production | `services/api/src/health_api/application/healthkit_import_service.py` |
| 44,112 | 1,047 | Production | `services/api/src/health_api/application/daily_service.py` |
| 43,714 | 1,033 | Production | `services/api/src/health_api/application/planning_schedules.py` |
| 35,431 | 312 | Documentation | `docs/api/api-contract.md` |
| 34,931 | 1,083 | Production | `services/api/src/health_api/api/planning.py` |
| 33,783 | 977 | Production | `apps/mobile/src/features/planning/screens/PlanningEditorScreen.tsx` |
| 32,453 | 892 | Production | `services/api/src/health_api/api/daily.py` |
| 31,024 | 907 | Production | `apps/mobile/src/features/daily/components/DailyEntryForm.tsx` |
| 29,163 | 788 | Production | `apps/mobile/src/features/daily/screens/TodayScreen.tsx` |
| 28,117 | 684 | Production | `services/api/src/health_api/application/planning_resources.py` |
| 26,027 | 100 | Documentation/plan | `docs/implementation/phases/phase-9-implementation-plan.md` |
| 25,526 | 685 | Test | `services/api/tests/test_daily_domain.py` |
| 24,643 | 281 | Documentation/review | `docs/implementation/evidence/phase-9-independent-review.md` |
| 24,585 | 677 | Test | `services/api/tests/test_account_data_api.py` |
| 24,475 | 122 | Historical documentation | `docs/history/coordinator-state-archive.md` |
| 24,464 | 573 | Test | `services/api/tests/test_daily_api.py` |

## Largest directories

| Bytes | Nonblank lines | Dominant category | Directory |
| ---: | ---: | --- | --- |
| 1,328,436 | 31,215 | Production | `services/` (`services/api/`) |
| 876,481 | 21,250 | Production | `services/api/src/health_api/` |
| 713,322 | 21,352 | Production | `apps/mobile/` |
| 651,825 | 5,954 | Documentation | `docs/` |
| 546,330 | 16,453 | Production | `apps/mobile/src/` |
| 500,474 | 18,483 | Generated contracts | `contracts/` |
| 495,182 | 14,851 | Production | `apps/mobile/src/features/` |
| 488,482 | 4,463 | Documentation | `docs/implementation/` |
| 436,138 | 10,765 | Production | `services/api/src/health_api/application/` |
| 324,511 | 8,187 | Tests | `services/api/tests/` |
| 312,099 | 3,487 | Documentation/evidence | `docs/implementation/evidence/` |
| 185,813 | 4,906 | Production | `services/api/src/health_api/api/` |
| 168,064 | 774 | Plans | `docs/implementation/phases/` |
| 155,670 | 4,586 | Tests | `apps/mobile/tests/` |
| 103,057 | 2,440 | Production/domain | `services/api/src/health_api/domain/` |

## Triage and context notes

- **Generated output:** `contracts/openapi/openapi.json` (499 KB) and `packages/api-client/src/generated.ts` (134 KB) are expected to be large because they describe the API. FastAPI source is authoritative; CI runs the API-client generator and checks both artifacts for drift. Keep source/generator commands in the OpenAPI and API-client READMEs, and fix source before regenerating output.
- **Locks/configuration:** `pnpm-lock.yaml` and the hash-pinned Python runtime lock are dependency evidence. Do not prune them as source bloat; changes require dependency/compatibility review.
- **Production hotspots:** `models.py`, `analytics_artifacts.py`, `healthkit_import_service.py`, `daily_service.py`, and `planning_schedules.py` merit function/invariant review when those domains are next changed. Current-state documentation already records decomposed analytics, planning, and AI-context façades; avoid splitting solely for size. `models.py` is one relational mapping module, so assess cohesive table ownership and import context before any separation.
- **Route/mobile hotspots:** `api/planning.py`, `api/daily.py`, `PlanningEditorScreen.tsx`, `DailyEntryForm.tsx`, and `TodayScreen.tsx` are the largest UI/transport entry points. Review for transport/policy or editing/presentation mixing in the corresponding user-journey task; no broad refactor is justified by this baseline alone.
- **Tests:** the largest are `test_daily_domain.py` (685 nonblank lines), `test_account_data_api.py` (677), and `test_daily_api.py` (573). Retain specification readability. The new `test_personal_ai_context_db.py` seed helper is a concrete compact setup fix: establish FK insertion order without introducing broad fixtures or disabling constraints.
- **Documentation:** `docs/README.md` routes by task and `docs/current-state.md` is the single living delivery summary. The plan/evidence archive is large, but phase plans are scope references and evidence records explain what ran; prefer selective routing and date/status labels over deleting useful provenance. `docs/history/coordinator-state-archive.md` is already under `history`.
- **Generated and deployment status:** `packages/api-client/README.md`, `contracts/openapi/README.md`, CI workflow, and `infra/gcp/README.md` should remain the canonical source/generation/release guides. The current CI failure is a concrete Terraform format issue, not evidence that Terraform-generated output is generally stale.

No behavioral/code-quality edits were made in Health during this Gate 0 inventory.

## Gate 1 static-check follow-up — 2026-10-13

The inventory above remains an exact snapshot of base HEAD `7fb84c76217c772b2bce6715744b8294afafa771`; it does not recalculate bytes or logical lines from the uncommitted working tree. The CI-scoped Ruff lint and format commands now pass across 108 files after fixing 9 import-order findings and formatting 11 files. Strict mypy now passes across 70 source files. Its three prior diagnostics were narrow typing issues: the Firebase SDK UID is now captured and validated before return, and the federation schema version constant is explicitly final so the Pydantic literal defaults remain typed. No broad module split was justified by these findings.

The current source set remains scoped to Health: the original six working-tree fixes were preserved, with formatter updates and the two typing cleanups. See [STATUS.md](STATUS.md) and [QA.md](QA.md) for the complete command/results record. Mobile and generated-client checks remain unverified until the repository's pinned pnpm 9.15.0 is available.
