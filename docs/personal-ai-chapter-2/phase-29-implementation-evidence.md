# Phase 29 implementation evidence — Health integration

Date: 2026-10-11
Personal AI base revision: `158b569e7ad28c350f701b7e78d1fd38f2127b6d`
Health base revision: `a0c170a7e39a88efae65ecbf4ebffdb07b7461a0`

## Delivered locally

Personal AI now has a versioned, read-only Health provider over the existing
Application Integration Contract seams. The Health wire version is
`health-context-read-v1`; the provider registers separate profile and history
capabilities through the shared context runtime, planner, coordinator,
permission revalidator, application registry, policy, and assembler. No
provider-specific planner, router, memory, or orchestration path was added.

Health remains canonical. Its separate read-only endpoint resolves only an
existing `(issuer, subject)` owner mapping after verifying an exact Google
service identity and a recent, revoked-checked Firebase user token. It applies
the existing owner/current/item-permission eligibility predicate plus the
independent cross-domain permission before either cataloging or fetching a
category. Requests are bounded by category, fields, entity references, time
window, result count, request bytes, and response bytes. The projection keeps
source and object references, source revision, authority, effective and
observed time, units, quality/unknown uncertainty, field sensitivity, and
permission dependency versions. There are no write, proposal, or memory
operations, database credentials in Personal AI, or duplicate Health state.

Personal AI maps Health categories to distinct provider capabilities. Its
Health policy is restricted, cross-app use is denied, external execution and
external disclosure are disabled, manual import/reuse is denied, copy is
allowed, and no draft targets or Health action tool are registered. Existing
Health local preview/search and Assistant messaging behavior remain separate.

## Architecture audit and adjacent phases

- State, permissions, and domain truth remain owned by Health; Personal AI
  stores only bounded context for the current preparation flow.
- Reads reuse Health's shared SQL admission predicate rather than duplicating
  local AI permission logic. The cross-domain requirement is an optional
  extension, so existing local preview and search callers retain their
  behavior.
- Authentication carries separate service and user credentials; request
  scope and a body-supplied owner are never authority. Owner creation and
  email-based identity matching are absent.
- The existing shared context provider, planning, policy, assembly, and
  permission revalidation contracts handle the new app. The generic source
  reference kind was extended to preserve Health provenance.
- Phase 30 can add generic grant/revocation dependencies over these provider
  capabilities. Phase 31 can add a typed domain-authorized proposal seam
  without changing this read-only contract. Neither phase's state machine or
  persistence was pulled forward.
- No Health-specific branch was added to generic layers, and no alternate
  routing, retry, accounting, context, or persistence mechanism was introduced.

## Verification

- Personal AI focused tests: `test_health_context.py`,
  `test_applications.py`, and `test_settings.py` — 36 passed.
- Health API suite — 179 passed, 73 skipped. The skipped database-backed tests
  require `TEST_DATABASE_URL`; this run does not establish PostgreSQL behavior.
- Personal AI context evaluation — 5/5 fixtures passed.
- Personal AI context-planner evaluation — 9/9 fixtures passed, including
  synthetic undeclared-provider fixtures.
- Ruff passed for all touched Personal AI and Health Python files.
- Health Mypy passed for the 8 touched API source files.
- Personal AI backend lint and wheel/source build passed.
- `git diff --check` is recorded after final evidence edits.

The full Personal AI backend suite was attempted but could not complete
collection in the available local interpreter: the checked environment lacks
the Pub/Sub dependency, and the repository-local environment lacks SQLAlchemy.
The focused changed-surface tests and deterministic evaluations above ran
successfully; the full suite is not claimed as passed.

## Deferred activation and intentional deviations

The implementation remains a local, default-off contract. Health requires a
recent Firebase ID token, while the current Personal AI adapter supplies a
verified Google OIDC user token. There is no safe delegated-token bridge or
accepted identity mapping between those contracts. Health's read gate and
Personal AI's Health provider gate therefore remain false. No same-owner,
email, or request-body shortcut was added.

Health daily records also default `cross_domain_use_allowed` to false, and the
current owner-facing interface has no control to grant it. The catalog
therefore offers no daily category until Health has an explicit supported
permission path. The read-only sidecar category selector is deferred for the
same reason: listing a static or unverified category would violate the plan's
requirement to show only categories authorized by Health. Copy remains the
only allowed sidecar action; no non-authoritative draft target exists. This
deviation preserves the authorization boundary and does not claim sidecar or
live integration acceptance.

`PERSONAL_AI_ENABLED`, `/assistant/messages`, and Health mutation behavior are
unchanged. Live Firebase/Google IAM verification, PostgreSQL execution,
provider privacy/use review, cloud deployment, mobile credential behavior,
real-data safety, and sidecar behavior remain unverified. Health's OpenAPI
export could not write its repository artifact from the restricted temporary
execution context; the generated-client command was also unavailable because
the installed pnpm version is outside the repository's supported range.

## Post-implementation review follow-up — 2026-10-11

Health daily Event and Observation owner create/update requests now expose
`cross_domain_use_allowed`, defaulting to false. Updates use the existing
expected-revision path, advance the canonical object revision, and record both
consent flags in revision history. Health context permission versions include
the monotonic revision and the current source-consent state, so revoke/regrant
does not restore the old dependency version. A future Phase 30 federation
grant remains a separate prerequisite; effective access must require both
source consent and the federation grant.

The shared Personal AI `ContextItem` and source envelope carry generic partial
result information. Truncated Health responses remain available as explicitly
partial. Health provider capabilities are now unavailable in the registry
until its Firebase owner-token requirement can be reconciled with Personal
AI's Google OIDC identity; changing the feature flag cannot bypass this gate.
The Health sidecar remains unavailable.

Verification on 2026-10-11:

- Personal AI full backend suite: **1,398 passed, 82 skipped**; Ruff passed.
- Health API/contract tests: **7 passed, 16 skipped**. The skipped cases need
  `TEST_DATABASE_URL`, so the revisioned revoke/regrant database assertion was
  not executed locally.
- Health Ruff and Mypy passed. OpenAPI JSON and TypeScript client artifacts
  were regenerated with the underlying repository scripts, and client
  typechecking passed. The repository's pnpm wrapper was unavailable because
  installed pnpm 11.25.0 is outside its supported 9.x range.
- Live identity, PostgreSQL, deployment, provider privacy, and sidecar checks
  remain unverified.
