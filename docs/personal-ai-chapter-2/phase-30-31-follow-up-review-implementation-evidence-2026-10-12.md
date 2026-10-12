# Phase 30/31 follow-up review implementation evidence

**Date:** 2026-10-12

**Reviewed input:** `phase-30-31-multirepo-follow-up-review.md`
**Verification basis:** working-tree changes on the reviewed repository heads below; no commits were created.

## Repositories and tested base revisions

| Repository | Base `HEAD` |
| --- | --- |
| `personal-ai-system` | `7a400bc62c729d17b470ac16c464c69123b462ff` |
| `health-app` | `9aa72fe5825ca1df17764e43c3760d4d4f9d35d6` |
| `personal-travel-app` | `ff3ac4c32bd1bed6dff113460279e1d2ad186d54` |
| `shopping-assistant` | `2268b944ffa8fe5c2e6f2787c88dea616160e398` |
| `personal-finance` | `495c21186b68215bf110ab6ab3115cd67190cc67` |

All five local branches matched the review's stated heads. Checks below ran against the uncommitted working-tree overlays. Existing untracked review/handoff documents were preserved.

## Findings addressed

### Phase 30

- **P30-H1, locally addressed:** Personal AI now creates a short-lived Ed25519-signed Health assertion only after normal Google identity verification. It binds the Health audience, recent-auth time, exact request body, purpose, and destination. Health verifies the assertion and Personal AI service identity, maps only an already-linked Google identity to its existing Firebase owner, and rechecks Health-owned consent and object authority. The broader Phase 29 Firebase-token read contract remains unavailable. Both federation gates remain off.
- **P30-H2, partly addressed:** the generic sidecar accepts bounded current federation choices and carries the exact selection through preview, prepare, and automatic continuation. Travel loads current choices under its authenticated host and forwards the selected choice. Shopping still has no supported user-bound Personal AI host.
- **P30-M3, addressed locally:** Finance response binding checks the selected budget entity, canonical source and record references, purpose/version, dependency, revision, and bounded fields before accepting the source response.
- **P30-M1 remains open:** source adapters and generic broker work do not constitute four accepted destination-product flows. The Shopping destination/identity host is missing, so the two Shopping-bound flows cannot be accepted; live Health-to-Travel execution and revocation also remain unverified.

The attempted Shopping client would have sent both a Google user identity token and a service credential to an arbitrary configured HTTPS origin. Automatic approval review rejected that egress because the repository has no canonical trusted origin or allowlist. The draft client/configuration was removed. No alternative path forwards those credentials.

### Phase 31

- **P31-M1, addressed locally:** user-declared provider/model labels from manual imports are omitted from verified producer attribution. The canonical attribution fingerprint still binds the full source record.
- **P31-S1, addressed locally:** candidate conversion has typed deterministic not-applicable/invalid outcomes, transient unavailability, and malformed-adapter contract failure semantics. Deterministic failures do not persist proposals; transient failures remain retryable.
- The review's previously resolved M1/M2/S1/S2/S3/L1 framework boundaries were preserved; no mutation controller rewrite or domain write adapter was added.

## Checks run

- Personal AI backend focused federation, Health federation, Finance binding, and mutation suite: **127 passed**.
- Personal AI changed backend Ruff checks: **passed**.
- Personal AI continuation sidecar tests: **11 passed**; frontend typecheck: **passed**.
- Health context contract and federation export suite: **20 passed**; changed-file Ruff checks: **passed**.
- Travel Personal AI host/client backend suite: **57 passed**; changed-file Ruff checks: **passed**.
- Travel frontend Node regression suite: **60 passed** using the bundled Node runtime. Travel Next route type generation, TypeScript `--noEmit`, and ESLint on the changed frontend files: **passed**.
- The `pnpm test` wrapper attempted dependency installation and stopped because pnpm reports the `unrs-resolver` build script as ignored. The same existing Node test script passed when run directly; no build-script approval was granted.

## Remaining acceptance gaps

- Phase 30 remains open until all four exact destination-product flows work through authenticated hosts and the required revocation, wrong-owner, stale-grant, incomplete-source, and authoritative-empty cases are accepted.
- Shopping requires a canonical, trusted Personal AI HTTPS origin and an approved user-bound identity/service authentication contract before implementation can safely send credentials there. The current repositories do not establish either.
- PostgreSQL-backed grant races, live linked-account and service identity checks, deployed IAM, provider behavior, and browser/device acceptance were not established by the local suites above. Federation gates remain disabled.
- Phase 31's generic candidate framework is locally covered; real domain mutation adapters, target-store effects, and deployment acceptance remain out of scope and unavailable.

No cloud, provider, emulator, database-backed, or production acceptance is claimed by these offline checks.
