> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Personal AI baseline status

2026-10-13; tested base HEAD `c029194156c570ec55f8173af969702f0265e57b` plus the reviewed working-tree patch set. Pre-existing untracked review documents preserved. Gate 0 remains in progress; Gate 1 awaits coordinator review.

- Verified local offline: 1,705 passed, 89 native/cloud cases deselected; backend Ruff passes. Frontend remains at the previously verified 123 tests in 23 files plus lint/types; this patch did not change frontend files.
- Verified native Postgres: the 46-test provider-accounting, artifact-tier, and routing-decision set passed twice (16.95s, then 17.88s with the file order reversed) against disposable per-test databases on PostgreSQL 17 (`server_version_num=170011`) with pgvector migrations. Follow-up inventory found zero leftover `pai_test_<uuid>` databases. This does not cover DynamoDB Local, cloud, live providers or deployment.
- Verified strict planning replay on the captured local macOS/Python 3.11.15 runtime: 30 rows; non-promotion; zero planner calls/tokens/quota; no measured model-answer quality and no promoted coverage. New v11 records the exact P19 event-forwarding and P21 UTC-deadline source changes; v10 and the corpus remain unchanged. Portable unit conformance uses a temporary runtime-bound lock; production replay checks remain strict.
- Existing CI evidence: [run 38348677456](https://github.com/jasonkli21/personal-ai-system/actions/runs/38348677456) predates these patches and records the two planner-evaluation failures on Python 3.12, 1,697 passing tests, and 91 skips; Python 3.11 was cancelled, while frontend and container jobs passed. No post-patch remote CI run is claimed.
- Reconciled failures: the original CI failures were strict runtime-lock comparisons, not planner semantic regressions. Native review also corrected event forwarding, UTC elapsed-time arithmetic, outdated serializer accessors, a conservative migration expectation, and a same-owner test setup that serialized before reaching shared quota-window contention.
- Cloud identity, DynamoDB/GCS operations, browser, live provider, recovery/deletion and cross-application acceptance remain open.

Next: coordinator reviews the bounded Gate 1 evidence and decides whether to accept the gate. Obtain post-patch remote CI evidence separately; keep native and external acceptance categories distinct.
