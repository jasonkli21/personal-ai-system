# GCP deployment assets

Run `make cloud-plan-check` at the repository root to validate the synthetic
[example manifest](cloud-plan.example.json). For a local proposal, use
`bash infrastructure/gcp/deploy.sh plan --manifest /path/to/proposal.json --baseline /path/to/reviewed.json`.
The command returns a redacted policy and drift result using local files.
`apply` is blocked until a separately authorized and reviewed implementation
can bind the plan to verified live state.

The planned runtime stores query-rich records and vectors in Neon/Postgres
and conversations and runtime state in DynamoDB. Cloud Run uses Google
service identity with AWS STS for DynamoDB access. See the
[GCP deployment guide](../../docs/gcp-deployment.md) and
[deployment operations](../../docs/gcp-deployment.md).

Run `bash -n infrastructure/gcp/deploy.sh` and `make operations-check` for syntax,
fake CLI tripwires and static contract checks. Deployed GCP/AWS/Neon
connectivity, strict-$0 eligibility and provider account limits require
separate evidence.
