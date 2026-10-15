# Five-repository stabilization re-review handoff

**Prepared:** 2026-10-14
**Scope:** Luna XHigh re-review fixes across Personal AI, Shopping, Finance,
Travel, and Health. This is the current independent-review entry point.
**External readiness:** Not established. Local/native checks below do not prove
cloud, provider, browser, or device acceptance.

## Final commits

All repositories are on `main`. Domain commit hashes will be filled after their
commits are created. The PAI commit contains this handoff, so resolve its exact
hash with `git log -1 --format=%H -- stabilization/FRESH-REVIEW-HANDOFF.md`.

| Repository | Reviewed source baseline | Final fix commit |
| --- | --- | --- |
| `personal-ai-system` | `20ef41ae6b76de691c003ae6a345fdb91b3ecd02` | Resolve with the command above |
| `shopping-assistant` | `197849e545ae74f1860a58054c8a741ccb39d9e5` | `720efc925b34ca06b4e429e0a180d1a360761029` |
| `personal-finance` | `8097060f7734525f2c8294bc77f2325d47f2c7d4` | `a6a848ac8314a5a8bfcc7a66cb9df30dd48f42b7` |
| `personal-travel-app` | `4836fb82d45a66ed2fab726eff4e31e09f9ae8fa` | `61a708b257cb9862bc415ce8a7151201489d3472` |
| `health-app` | `c3020b9c6926fd6454e5fe95b0d7fa5fa13ebb00` | `5112cad381cc38900bd1333c95fdc87c0668f00` |

## Architecture and authorization semantics

Domain applications continue to own canonical records, source consent,
revisions, domain validation, and source recovery. Personal AI owns cross-app
orchestration, grants, immutable task intent, confirmation, execution
reservation, uncertainty, and reconciliation. Shopping remains authoritative
for project identity, project revision, project validation, writes, and durable
destination receipts.

Source commands remain immutable. Each physical write is reserved once under an
execution key; an uncertain acknowledgement is reconciled by observing that
same key and never triggers a replacement mutation. Consent, grant, source
revision, target revision, and destination owner checks remain fail-closed.

The successful live Shopping execution-authority callback is the authorization
linearization point for an already-reserved execution. A revocation before the
callback denies the write. A revocation after a successful callback blocks
future writes but does not cancel that in-flight destination transaction. The
completed receipt remains observable subject to current read authorization.
Shopping's local owner-lifecycle and project locks still serialize local
deletion/revision against its effect and receipt. The two databases do not
provide global atomic revocation-to-commit ordering.

## Changes by finding

### F1 — authorization and revocation ordering

- Documented the callback linearization semantics in
  `stabilization/CROSS-REPO-CONTRACTS.md`,
  `stabilization/CROSS-REPO-INVARIANTS.md`, `stabilization/OPERATIONS.md`, and
  current-state records.
- Added deterministic grant, source-consent, and source-owner revocation-after-
  callback cases in `stabilization/tests/test_suite_tasks.py`.
- Added a Shopping PostgreSQL concurrency test proving owner purge waits for an
  effect already authorized under its local lifecycle lock.
- Kept the pre-callback revocation denial test and one-effect/receipt
  assertions. No global serializability claim or second remote callback was
  introduced.

### F2 — truthful Travel and Health recovery

- Travel now stores owner-scoped source command/body/phase/confirmation state in
  session storage and distinguishes command creation, known command, submit,
  validation, confirmation, and effect uncertainty. Health uses serialized,
  owner-scoped SecureStore recovery with the same distinctions.
- Definitive create 4xx clears the failed command so a corrected request gets a
  new identity. Ambiguous create retries the identical body and command ID;
  ambiguous submit reuses that known ID. Possible apply effects remain
  `effect_unknown` and direct the user to reconcile the original execution.
- Owner changes clear local recoverable state. Restart recovery preserves the
  original command and confirmation IDs.
- Tests: `frontend/tests/shopping-task-recovery.test.mjs`,
  `frontend/tests/shopping-project-select.test.mjs`,
  `apps/mobile/tests/shopping-task-recovery.test.ts`, and
  `apps/mobile/tests/shopping-project-picker.render.test.tsx`.

### F3 — user-facing Shopping project choices

- Added a closed, typed read-only target-choice contract through Shopping →
  Personal AI → Finance/Travel/Health. Shopping returns only project ID, title,
  and current revision for the linked owner's active projects, with a bounded
  result. Current workspace remains `null`; apply still validates the selected
  revision at the destination.
- Choice responses are `no-store`. Unlinked, disabled, deleting, or purging
  owners cannot enumerate projects. Tests verify owner isolation, minimal
  fields, and stale-revision rejection.
- Finance, Travel, and Health use project selectors; normal users no longer
  paste Shopping UUIDs or revisions. Render tests cover the selector UI.

### F4 — bounded maintainability

- Extracted Travel and Health recovery phase/storage helpers and dedicated
  project selector components. This supports F2/F3 and their focused tests; no
  unrelated large modules were split.
- Preserved the strict planning source-identity guard by retaining the original
  v13 lock and adding v14 for this source revision. A full 30-case deterministic
  offline evaluation kept the same planner/configuration/runtime and remained
  non-promoting; the anchor allows only this identical-source direct child.

### F5 — evidence and review context

- Moved raw JSON evidence and superseded handoff/status/QA snapshots into
  `stabilization/archive/2026-10-14/`. Kept canonical contracts, invariants,
  operations, blockers, roadmap, current state, and concise verification in the
  active documentation route.
- Inventory and isolated-contract generators now write under the dated archive
  and exclude archive contents from their own inventory. No historical evidence
  was deleted. See the archive README for classification.

### F6 — Health migration immutability

- Added `health-app/migrations/historical-sha256.txt` and a byte-hash regression
  test for the 17 pre-existing migrations.
- Ruff formatting excludes those exact historical paths, not a broad migration
  glob. New migrations remain format-checked. No old migration was rewritten in
  this pass.

## Local/native verification

Exact commands, final test counts, source commits, and temporary log paths are
recorded in [VERIFICATION.md](VERIFICATION.md). Evidence is local and synthetic:
the task matrix uses real migrations, PostgreSQL transactions, signatures, and
loopback HTTPS listeners, while Google/Firebase identity and certificate
lookups are faked. Offline tests do not replace PostgreSQL locking checks.

No CI result for these new commits is claimed here. The earlier published CI
snapshots are archived and apply only to their original source revisions.

## High-risk paths for the next reviewer

- Personal AI: `backend/src/personal_ai/mutations/service.py`,
  `backend/src/personal_ai/mutations/shopping.py`,
  `backend/src/personal_ai/api/mutations.py`,
  `backend/src/personal_ai/auth/task_identity.py`,
  `backend/src/personal_ai/contracts/delegated_tasks.py`,
  `stabilization/tests/test_suite_tasks.py`.
- Shopping: `apps/api/src/shopping/integrations/personal_ai/task_auth.py`,
  `task_router.py`, `tasks.py`, and
  `apps/api/tests/integrations/test_delegated_tasks_db.py`.
- Finance: `services/api/app/api/task_routes.py`,
  `services/api/app/integrations/task_wire.py`,
  `apps/web/src/ShoppingBudgetTask.tsx`, and
  `apps/web/src/ShoppingProjectSelect.tsx`.
- Travel: `backend/src/personal_travel/api/routes/shopping_tasks.py`,
  `backend/src/personal_travel/api/routes/auth.py`,
  `frontend/components/trip-workspace/shopping-task-panel.tsx`, and
  `frontend/lib/shopping-task-recovery.mjs`.
- Health: `services/api/src/health_api/api/shopping_tasks.py`,
  `services/api/src/health_api/integrations/task_wire.py`,
  `apps/mobile/src/features/profile/components/ShoppingTaskCard.tsx`,
  `apps/mobile/src/features/profile/shoppingTaskRecovery.ts`, and the migration
  byte-lock/configuration.

## External acceptance still open

Real Cloud Run IAM and service-token acquisition; Google certificate/key
rotation; Firebase linked-account and revocation behavior; multi-instance
ordering; live model/provider behavior; browser/mobile rendering in real
sessions; HealthKit device behavior; cloud object-store IAM, retention, deletion,
and backup restore; approved RPO/RTO; process kill/restart at effect boundaries;
mixed-version deployment/drain; and legal/privacy retention approval remain
unverified. Feature gates stay off by default. Do not infer production readiness
from local fakes, this handoff, or baseline CI.
