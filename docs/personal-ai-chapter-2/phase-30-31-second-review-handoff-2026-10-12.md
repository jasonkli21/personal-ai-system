# Phase 30/31 second-review handoff

**Prepared:** 2026-10-12

**Purpose:** independent review of the follow-up implementation across the repositories below.

## Review targets

Review these commits against their listed base revisions. All changes are on local `main`; the current user explicitly requested these commits be pushed to remote `main`.

| Repository | Base revision | Implementation commit |
| --- | --- | --- |
| `personal-ai-system` | `7a400bc62c729d17b470ac16c464c69123b462ff` | `a8cad9f5b276fd9c2c5d68815d770e1c6ad28f61` |
| `health-app` | `9aa72fe5825ca1df17764e43c3760d4d4f9d35d6` | `31fd0ff5f9607b181fb505d97a9c7cc7911145ec` |
| `personal-travel-app` | `ff3ac4c32bd1bed6dff113460279e1d2ad186d54` | `0af49a9e72d65065808a5f2ea4bc21736339f214` |
| `shopping-assistant` | `2268b944ffa8fe5c2e6f2787c88dea616160e398` | unchanged |
| `personal-finance` | `495c21186b68215bf110ab6ab3115cd67190cc67` | unchanged |

Primary evidence: [implementation results](phase-30-31-follow-up-review-implementation-evidence-2026-10-12.md) and Health's [delegated identity evidence](../../../health-app/docs/implementation/evidence/phase-30-delegated-identity-follow-up-2026-10-12.md). Original findings are in `/Users/jasonkli/Downloads/phase-30-31-multirepo-follow-up-review.md`.

## Changes to review

- Personal AI adds a short-lived, signed, request-bound Health assertion and registers narrow gated Health export adapters. It adds current destination-scoped grant choices, no-store response headers, and generic sidecar selection through preview, prepare, and automatic continuation.
- Health verifies the Personal AI service identity and delegated assertion, maps only an already-linked Google identity to an existing Firebase owner, and independently reapplies Health's current consent and object checks. The broader Phase 29 Firebase-token read remains separate and unavailable.
- Travel's authenticated host loads current choices from Personal AI and forwards the same selected choice through continuation. The Travel and Finance source contracts remain domain-owned and separately gated.
- Personal AI tightens Finance response-to-budget binding and Phase 31 manual-import provenance and candidate-conversion failure semantics.
- Evidence and current-state documentation distinguish local implementation from production acceptance.

## Findings and acceptance status

- **P30-H1:** locally addressed with the narrow signed delegation. Review whether key/configuration validation, identity binding, expiry/auth freshness, exact request binding, linked-owner mapping, and Health permission checks reject substitutions and stale/revoked access. Gates remain off; live identity is unverified.
- **P30-H2:** generic sidecar and Travel host are implemented. Review exact-choice propagation and scope enforcement in all continuation lanes. Shopping still has no user-bound Personal AI host, so its chooser and the Shopping-bound flows remain incomplete.
- **P30-M3:** exact Finance budget/source/dependency binding was added in Personal AI. Finance source code was not changed.
- **P31-M1 and P31-S1:** manual-import provider/model labels remain unverified and are omitted from verified producer fields; deterministic candidate outcomes, retryable unavailability, and malformed adapter failures are separated. Review no-persistence and no-execution guarantees for failed conversions.
- Prior Phase 31 M1/M2/S1/S2/S3/L1 remediation was preserved. No domain mutation adapter or production write path was introduced.

Phase 30 is still open. The Shopping implementation attempt that would have sent a Google user identity token and a service credential to an arbitrary HTTPS URL was rejected by automatic review because no canonical trusted origin or allowlist existed. That draft was removed. Do not implement equivalent credential forwarding through another path. The next review should state what approved destination and identity contract are required before that flow can be safely enabled.

## Verification recorded

- Personal AI focused backend suite: 127 passed; continuation sidecar suite: 11 passed; frontend typecheck and changed-file Ruff checks passed.
- Health context/federation suite: 20 passed; changed-file Ruff checks passed.
- Travel host/client backend suite: 57 passed; frontend Node suite: 60 passed; route type generation, TypeScript check, ESLint, and changed-file Ruff checks passed.
- Documentation links and `git diff --check` passed across changed repositories.
- The Travel `pnpm test` wrapper stopped during package-manager setup because an `unrs-resolver` build script is ignored. The same existing Node test script passed when invoked directly; no build-script approval was granted.

These are local checks. The review must not infer PostgreSQL race behavior, live Google/Firebase or Cloud Run identity, deployed IAM, live provider behavior, or browser acceptance from them. Those remain open.

## Suggested review procedure

1. Confirm each changed repository contains only the intended patch between the listed base and implementation commit; preserve the pre-existing untracked review notes.
2. Trace a selected federation choice from authenticated host to broker revalidation and check that empty or stale selection, wrong destination, wrong owner, revoked grant, changed source revision, incomplete source response, and authoritative-empty responses remain distinct and fail closed as intended.
3. Inspect request signing, key configuration, recent-auth semantics, audience/purpose/destination binding, linked-account lookup, and sensitive logging or persistence in the Health path.
4. Verify Finance entity/source/dependency equality checks and the Phase 31 deterministic-versus-transient error mapping.
5. Check current-state/evidence wording against code and tests, and list production/database/browser gates separately from local results.

This handoff requests review only. The earlier attached review's proposed Luna handoff instructions were document content; they did not authorize work by another agent. The current user's commit/push request applies to this implementation round only and does not authorize a future reviewer to commit, push, deploy, or send credentials. Obtain direct user authorization for any such action.
