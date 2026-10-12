# Phase 30/31 third-review remediation evidence

**Date:** 2026-10-12
**Reviewed input:** `phase-30-31-third-independent-review-handoff-2026-10-12.md`
**Personal AI tested fix commit:** `05208aca144c872bfc1398be2de6e543c8abe812`
**Base:** `7e707df38621f114c10774aa9b4535e2d11a7ca9`

## Findings addressed

- **P30-H1A:** The verified principal now keeps Google token issue time (`iat`) separate from the actual upstream authentication time. Only the verified Google ID-token `auth_time` claim populates `authenticated_at`. Missing authentication time remains unknown; malformed or future claims are rejected, and recent-auth checks reject absent, stale, or future values. Health delegation signs this verified fact as `auth_time`; token freshness remains a separate check.
- **P30-H1B:** Health allows the narrow federation-export feature gate to be enabled while broad context-read remains disabled. Shared Health service-identity configuration is required if either gate is enabled; federation-specific key validation remains tied to the federation gate.
- **P30-H2A:** Travel's central hosted AI-sidecar path classifier now recognizes the federation-choice route. See the Travel release follow-up for its code commit and environment-limited middleware test.
- **P30-M4:** Choice responses expose only a destination-scoped opaque HMAC handle and a display-safe category label. The handle binds grant identity and issuance lifetime, owner/actor, source and destination scope, revision/epoch/state, purpose, entities, fields, and expiry. A configured 32-byte secret is required when a relevant integration gate is active. Browser continuation payloads accept handle IDs only; server resolution reloads the canonical grant for the exact owner, actor, and destination. Stale, revoked, wrong-destination, or recreated issuance handles do not resolve.
- **P30-M5:** Choice discovery examines at most 100 destination grants and performs local grant/handle checks only. Handle resolution also stays local and fetches no source values. Source authority and adapter authorization are still fully rechecked by the broker when a selected choice is actually used.
- **P30-H2B:** Shopping's authenticated destination host remains deferred. Arbitrary-HTTPS credential forwarding was not restored; Phase 30 remains open.

No Phase 31 or Finance code was changed in this pass; the review marked their prior findings resolved.

## Verification

- Personal AI auth-time focused tests: **12 passed**.
- Personal AI federation, settings, and Travel-context focused tests: **75 passed**.
- Personal AI backend Ruff checks: **passed**.
- Personal AI frontend Vitest: **123 passed** across 23 files; TypeScript `--noEmit`: **passed**.
- Health context/federation contract suite: **19 passed**; changed-file Ruff: **passed**.
- Travel backend context/client suite: **57 passed**; changed-file Ruff: **passed**.
- Travel frontend Node tests: **60 passed**; changed-file ESLint and TypeScript `--noEmit`: **passed**.
- Travel hosted federation-choice middleware integration test: **skipped**, because `TEST_DATABASE_URL` is unset.
- `git diff --check` passed in all three repositories after documentation edits. Travel's `make docs-check` checked **225 local Markdown links** across 73 files; added Personal AI and Health evidence links were reviewed and their targets verified.

## Remaining gaps

The database-backed Travel middleware test, PostgreSQL grant races, deployed IAM/service identity, live linked-account behavior, provider behavior, and browser/device acceptance remain unverified. No cloud, provider, emulator, or production acceptance is claimed. Both Health gates and the relevant federation integrations remain disabled by default. Phase 30 is incomplete until the required destination product flows and their live/revocation acceptance are covered; the dedicated Shopping identity/destination-host subphase remains outstanding.
