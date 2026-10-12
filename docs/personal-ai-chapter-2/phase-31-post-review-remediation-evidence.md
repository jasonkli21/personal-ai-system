# Phase 31 post-review remediation evidence

Date: 2026-10-11. Tested revisions: Personal AI Phase 30 base `695f020` plus the Phase 31 changes in this commit. The Phase 30 source work is committed separately. This evidence records local code and focused checks, not live domain mutation or production acceptance.

## Review findings addressed

- **M1 — canonical provenance.** Proposal creation now accepts an opaque completed-output handle and operation selector at `POST /v1/mutations/candidates`. The server resolves the owner/application/workspace-scoped active assistant output, reads its persisted `TurnAttribution`, and asks the registered adapter to derive typed intent. Producer attribution and source snapshots are built server-side. The previous public create contract accepting caller-authored snapshots is removed.
- **M2 — operation retirement.** Proposal intent binds an immutable contract fingerprint. Runtime contributions can retain fingerprint-keyed reconciliation adapters after current write policy is retired. Startup checks retained proposal contracts and fails if a resolver is absent. Reconciliation continues through the retained adapter without re-enabling new writes.
- **S2 — transient pre-send failures.** Authority and permission-check exceptions are classified as unavailable and return HTTP 503 while leaving the exact confirmed binding retryable. Authoritative denial/staleness remains terminal; after reservation, ambiguity remains `uncertain` and cannot resend.
- **S3 — public projection.** Browser responses omit the domain operation key, execution/reconciliation identifiers, lease, raw source dependencies, and operation fingerprint.
- **L1 — control reads.** Internal control loading and disclosure-safe `read_view`/`_present` are distinct APIs; the route uses the safe projection.
- **S1 — host path.** A synthetic application host fixture starts from a completed output, creates a candidate through the Next.js proxy, passes the returned opaque proposal ID to the ordinary sidecar panel, and then validates, confirms the exact binding, applies, and displays the authoritative receipt through the same proxy. The paired backend fixture resolves canonical attribution and exercises the registered synthetic adapter. No real domain operation is currently declared or supplied by a product host.

## Verification and remaining gaps

- Mutation backend suite: **46 passed**; the separate Phase 30 federation/Finance/Travel focused suites: **67 passed**. Ruff passed on changed backend files.
- Frontend Vitest suite: **122 passed** across 23 files; application and test TypeScript checks passed; ESLint passed for changed sidecar/API files.
- Existing synthetic tests cover canonical active-output resolution, adapter conversion, caller-authored provenance rejection, compatibility fingerprint mismatches, startup retention guard behavior, retryable authority outages, permission outages, explicit revocation, and public redaction.
- No live domain mutation adapter is enabled. The startup compatibility query was exercised through synthetic tests, not against retained production Postgres state. Domain-side atomic authorization/write/receipt behavior, application-host UX, browser review, cloud identity, and deployment remain open.
