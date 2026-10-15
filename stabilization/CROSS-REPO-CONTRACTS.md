# Cross-repository contracts — 2026-10-14

The reference implementation reuses federation and mutation seams. Domains own
canonical records, revisions, consent, validation, commands and UI. PAI owns AI
capabilities, grant choices, immutable orchestration intent, confirmation,
execution reservation and outcome observation. Independent review and deployed
acceptance remain open.

| Boundary | Authority/version | Enforcement |
| --- | --- | --- |
| Delegated user | `contracts/delegated_tasks.py`, suite-delegation-v1 | Ed25519, pinned issuer/key/audience, canonical request digest, lifetime≤60s, actual verified auth_time age≤300s, closed claims |
| Origin trust | PAI settings/DelegatedOriginTrust | Explicit source IAM, Google issuer/subject, mapping reference and allowed destinations; no email/UUID auto-link |
| Source command | suite-source-command-v1 / command-read-v1 | Immutable owner command, opaque grant choice, source entity/revision, pinned operation/payload, target/revision, purpose, expiry and provenance |
| Target authority | suite-task-target-v1 | Own IAM plus request-bound user, null Shopping workspace, explicit project and current owner lifecycle |
| Task/result | suite-task-v1 / suite-task-result-v1 | Closed schema, operation/version/fingerprint, intent/execution binding, expected domain revision; bounded bytes/time and no transport retries |
| Source control/status | `contracts/task_control.py`, suite-source-task-status-v1 | Finite control paths, exact method/path/origin/application binding, small status including original confirmation ID |
| Federation grant | Existing federation-grant-v1 | Owner, issuance, revision/epoch, purpose, destination, source policy/consent checked at actual use |
| Mutation lifecycle | Existing PAI contracts/repository | Truthful deterministic-command provenance, immutable binding, explicit confirmation, one execution reservation, uncertainty and observation-only reconciliation |
| Execution authorization point | Destination task transaction + live PAI callback | Shopping's successful live `effect=true` authority callback is the authorization linearization point for the reserved execution key. Revocation before the response blocks the effect; revocation after it blocks later executions but does not cancel this in-flight effect. Shopping's own owner-lifecycle row lock still fences the local transaction. |
| Shopping operation | Shopping descriptors/fingerprints | project.set_budget v1 and project.append_context_note v1; normal project constraints/revision and atomic effect/receipt |
| Shopping target choices | `suite-task-target-choices-v1` | Read-only, request-bound delegated identity; returns only owned active project ID, title and revision. PAI relays the source user's identity to Shopping; source databases do not copy project state. |
| Existing context | Owning domain contracts + PAI providers | Travel context-read-v2, Shopping/Finance context-read-v1, broad Health context-read-v1, separate minimized Health federation export; independent gates |

Canonical schemas and `task_manifest()` produce explicit shared fingerprints.
Shopping publishes actual operation descriptors; configuration pins their
fingerprints. Generate copies with
`backend/.venv/bin/python backend/scripts/sync_task_contracts.py`; `--check`
compares all 8 generated modules and source hashes byte-for-byte. Domains import
their own copies, never a sibling Python package. Each app's OpenAPI/client
generator owns its public API.

PAI current write adapters and explicitly retained reconciliation adapters are
separate. Shopping observes a known exact receipt before current-operation
validation. Unknown retired contracts cannot write. Populated source-command,
receipt and erasure-marker migrations refuse destructive downgrade.

The three source paths share transport/state machinery: Finance monthly budget,
Travel consented destination/dates, Health consented ergonomic constraint. Health
excludes the full profile; Travel excludes private trip titles. Notes append
bounded explicit context while preserving existing notes/constraints; overflow
rejects without truncation. General AI generation, broad Health identity and the
Shopping sidecar remain separate gaps.

The destination callback is the distributed authorization point for an already
reserved execution. There is no cross-database transaction spanning PAI/source
authority and Shopping's commit. A source/grant/account revocation observed before
Shopping receives `allowed=true` blocks the write. Revocation after that response
does not cancel this execution; it blocks later ones. Shopping's local owner
privacy lifecycle is checked and locked in the same transaction as its project
write and receipt, so a local deletion fence that wins that lock blocks the write.
The read-only target-choice endpoint returns only `{project_id, label, revision}`
for the linked owner's active projects; it is not an execution permit, and normal
target ownership/revision checks still run at apply time.

Mixed-version rollout retains keys/trust, fingerprints, receipts and observation
endpoints while draining confirmed/uncertain work. Disable new PAI writes first;
do not remove the destination before original-key reconciliation. Never replace
an uncertain execution key or infer no effect from a missing acknowledgement.
See [operations](OPERATIONS.md) and the [fresh re-review handoff](FRESH-REVIEW-HANDOFF.md).
