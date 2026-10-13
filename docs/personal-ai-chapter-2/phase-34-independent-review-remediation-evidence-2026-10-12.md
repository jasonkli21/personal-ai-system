# Phase 34 independent-review remediation evidence

Date: 2026-10-12

Review target/base revision: `95de11c84065bb6ea2695f2e9f9309268f5841ea`

Remediation source digest: `c0a6f42aa11a33ce33990daca257bb1703b437ab2e87845b89d2898272fe2e15`

Evidence kind: local offline tests and synthetic evaluations

This record addresses the findings in the independent Phase 34 review. The
implementation remains opt-in and no retrieval strategy coverage is promoted.

## Finding dispositions

| Finding | Remediation |
| --- | --- |
| 1. Semantic near-duplicate consolidation | Added `support-v1` for a narrow, positive preference grammar. Exact value and full context clauses must match after surface normalization; negated, qualified, conflicting, or otherwise unsupported assertions remain separate. Similarity only proposes candidates. Derived views retain every exact excerpt, source ID, and dependency version. |
| 2. Exact duplicate retrieval | Every retrieval variant groups identical normalized assertions into one selected representation and retains the complete support IDs and immutable originals. The consolidated context path prefers a valid view and restores its originals if the view does not fit. |
| 3. Existing corpus and refresh triggers | The public completed-turn coordinator runs a bounded rotating corpus sweep when consolidation is enabled. Stable job intent identity includes source IDs and dependency versions, allowing retries to deduplicate while changed epochs can enqueue refresh work. |
| 4. Freshness scoring | Stable preferences receive no age decay; episodic memories use the configured relevance half-life; explicit corrections use a maximum seven-day half-life. Age changes ranking only and does not expire historical records. |
| 5. Task-conditioned query contract | Unused task, requirement, entity, and temporal fields were removed from `MemoryQuery`. Task-conditioned ranking is explicitly deferred rather than represented as an implemented capability. |
| 6. Capped reverse-link projection | Removed `consolidated_into_memory_ids` from lifecycle state. Complete reverse membership comes from `derived_memory_sources`; legacy projection payloads discard the former cache. The >8-event regression exercises the shared transition contract in both normal and persistence test paths; it does not claim native Postgres execution. |
| 7. Memory-derived artifacts | `ArtifactService.write` rejects artifacts with `ai_memory_source` or `ai_memory_view` dependencies before reservation. Memory-bearing artifact reuse is an explicit unsupported contract until artifact maintenance has scope-aware revalidation inputs. |
| 8. Persisted refresh state | Removed the durable `DerivedMemory.refresh_state` field and ignore it when hydrating legacy payloads. Current invalid/refresh-required status is computed from canonical dependencies and lifecycle state. |
| 9. Production trigger conformance | Added a public `after_completed` test that starts from a completed turn, asserts the bounded maintenance job, and exercises idempotent rediscovery/refresh behavior without calling the coordinator's private enqueue helper. |

## Verification

The review target is `95de11c84065bb6ea2695f2e9f9309268f5841ea`; the remediation
tree was evaluated before its single commit and is identified by the source digest
above.

- Backend runnable tests: 1,634 passed; 89 environment-dependent tests skipped.
- Backend Ruff: passed.
- Memory evaluation: 14/14 passed.
- Memory lifecycle evaluation: 60/60 passed.
- Planning evaluation: passed with no coverage promoted.
- Paired memory optimization: 20 cases per variant; fixed 1,004, compact 1,004,
  consolidated 1,012 packed tokens; 25 logical embedding calls and 14 maintenance
  jobs per variant; source dependency coverage 1.0; false-memory and scope-leakage
  observations zero. The 5% token-saving threshold was not met, so no variant was
  promoted.
- Documentation review and `git diff --check`: passed.

## Remaining verification limits

Native Postgres/pgvector and migration 027 execution, DynamoDB Local, cloud smoke,
live Gemini/provider behavior, deployed identity/privacy, downstream answer quality,
and native resource/free-tier measurements remain unverified. Synthetic and fake
checks do not establish those environments. No native-store or live-provider test was
run for this remediation.
