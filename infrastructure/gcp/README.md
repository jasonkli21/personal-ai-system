# GCP deployment assets

Run `make pi7-cloud-plan` at the repository root to validate the synthetic
[example manifest](pi7-cloud-plan.example.json). For a local proposal, use
`bash infrastructure/gcp/deploy.sh plan --manifest /path/to/proposal.json --baseline /path/to/reviewed.json`.
The command returns a redacted policy and drift result using local files.
`apply` is blocked until a separately authorized and reviewed implementation
can bind the plan to verified live state.

The planned runtime stores query-rich records and vectors in Neon/Postgres
and conversations and runtime state in DynamoDB. Cloud Run uses Google
service identity with AWS STS for DynamoDB access. See the
[GCP deployment guide](../../docs/gcp-deployment.md) and
[PI-7 operations](../../docs/platform-independence/pi-7-operations-runbook.md).

Run `bash -n infrastructure/gcp/deploy.sh` and `make pi7-check` for syntax,
fake CLI tripwires and static contract checks. Deployed GCP/AWS/Neon
connectivity, strict-$0 eligibility and provider account limits require
separate evidence.
