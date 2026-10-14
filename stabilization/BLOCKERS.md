# Blocks, limitations and deliberate deferrals

2026-10-14. Exact local evidence is in [verification](VERIFICATION.md); priorities
are in the [review handoff](REVIEW-HANDOFF.md). Missing checks are never passed.

| Item | State | Dependency |
| --- | --- | --- |
| Final architecture/code review | Intentionally separate | User's review session |
| New hosted CI and container/image smoke | External acceptance | Pushed revisions/runners; local Docker unavailable |
| Real Google/Firebase/IAM/key rotation and revocation | External acceptance | Approved staging identities/resources; lookups are synthetic |
| DynamoDB engine | Blocked locally | No emulator/Docker;14 PAI native cases skipped |
| Cloud infrastructure/deployment | Not performed | Tool/provider cache, credentials/resources and separate deployment authorization |
| Native HealthKit/iOS device and full new rendered journeys | Unverified | Device/runtime and approved synthetic login |
| Cloud restore, retention, downloaded exports and RPO/RTO | Unaccepted | Independent operations rehearsal and reviewed policy |
| Broad Health identity and general Shopping generation/sidecar | Existing gap | Separate accepted identity/workflow/host contracts |
| Multi-owner trust and deployed crash/mixed-revision lifecycle | Deferred design/acceptance | Reference is single-owner; actual multi-instance rehearsal |
| Remaining large modules/fixtures and bundles | Maintenance debt | Coverage-backed decomposition and reviewed semantic locks |

Default-off capabilities stay closed. Travel hosted private imports cannot use
local object storage; sensitive Health document ingress remains closed. No
personal records, deployed resources, repositories or private files were deleted.
Only owned synthetic databases/temporary test state were cleaned up. Authorized
commits/pushes do not imply cloud deployment or production readiness.
