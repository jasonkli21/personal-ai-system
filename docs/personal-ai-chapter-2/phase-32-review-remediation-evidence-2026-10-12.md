# Phase 32 independent-review remediation evidence

Date: 2026-10-12. Review target: Phase 32 implementation at
`3e9452185848414410ccbbedbd228bf5f22a8bce`. The remediation was evaluated from
that Git base and is required to remain its direct child with the same material
source identity. Source identity digest:
`1041ce057469d6e72a32af7e9b89022d24c6b60980cf9d9d7025361d76bd99a4`.

## Finding disposition

- **R1 — trace dependencies and choice results:** added typed policy, schema,
  provider-spec, grant-revision/epoch, source-revision, and permission dependency
  snapshots to the existing trace. References are hashed; version/revision values
  remain exact. Each known choice records accepted, narrowed, rejected, or retained
  with a reason. Canonical planning latency is measured. Build-time source versions
  are added only after retrieval. Round-trip and privacy checks cover the trace.
- **R2 — missing measurements:** promotion-critical hard-invariant, quality-boundary,
  call, quota, proposal-validation, and rollback evidence is nullable. The gate emits
  explicit unknown-measurement reasons and denies promotion. Rollback is true only
  when every row has all required retain-control comparisons; missing evidence is
  unknown for either side.
- **R3 — baseline identity:** baseline v2 binds the source revision relationship,
  the full `backend/src/personal_ai` source tree and backend lock/config files,
  evaluator/corpus/fixture identities, Python 3.11.15/ABI, platform, and a digest of
  94 installed runtime distributions. The evaluator rejects an unrelated Git
  revision or changed material/runtime identity.
- **R4 — downstream quality and validation rates:** added an adapter to the Phase 22
  scorer. It scores only fixture sources whose transient references were actually
  injected into the exact assembled context and records strategy/configuration,
  task/scoring identity, provider/model, tested revision, context/output digests,
  and hard-boundary outcome without retaining prompts, answers, or source IDs. The
  evaluation runner also accepts identity-matched validation traces and derives
  proposal rejection, narrowing, fallback, and unauthorized-attempt counts and
  rates. No quality or validation-trace observations were supplied for this
  deterministic baseline, so those values remain null and block promotion.
- **R5 — request semantics:** explicitly marked `PlanningRequest` as
  `narrowing_validation_only`, with zero inference budget. The contract and plan now
  require a separate, privacy-reviewed assisted-selection request with typed task
  features and an independently authorized candidate envelope before any future
  model call. No model interface was enabled.
- **R6 — promotion scope:** promotion uses the same versioned typed key for
  application, task family, source pattern, and sensitivity. Application summaries
  are display-only. Tests check exact key matching and fail-closed missing fields.
- **R7 — corpus coverage:** held-out v2 adds 16 independently authorized competing
  providers under a tight context budget, exact trip-source revision 7→8
  transitions including partial revision-8 evidence, and separate synthetic grant,
  source-revocation, consent, membership, and expiry states. The families are
  intentionally grouped and remain below the 100-family promotion threshold.

## Verification

- Backend offline test suite: **1,572 passed, 84 deselected**. The deselected tests
  require persistence/cloud environments; both manual Gemini suites were excluded.
  Command:
  `python -m pytest -m 'not persistence_integration and not cloud_smoke' --ignore=tests/test_gemini_manual.py --ignore=tests/test_context_manual.py -q`
- Backend Ruff: passed (`ruff check .`).
- Planning evaluator: passed with 30 rows, 23 exact coverage keys, 22 scripted
  retain-control pairs, and the 16-candidate authorized catalog selecting one
  source. The decision is `non_promotion`; planner calls/tokens/quota are zero.
- `git diff --check`: passed after the documentation and code changes.

## Remaining evidence limits

The additional source-version and federation-race cases are synthetic; they do not
prove live PostgreSQL/DynamoDB membership, consent, or concurrency behavior. There
is no observed Phase 22 answer-quality sample, validation-trace observation, or
assisted candidate comparison, and no exact coverage key has 100 independent
families. No coverage is promoted. Live providers, deployed authentication and
authorization, production trace retention, and deferred cloud/persistence suites
remain unverified.
