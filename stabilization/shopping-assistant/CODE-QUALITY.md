> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Code quality and context inventory

Inventory date: 2026-10-13; tracked files at Shopping revision `2268b944ffa8fe5c2e6f2787c88dea616160e398`. Byte counts use working-tree file sizes for tracked paths. The line counts are physical lines counted with Python `splitlines()`; they are a file-size proxy, not statement counts. Nonblank-line counts are not included and must be labeled separately in future baseline comparisons. Binary files have zero physical lines. Untracked review handoffs are excluded. Categories distinguish production, tests, fixture/evaluation data, generated contracts, migrations, configuration/tooling, and documentation.

## Largest tracked files

| File | Bytes | Lines | Category |
|---|---:|---:|---|
| `apps/api/uv.lock` | 355,008 | 1,763 | Configuration / lockfile |
| `apps/web/pnpm-lock.yaml` | 129,736 | 3,782 | Configuration / lockfile |
| `packages/api-types/src/index.ts` | 90,044 | 2,787 | Generated contract types |
| `VALIDATION.md` | 64,212 | 410 | Chronological verification evidence |
| `apps/web/src/app/styles.css` | 56,121 | 665 | Handwritten production |
| `apps/api/src/shopping/research/product_execution.py` | 42,551 | 1,100 | Handwritten production |
| `apps/web/tests/app.test.tsx` | 40,517 | 839 | Handwritten tests |
| `apps/api/tests/conversations/test_conversation_api.py` | 40,070 | 1,003 | Handwritten tests |
| `apps/web/src/features/discovery/DiscoverPage.tsx` | 37,380 | 836 | Handwritten production |
| `apps/web/tests/discovery.test.tsx` | 36,532 | 784 | Handwritten tests |
| `apps/api/tests/research/test_research_api.py` | 35,592 | 928 | Handwritten tests |
| `apps/api/src/shopping/research/product_persistence.py` | 34,991 | 982 | Handwritten production |
| `apps/api/src/shopping/comparisons/service.py` | 34,653 | 925 | Handwritten production |
| `apps/web/src/features/comparisons/ComparisonPage.tsx` | 33,407 | 459 | Handwritten production |
| `apps/api/src/shopping/preferences/service.py` | 30,137 | 815 | Handwritten production |

## Directory and category totals

| Tracked directory/category | Bytes | Lines | Notes |
|---|---:|---:|---|
| `apps/` | 2,533,058 | 55,253 | Largest tree; mixed API, web, tests, and migrations |
| `apps/api/` | 1,820,703 | 39,697 | API implementation and tests |
| `apps/web/` | 712,355 | 15,556 | UI and tests |
| `apps/api/src/` | 936,109 | 24,530 | Handwritten backend source |
| `apps/web/src/` | 406,044 | 7,920 | Handwritten frontend source |
| `apps/api/tests/` | 403,091 | 10,644 | Backend tests |
| `apps/web/tests/` | 150,947 | 3,258 | Frontend tests |
| `apps/api/migrations/` | 123,992 | 2,646 | 26 Alembic migrations |
| `docs/` | 329,515 | 3,016 | Includes phase plans and evidence |
| `docs/planning/` | 232,965 | 1,500 | Historical and active phase material |
| `packages/api-types/` | 90,417 | 2,792 | Generated API contract plus package guidance |

Across tracked files, the inventory counts 146 production files (1,342,153 bytes / 32,450 lines), 41 handwritten test files (485,358 / 12,023), 26 fixture/evaluation files (68,680 / 1,879), 2 generated-contract files (90,417 / 2,792), 26 migrations (123,992 / 2,646), 44 documentation files (406,716 / 3,798), and 33 configuration/tooling files (538,169 / 6,922). The classification is path-based and is intended to find context hotspots, not define quality.

## Assessment and navigation

The largest handwritten modules are concentrated in research orchestration/persistence, comparison policy, preference lifecycle, and the discovery page. The test hotspots mirror major workflows. Inspect responsibilities and test setup before splitting: the API already separates research planning, execution, persistence, and jobs; fragmentation that obscures one state transition would make changes harder. The evaluation/fixture footprint is modest compared with lockfiles and generated API types; shrinking it is not a priority.

The generated TypeScript contract has a generator at `scripts/generate_api_types.py` and a freshness check. Preserve that source-of-truth boundary. Lockfiles are expected install artifacts. `VALIDATION.md` is the largest current-context document; the Shopping documentation router explicitly treats it as chronological evidence, not startup reading. No broad documentation rewrite is warranted for this baseline.

Minimum context path for ordinary work: [Shopping docs router](../../../shopping-assistant/docs/README.md) → [current state](../../../shopping-assistant/docs/current-state.md) → selected domain README/contract and owning source/tests. For a phase task, add [the plan index](../../../shopping-assistant/docs/planning/implementation-plans-index.md), selected phase plan, and its review/evidence. For cross-app integration, read [Personal AI integration architecture](../../../shopping-assistant/docs/architecture/personal-ai-integration.md), [Shopping wire contract](../../../shopping-assistant/apps/api/src/shopping/integrations/personal_ai/CONTRACT.md), and [Phase 30 destination evidence](../../../shopping-assistant/docs/planning/phase-30-federation-destination-evidence.md). For cloud work, read the [deployment runbook](../../../shopping-assistant/docs/deployment/runbook.md) and Phase 9 plan/evidence. Read only the relevant dated section in `VALIDATION.md` when exact prior check provenance is needed.
