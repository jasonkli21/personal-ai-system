# Phase 33 independent-review remediation evidence

Date: 2026-10-12. Review target: `79d74554c4c3b00fc5202340a106d789225f0274`; remediation tested as a working tree on that revision. The review handoff was `phase-33-independent-post-implementation-review.md`. Existing untracked review notes in `docs/` were preserved.

## Findings and changes

| Finding | Remediation | Status |
| --- | --- | --- |
| 1. Search dispatch omitted hard source/freshness bounds | Added immutable `SearchOperation` with query/plan identity, typed and literal allowlists, exclusions, publication bound, result cap and deadline. Brave applies expressible domain constraints and fails closed on exact mandatory publication bounds it cannot honor. Returned sources still pass defense-in-depth checks. | Addressed |
| 2. Research predicted Phase 19 physical-attempt IDs | Removed UUID-derived usage links from logical attempts. Started attempts have no physical ID; terminal attempts store IDs returned by the adapter's canonical P19 path. A P19 admission denial may link its canonical invocation while leaving the physical attempt absent. Admission denials do not retry without a known reset horizon. | Addressed |
| 3. Search composition selected synthesis and its counter | Split search composition into `search.runtime.compose_search_adapter` and synthesis composition into `llm.research.compose_research_inference`; production API factories use both independently. Non-synthetic registered search is tested through the production API composition. | Search/inference coupling addressed. Phase 21 execution-plan dispatch for request-time synthesis remains open behind the existing Gemini-only request-workflow gate; this remediation does not claim that route integration. |
| 4. Cached exports omitted embedded artifact permissions | Export manifests now union research-source permissions with permission dependencies inherited from embedded artifacts, retain grant dependencies and expiry, and fail closed above the bounded dependency limit. | Addressed |
| 5. Iterative research used a parallel planning envelope | Iterative physical searches now use the same immutable `SearchOperation` contract and persist operation/strategy identity. Follow-up qualifiers no longer encode scope as generated `site:` query syntax; allow/exclude/freshness bounds remain typed. | Addressed |
| 6. Source-rights identity conflated provider and revocation facts | Rights authorization now carries provider ID, account-derived authority ID, epoch and preflight reference. Stored dependencies revalidate against the recorded provider authority, independently of current adapter selection or feature enablement. | Addressed |
| 7. Unknown revisions were treated as equal across sources | Exact content merges across different canonical sources only when publication time and native revision are both known. Unknown metadata merges only exact same-source duplicates. | Addressed |
| 8. Frozen baseline was not a semantic gate | Added `retrieval-heldout-v2.json` and `retrieval-baseline-v2.json`. The 20-case literal control is checked against fixture outcomes and frozen state/failure/status/count invariants. Every candidate must preserve the frozen semantic state, exact support/citations, hard-bound/freshness checks, evidence/citation floors and call/query ceilings. A regression unit test changes the control state and proves the gate rejects it. | Addressed |
| 9. Provider registration remained partly provider-specific | Moved provider validation, endpoint-profile construction and iterative cost policy behind search registration metadata/provider-owned functions. Removed the `adapter.name == "fake"` cost branch. Composition verifies declared synthetic/external origin and typed cost profiles. A non-synthetic registration reaches the real single-pass API factory with controlled local accounting. | Addressed |

## Baseline and evaluation

The v2 fixture digest is `679e05ed0c6ad8be3136a1938f444cb27ec05df3997425df52e9cc1cd12d5cdc`. It preserves the v1 cases, adds typed/literal intersection and mandatory publication-bound cases, and records the corrected outcomes for unknown cross-source versions and known source revisions. The v1 baseline remains unchanged as historical evidence.

The 20-case synthetic paired run produced 60 candidate summaries and did not promote a strategy:

| Strategy | Search calls | Packed-token estimate | Total-token estimate |
| --- | ---: | ---: | ---: |
| Literal control | 20 | 18,089 | 20,381 |
| Compact extractive | 20 | 17,480 | 19,772 |
| Preserved-question qualifier | 20 | 18,089 | 20,381 |
| Bounded expansion | 39 | 21,012 | 23,304 |

Live answer quality, quota, provider behavior, and target-store behavior are unmeasured. These synthetic outcomes do not support promotion.

## Verification

- Focused backend tests: **152 passed**, covering retrieval, provider adapters, research contracts/pipeline, iterative research and artifacts.
- Full backend suite: **1,600 passed, 87 skipped**, with 2 existing deprecation/runtime warnings; 102.32 seconds.
- Paired retrieval evaluation: **20 cases / 60 candidate summaries**, `not_promoted`.
- Phase 32 planning evaluator: **30 rows / 23 coverage slices**, `non_promotion`, zero planner calls.
- External provider, P19/Postgres, DynamoDB Local, cloud, publisher-rights and GCS checks were not run; offline fakes and HTTP fixtures do not establish those behaviors.
- Phase 32's unchanged planning corpus evaluates successfully with its v4 runtime/material-source freeze; decision remains `non_promotion`. Freeze source identity digest: `cd2adf7d58cb91c60398e1d92e43a011bcb0f56ac569771dd695328b4bc2bd22`; v3 remains historical.
- The first full backend run exposed two stale Phase 32 v3-lock failures after the reviewed source changes. The versioned v4 freeze resolves those source identity failures without changing the corpus or planner outcomes.
- Ruff: passed (`python -m ruff check .`). `git diff --check`: passed. Edited documentation links resolve to existing local files; content was reviewed with the final diff.
- Tested against source revision `79d74554c4c3b00fc5202340a106d789225f0274`, with source identity bound in Phase 32 v4. Provider, database, cloud, and publisher-rights checks remain unrun as listed above.

## Remaining integration gap

Finding 3's composition defect is fixed: search registration no longer chooses the inference client or tokenizer. Research synthesis still does not obtain and execute a Phase 21 `ExecutionPlan`. The repository's current request-workflow boundary remains Gemini-only until Phase 15 source-membership and revocation acceptance is complete. Phase 33 must not be described as having canonical P21 request-time synthesis routing until that integration and its acceptance are implemented.
