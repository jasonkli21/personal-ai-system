# Owner profile portability remediation — 2026-11-03

Starting revision: `bc4a0b555f8885ef03135a3358384c6f182baf3f`. This local
remediation addresses the profile-route and portable-file findings from the
independent handoff. It does not change the production release decision.

## Findings closed locally

| Finding | Change and regression evidence |
| --- | --- |
| Legacy correction bypassed recent authentication and revision CAS | Both `PUT /v1/profile` and `POST /v1/memory/control/portability/profile` require a recent verified builtin owner and `expected_revision`. Both use the canonical profile repository writer. A stale principal receives 401; two edits claiming the same old revision yield one accepted edit and 409 conflicts on both routes. Wrong-audience and external-client requests are denied without changing profile state. The profile revision and existing grant invalidation remain canonical. |
| Legacy profile read bypassed the owner deletion fence | The legacy route now reads through `profile_snapshot`. In-memory and Postgres `get` use the same fenced read boundary. A fenced owner receives a content-free 503 on both profile read routes. Owner → consent → profile lock order is unchanged. |
| Portable v1 accepted grant-shaped metadata and impossible creation time | Portable fields now use a closed four-key schema. Even empty sharing metadata is rejected. Creation time more than five minutes in the future is rejected; historical observations remain accepted. Rehashed adversarial manifests and normal round-trip preview are covered. |
| Browser component/proxy coverage was narrow | Tests cover exact download Blob bytes and URL cleanup, exact upload file sent to inert preview, absence of an import write call, pending-response suppression after identity change, bounded 413/422/503 messages, flag/media-type denial and upload timeout cancellation. |

The current flags remain default-off. Export remains limited to
`explicit_profile`; `import_commit=false` and verified knowledge revision/export
remain unavailable. No model/provider invocation, external send, or data write
was added to import preview. Previously downloaded bytes remain outside managed
revocation.

## Verification

| Command/check | Result |
| --- | --- |
| `backend/.venv/bin/python -m pytest -q -m 'not loopback_http' backend/tests/test_profile_consent.py backend/tests/test_memory_control_api.py backend/tests/test_pi6.py backend/tests/test_planning_experiment.py::test_current_planning_lock_binds_owner_portability_source_without_promoting backend/tests/test_planning_experiment.py::test_workflow_source_identity_generations_preserve_frozen_inputs` | **PASS**, 111 passed, 11 loopback cases deselected. Includes same-principal stale-auth and stale-revision checks on both correction routes, both fenced reads, forged portable files, source-generation preservation and non-promotion. |
| `frontend` focused portability panel and proxy Vitest files | **PASS**, 13 passed. |
| Full `frontend` `pnpm run typecheck`, `pnpm run lint`, `pnpm test` | **PASS**; 141 tests across 26 files. |
| `frontend` `pnpm run build` | **PASS**; Next.js production build. Next emitted its existing ESLint plugin configuration warning. |
| `make backend-lint` | **PASS**, Ruff clean. |
| `make naming-policy-check` | **PASS**, naming policy plus 2 checker tests. |
| `make memory-control-eval` | **PASS**, 36/36 synthetic cases; no unauthorized simulated mutations. |
| `make planning-eval` | **PASS**, lock v35; planner calls 0; decision remains `non_promotion`. |
| `make sdk-check` | **PASS**, 379 passed, 12 loopback cases deselected, zero blocked network attempts. |
| `make consent-check` | **BLOCKED**, sandbox denied the local fence socket bind (`PermissionError: Operation not permitted`). No consent gate is claimed from this attempt. |
| `UV_CACHE_DIR=/private/tmp/pas-uv-cache PATH="$PWD/backend/.venv/bin:$PATH" make consumer-contract-check` | Build, inventory and core probes passed; installed signed-HTTP phase **BLOCKED** by sandbox socket-bind denial: 102 passed, 91 errors. No consumer failure is attributed to the profile change. |
| `make backend-test-offline` with SDK/reference package paths | **NOT GREEN**, 2,408 passed, 12 failed, 1 skipped, 155 deselected, 92 errors; 224.52 seconds. Many signed HTTP, retrieval and local-loopback fixtures fail setup because the sandbox denies socket binds. The broad result is not attributed wholesale to this remediation; focused profile and portability tests pass. |
| Native PostgreSQL/pgvector two-worker tests | **NOT RUN**; `PERSISTENCE_TEST_POSTGRES_DSN` is unset, `pg_isready` reports no server on `/tmp:5432`, and Docker is unavailable. |
| E3–E5 identity/provider/deployment/restore/erasure/utility checks | **NOT RUN / BLOCKED**; no provisioned service or approval is present. |

The preserved planning baseline is advanced additively to v35, and PI-6 source
generation 9 binds the changed profile API test harness and runtime. Prior locks,
manifests, frozen cases, scorer, thresholds and non-promotion remain unchanged.

## Remaining release gates

Owner portability remains `BEFORE_ENABLEMENT`; production remains **NO-GO**.
This session self-reviewed the exact diff; no follow-up independent review was
conducted. Deployed Google/IAM identity, atomic send/revoke ordering, native
concurrency, restore and anti-rollback, physical erasure, real provider/billing
controls and longitudinal utility remain unverified. Do not enable live data or
import commit while those gates remain open.
