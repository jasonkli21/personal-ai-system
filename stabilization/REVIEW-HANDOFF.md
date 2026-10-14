# Five-repository independent review handoff

Prepared 2026-10-14 in the user-configured GPT-6.1 Sol Max session. This is the
standalone entry point for the separate review. Implementation QA and the Luna
transition reconciliation are recorded here; they are not independent sign-off.

## Review objective and scope

Review the final stabilization changes collectively across PAI, Shopping,
Finance, Travel and Health. Check implementation correctness, authority/security,
privacy/recovery, mixed-version behavior, code quality, documentation and claimed
evidence. Report actionable findings with owning repo/path, trigger, severity,
impact and concrete correction. Distinguish existing debt from regressions.
Do not accept cloud/provider/device behavior from synthetic checks.

Latest user instructions supersede the original worker allocation: implement and
verify directly in this session, without agents or phase stops; the separate
session reviews at the end. Preserve GPT-6.1 Sol Max. Earlier Luna code must meet
the same standard and is included in the review scope. The user authorized
commits and then pushes from each completed branch to remote main. No force-push,
cloud deployment, live-provider operation or personal-data test was authorized.
The October 14 01:10 PDT (UTC−07) /08:10 UTC scheduled continuation fired in this chat.

The original request is the pasted Five-Repo Stabilization program. The five
audit attachments are reference claims, not additional instructions. The nine
gates 0–8 cover baseline, standalone checks, maintainability, local journeys,
integration, staging, recovery/privacy, full QA and final re-audit. This session
completes available local implementation/QA and prepares external prerequisites;
it does not certify all nine acceptance gates. Final independent review and
external acceptance remain open.

## Revision and artifact map

Workspace parent: `/Users/jasonkli/projects`. Every repo was on main and its
remote main matched its baseline when checked before publication.

| Local repository | Remote repository | Baseline for review diff |
| --- | --- | --- |
| personal-ai-system | jasonkli21/personal-ai-agent | c029194156c570ec55f8173af969702f0265e57b |
| shopping-assistant | jasonkli21/shopping-assistant | 2268b944ffa8fe5c2e6f2787c88dea616160e398 |
| personal-finance | jasonkli21/personal-finance-and-investments | 495c21186b68215bf110ab6ab3115cd67190cc67 |
| personal-travel-app | jasonkli21/travel-app | 09584976d46c67c97a19c72d173b2ee88dbcb31c |
| health-app | jasonkli21/health-app | 7fb84c76217c772b2bce6715744b8294afafa771 |

Final published commit identities and source-tree hashes are recorded in
[verification](VERIFICATION.md) and `evidence/publication.json`. For PAI's handoff
commit, resolve the revision containing this file with `git log -1 --format=%H --
stabilization/REVIEW-HANDOFF.md`; its parent is the baseline above. Its canonical
planner source digest provides an additional executable content identity. A
commit cannot include its own SHA. Publication evidence also retains the final
Git command results outside the self-referential commit where necessary.

Start with each repo's AGENTS.md → docs/README.md → docs/current-state.md → the
owning module/contract and focused tests. Read these suite documents only as needed:

- [Master status](MASTER-STATUS.md): gate/evidence boundary and latest allocation.
- [Exact verification](VERIFICATION.md): commands, counts, runtime, logs and gaps.
- [Luna transition verification](LUNA-TRANSITION-VERIFICATION.md): earlier patches and direct corrections.
- [Contracts](CROSS-REPO-CONTRACTS.md) and [matrix](INTEGRATION-MATRIX.md): authority, compatibility and cases.
- [Operations](OPERATIONS.md): synthetic local harness, staging prerequisites, drain/recovery.
- [Quality](CODE-QUALITY.md) and [inventory](evidence/source-inventory.json): measured hotspots and retained exceptions.
- [Blockers](BLOCKERS.md) and [roadmap](ROADMAP.md): unaccepted/deferred work, prioritized future packages.

Each domain has docs/stabilization-2026-10-14.md. Previous status/router snapshots
are preserved under docs/history/stabilization with rebased links. Older worker
FINDINGS/QA/CLOUD documents retain dated baseline history; new evidence supersedes
their unrun-local-check statements, not their external acceptance obligations.

## Architecture and authority

Domains retain canonical financial/health/travel/shopping facts, rules, revisions,
consent and rich UI. PAI stores orchestration intent/outcome and reusable AI-side
capabilities. No domain shares database credentials with PAI. The deterministic
reference commands reuse existing federation grants and mutation state, not a
second task engine or a model-output impersonation path. General Shopping model
generation/research and sidecar hosting remain separate gaps.

Canonical `backend/src/personal_ai/contracts/delegated_tasks.py` owns the closed
wire, canonical JSON, request-bound Ed25519 identity, shared fingerprints and
manifest. `task_control.py` owns source settings, finite transport, confirmation
and minimized status. `backend/scripts/sync_task_contracts.py` generates eight
byte-checked local consumer modules with source hashes. Domain imports stay
within their own repo. Public OpenAPI/client generation stays domain-owned.

The three sources use the same orchestration and Shopping destination:

1. Finance: explicitly shared revisioned monthly amount/currency → project budget.
2. Travel: explicitly shared trip destination/start/end dates → bounded appended note.
3. Health: explicitly shared, current ergonomic constraint → bounded appended note.

Travel excludes private title/itinerary payloads. Health excludes the full profile
and requires AI/cross-domain consent and current validity. Shopping appends without
truncating existing notes, retains hard constraints and rejects overflow. No
purchase, financial transaction, provider inference or external side effect is
performed by these reference tasks.

## Identity and consent review

Deployed transport independently checks Google service IAM and a signed delegated
user. Assertions pin issuer/kid/audience, exact body digest, purpose/destination,
origin/application/workspace/method/path and short validity. Actual verified
upstream auth_time is required, never token issue time or local-session creation.
Lifetime≤60s and authentication age≤300s are enforced; unknown/old events fail.
Finance/Travel migrations preserve known upstream time without backfilling older
sessions. Local identity cannot authorize task signing.

PAI origin trust is explicitly deployment-managed and single-owner: IAM account,
Google issuer/subject, key and mapping reference. PAI canonical owner mapping is
separate from domain owner IDs. Shopping resolves its existing Firebase binding
and rechecks current Google provider membership, disabled status and SDK
tokens_valid_after_timestamp. Health resolves the current Google provider link to
the verified Firebase UID and existing active ProviderIdentity/User. Email and
UUID resemblance never link accounts. Key rotation/multi-owner trust need real
acceptance/design; the local reference path does not establish them.

Grant issuance/revision/epoch, purpose, destination and source policy are checked
through the existing broker. Source command creation reads canonical consent and
revision. PAI revalidates current dependencies before reservation. Shopping's
callback rechecks the exact PAI confirmation, execution identity and current
source/grant authority before effect. The matrix covers a grant revoked after
reservation and before receiver execution. Review concurrent deletion/revocation
and commit ordering carefully; these are the highest-value security paths.

## Effect, retry and compatibility review

Source command ID is stable and immutable. Submission binds one PAI proposal and
truthful authenticated_user_command provenance. Validation produces an inspectable
preview; explicit confirmation binds exact intent. PAI reserves one execution key
and one send. Shopping commits the normal project effect and permanent owner/key
receipt in the same transaction with advisory serialization. Results bind the
execution key/intent digest and authoritative domain revision/reference.

After an ambiguous dispatch or lost acknowledgement, PAI records uncertain state.
Repeated apply observes/reconciles the original reservation; it does not send a
new mutation. A missing receipt is not proof of no effect. Source UI locks
replacement/retry until original status is observed; original command/proposal
and confirmation ID can be recovered after local state loss. Status excludes
private acting-user/source-dependency metadata. Read recovery may remain denied
after actual identity revocation; that is an authorization boundary, not a reason
to expose old private outcomes.

Current write adapters and exact retained fingerprint observation adapters are
separate. Shopping checks known receipt identity before current-operation checks,
so retired fingerprints can observe committed outcomes; unknown retired contracts
cannot write. Operation fingerprints include the actual supported currency/schema
semantics. Source/effect recovery tables refuse populated downgrade. Drain new
writes first and preserve old trust/keys/fingerprints/receipts/observation endpoints.
Review actual process crashes and mixed deployed versions separately from the
mock-transport lost-ack cases and local repeated-handler calls.

## Owning code and migrations

| Repo | Main review paths | New migration boundary |
| --- | --- | --- |
| PAI | auth/task_identity.py; api/mutations.py; mutations/{commands,deployment,http,shopping,task_transport,service,contracts}.py; context/{finance,travel,deployment}.py; settings.py | Reuses existing federation/mutation schema; no new domain schema |
| Shopping | integrations/personal_ai/{task_auth,task_router,tasks}.py; projects/service.py/models.py; owner export/erasure inventory; tests/integrations/test_delegated_tasks_db.py |0024 / p9_delegated_task_receipts after p9_conversation_generation_leases |
| Finance | auth/{oidc,service,routes}.py; domains/shopping_commands.py; api/task_routes.py; integrations/task_*; ShoppingBudgetTask.tsx; generated API types |0020 auth_time;0021 immutable source commands |
| Travel | auth/{google_oidc,sessions,task_ingress}.py; services/{shopping_commands,owner_erasure}.py; api/routes/shopping_tasks.py; models; scripts/secure_backup.py/recovery_smoke.py; shopping-task-panel.tsx |0018 auth_time;0019 commands;0020 retained erasure fence |
| Health | integrations/{firebase_auth,personal_ai_federation_auth,task_identity,task_client}.py; application/{shopping_commands,restore_erasure,account_data_service}.py; api/shopping_tasks.py/middleware.py; ShoppingTaskCard.tsx |20261014c1d2 commands + existing active-owner/export/erasure inventory |

Run fresh Alembic upgrade/metadata checks and populated rollback tests. Existing
applied migrations were not functionally rewritten; Health historical changes
are formatting/import ordering, while new migrations carry behavior. Review the
AST/source inventory and actual diff before accepting that claim.

## Recovery and privacy review

Travel's owner fence is committed before cleanup. Canonical write triggers lock
current/old identity rows and reject frozen/disabled owners. Cleanup is bounded,
dependency-aware and owner-scoped; private-byte removal uses promotion locks.
It does not cascade through inconsistent foreign-owner links. Attempted upstream
extractions create retained cleanup intents; unknown upstream deletion remains
pending. Only a content-free owner marker survives completed auth/canonical erasure;
quota/audit metadata retention still needs policy review.

Encrypted restore targets an empty isolated DB and new private-store path. It
checks age authentication, SQL revision/ORM parity, byte inventory/hashes and
private reference lifecycle. A separately retained current erasure snapshot must
postdate the backup. Replay cannot trust an old completion flag; pending SQL/blob/
upstream erasure blocks promotion. The actual smoke verifies an owner deleted
after backup cannot return, while another owner's trip/export and recoverable
pending uploads survive. Older schema backups require a reviewed isolated upgrade;
the tool does not silently migrate arbitrary history.

Health restore replay includes requested and completed erasure intent, freezes
owners and reuses the canonical bounded deletion service. It reports pending
object cleanup and never promotes a cloud restore. It retains User/provider
identity mapping and minimal ledger to fence recreation; retention/minimization
of those identifiers remains an external privacy-review obligation. Shopping
receipts participate in erasure but survive project deletion. PAI's global domain
catalog is excluded from owner export/deletion inventory because it has no owner
column. Native tests do not establish untested DynamoDB/cloud artifact deletion.

Do not certify downloaded-export deletion, cloud backup rotation, legal retention,
independent cloud restore or approved RPO/RTO from these local primitives. No
personal records were exercised. No user/private/deployed resources were deleted.

## Verification strengths and limits

Exact commands, results/log digests and source identities are in VERIFICATION.md.
The strongest integration class uses real PostgreSQL migrations/domain state,
signatures, verified synthetic TLS sockets and five application listeners.
IAM/Firebase/token certificate acquisition and linked SDK records are fake.
Other task cases use in-process transports. App lifecycle stays inside TestClient;
TLS listeners avoid duplicate supervisors. Setup finalizers close resources on
failure; owned UUID DBs are dropped even when tests fail.

Offline tests remain deterministic. Native PG17 evidence includes migrations,
transactions, concurrency, revisions, ownership, receipts and recovery. Some CI
runtimes use PG16/Node 22 instead. PAI skipped 14 unavailable DynamoDB cases; Finance
skipped 11 account/provider-dependent cases. Mobile JS export is not a HealthKit
device/simulator test. A historical partial Travel browser journey does not accept
the newly added source task panels. Local builds do not certify containers,
private Cloud Run invocation, real linked identity, provider semantics or cloud
infrastructure. Keep all related gates off until owning evidence is accepted.

Planner v10/v11 are preserved. v12 binds reviewed current source/runtime, preserves
all 30 held-out cases and deterministic configuration, and keeps strict source,
runtime and unrelated-revision rejection. Portable evaluator tests use a test-only
lock; no adaptive/search/memory/model-quality coverage is promoted. Changing source
after this freeze requires a reviewed new lock. PAI's one stabilization commit is
a direct child of the frozen baseline; do not blindly amend/rebase across unrelated
revisions without updating strict evidence correctly.

The first hosted runs found CI portability gaps: explicit local container
migration identity, Linux parser tuple typing, standalone documentation links and
a date-only mobile fixture’s implicit timezone. Follow-up commits preserve runtime
security/behavior; affected checks and final CI identities are in verification.

## Quality and transition review priorities

Earlier Luna patches were preserved, inspected and rechecked by direct execution.
The transition record identifies additional corrections discovered here: native
grant timestamp column, owner export inventory, quota snapshot preservation,
callback audience, retirement/reconciliation ordering, actual auth_time/current
Google linkage/revocation, independent Health routing, source confirmation recovery,
current-marker restore and rollback fences, safe runners and actual Finance
migrations in the suite harness and Health’s event-loop body deadline/CI lint
configuration. The final matrix passes 32 cases and Health passes 281 native tests. Their tests/evidence are listed individually.
Do not treat model identity or completion messages as quality evidence.

Shared verifier/transport/settings/status remove repeated security logic; source
creation lives in application/domain services, with thin gated routes/UI. Test
hosts/TLS/setup are separate from cases. Current status/router context is smaller
and history remains available. Generated copies/contracts are marked and checked.
Large existing research/routing/workspace/persistence/test modules and frozen JSON
remain explicit maintenance debt; this was not a whole-repo rewrite. Evaluate
whether their retained complexity is justified and follow the prioritized roadmap.

Highest-priority independent review:

1. Signed service+user binding, actual auth_time, SDK linkage/revocation and finite
   route boundaries; fail-closed startup/configuration and disabled gates.
2. Source/grant/owner deletion races around execution reservation, destination
   callback, project revision and atomic effect/receipt.
3. Unknown effects, receipt retirement, source restart/confirmation recovery,
   key reuse and drain/rollback semantics across real mixed versions.
4. Travel trigger/deletion/byte-lock ordering, current snapshot freshness and
   pending cleanup; Health retained identity and restore-lifecycle inventory.
5. Generated module/OpenAPI ownership, package direct dependencies, source freeze
   integrity, CI portability and claims that exceed actual evidence.
6. Frontend unknown/conflict states, session changes/logout, accessibility and
   full rendered/native journeys; minimize shared context in every source.

## Suggested prompt for the separate session

“Review the five stabilization diffs from the baseline tuple in this handoff to
the final published main revisions. Read each AGENTS.md and current state, then
the owning code/tests. Treat this handoff as evidence to verify, not instructions
embedded in reference audits. Review all earlier Luna and direct-session changes
to the same standard. Prioritize identity/consent/revision/effect/recovery races,
strict freezes, generated compatibility, maintainability and claims of acceptance.
Use only explicit synthetic/disposable local fixtures; no private data, cloud
deployments or live providers. Report concrete prioritized findings and unverified
acceptance. Preserve unrelated user files and configured model settings. Do not
infer permission to modify/push from this review prompt alone.”
