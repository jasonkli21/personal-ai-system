# Phase 35 independent-review remediation evidence

**Date:** 2026-10-12
**Reviewed implementation commit:** `f4a248a266317cc9f74a1c8466685612d9a5cb15`
**Scope:** Findings F35-01 through F35-07 in the independent post-implementation review.

## Finding disposition

| Finding | Disposition | Change |
| --- | --- | --- |
| F35-01 | **Open; partially addressed** | Added canonical FastAPI routing-service composition through the shared persistence factory. It requires an app-installed current authorization authority and returns 503 when that authority is absent. No user workflow consumes it: Phase 15 membership/revocation acceptance and provider-neutral dispatch integration remain open. The report and current-state docs now say shadow is not production-reachable. |
| F35-02 | Addressed | Added an injected adaptive strategy registry with opaque strategy IDs/versions, implementation compatibility checks, distinct-ID registration, and deterministic fallback for unknown/unavailable configuration. |
| F35-03 | Addressed | Promotion evaluation now emits pass/fail/unverified gates per coverage and computes the declared quality, resource, pipeline-latency, overhead, abstention, calibration, completeness, compatibility, and independent-group gates. Promotion is returned only when all gates pass. |
| F35-04 | Addressed | Dataset manifests now hash normalized configuration facts separately from source observation identity. Tests cover owner/request/root/timestamp invariance, configuration changes, and corpus changes. |
| F35-05 | Addressed under the bounded synchronous strategy contract | The registry requires the code-reviewed `bounded-pure-in-process-v1` contract. Such strategies must be deterministic, local, and bounded; I/O and unbounded work are unsupported. The 5 ms value is documented as a post-hoc observation threshold, not a timeout. This does not make arbitrary Python code preemptible. |
| F35-06 | Addressed | Source inspection hashes are cached by callable identity; class methods rather than per-instance bound methods are used for reusable strategy identities. |
| F35-07 | Addressed | The machine summary reports non-abstaining proposals, supported alternative comparisons, live holdout group counts, pipeline-complete groups, abstention reasons, and explicit quality-comparison status. Route agreement is labeled as non-quality evidence. |

F35-01 is intentionally not closed by routing production chat through P21. Current project status keeps P21 workflow integration behind Phase 15 authorization/revocation acceptance, and current generation has no provider-neutral transport that can honor alternate P21 selections. The new dependency establishes the canonical composition boundary and fails closed; it is not evidence of workflow integration.

## Frozen synthetic evidence

The synthetic snapshot retains 80 executed cases, 56 coverage identities, one conservative family group, and no live paired pipeline comparisons. All 80 shadow proposals abstain with `supported-signals-missing`; visible deterministic-route agreement remains 80/80 and does not count as quality evidence. The refreshed dataset digest is `0cbe5bffb03df5577d6ca015e3baf07dac2043a277617d273636cb7de27e248e`. The local run measured 41–151 µs of strategy overhead and 3,650 µs total strategy CPU. No coverage is promoted.

The Phase 32 planner freeze advanced to v8 to bind the changed backend source tree. Its corpus and non-promotion decision are unchanged; v7 remains preserved as historical evidence.

## Verification

**Tested revision:** base `f4a248a266317cc9f74a1c8466685612d9a5cb15` plus the review-remediation working tree. The final backend source identity digest is `daf2bdc6e3edc066b290cc8a9e70a884715cb78b13d1ca9730d0a16e2c5fab85`.

- `cd backend && ./.venv/bin/python -m pytest -q` — **1,672 passed, 91 skipped**; two existing dependency warnings.
- `cd backend && ./.venv/bin/ruff check ...` for the changed API, routing, persistence, evaluation, and test modules — passed.
- `cd backend && ./.venv/bin/python -m personal_ai.evaluation.adaptive_routing` — passed; 80 cases, 80 abstentions, no promoted coverage.
- `cd backend && ./.venv/bin/python -m personal_ai.evaluation.planning` — passed against the v8 freeze; corpus and non-promotion decision unchanged.
- `git diff --check` — passed.

No provider, database, emulator, cloud, deployment, or production-security checks were run. F35-01 remains open until Phase 15 authorization/revocation acceptance and provider-neutral workflow dispatch are complete.
