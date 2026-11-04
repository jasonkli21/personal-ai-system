# Cross-phase gate registry — 2026-11-03

This registry carries open safety and evidence obligations across PI-0–8. It
does not grant deployment or data authority. PI-8 audit-tool structure can be
validated independently of predecessor acceptance; production remains `no_go`.
Owners below are roles responsible for evidence, not named operators.

| Gate | Owner | Decision | Preconditions and required evidence |
| --- | --- | --- | --- |
| PI-0–4 formal independent acceptance | Independent reviewer | `BEFORE_ENABLEMENT` | Fresh review of each phase's exact commit and evidence; deployed identity, external rights, native storage and provider claims remain separate. |
| PI-5 R01–R03: trusted source authority, retrieval rights and durable original-key/forget receipts | PI-5 owner + security reviewer | `BEFORE_ENABLEMENT` | Trusted issuer/revision/rights epochs; recipient, purpose and model-processing permit at physical send; source withdrawal and downstream canaries; bounded monotonic original-key/tombstone authority across workers and restore. |
| PI-5 P5-24: canonical runtime verification | PI-5 owner + independent reviewer | `BEFORE_ENABLEMENT` | Reproduce the canonical command from a clean exact revision under the documented fence; preserve all historical locks and classify unsupported environments as blocked. |
| PI-5 P5-28: input ownership and source identity | PI-5 owner + independent reviewer | `BEFORE_ENABLEMENT` | Prove provenance and ownership for all evaluator inputs; keep v1/v2 plans, corpora, thresholds and prior evidence immutable. |
| PI-5 R01: revocation-to-physical-send race (PI8-R05) | Security reviewer + source issuer operator | `BEFORE_ENABLEMENT` | Atomic per-attempt send/revoke protocol, two-worker race canary, retained-output/export checks and a real issuer; local pre-send rechecks are not proof. |
| PI-5/7 R03: stale journal rollback (PI8-R06) | Storage/recovery owner | `BEFORE_ENABLEMENT` | Independently monotonic original-key and revocation authority; native mixed-age Postgres/pgvector and DynamoDB restore drill, reconciliation and rollback receipt. |
| PI-5 R07: marker-free legacy export provenance | Data lifecycle owner | `BEFORE_ENABLEMENT` | Inventory legacy/migrated serializers and rows; synthetic canary; quarantine unknown origin through export, replay, history, SSE and cache. No leak is established by current evidence. |
| PI-7 R08: dependency origin and clean installation | Build/release owner | `BEFORE_ENABLEMENT` | Independently digest-pinned wheelhouse, clean no-index install, optional-module absence, source-free consumer and native egress fence. Prepared RECORD hashes and archive listings do not establish origin. |
| PI-6 P6-02 / P6-29: predecessor PI-5 acceptance | PI-6 owner + independent reviewer | `BEFORE_ENABLEMENT` | Original production entry conditions remain unmet. The documented offline-development sequencing exception is local-only and does not waive this gate. |
| PI-6 P6-15 / P6-32: durable authority, restore, deletion and live provider proof | PI-6 owner + storage/security operators | `BEFORE_ENABLEMENT` | Native distributed attempt/source authority, mixed-age restore/deletion and approved live provider evidence. Synthetic rows remain synthetic. |
| PI-7 native egress fence and reproducible wheelhouse | Operations/build owner | `BEFORE_ENABLEMENT` | Native macOS or approved OS fence succeeds; clean pinned wheelhouse and installed consumer reproduced. Current sandbox launcher rejection stays blocked. |
| PI-7 Docker and native PostgreSQL/DynamoDB recovery | Storage operator | `BEFORE_ENABLEMENT` | Docker/native stores available in a disposable operator-owned topology; concurrency, transaction, recovery and teardown receipts. No daemon was accessed for this review. |
| PI-7 cloud IAM, network, identity, billing and provider caps | Cloud/provider operator | `BEFORE_ENABLEMENT` | Verified project/audience/IAM/secrets/storage/image/network bindings, effective account-enforced caps and explicit spend/time/request ceiling; no live apply or billable call is authorized here. |
| PI-7 physical erasure, backups and restore anti-rollback | Data lifecycle operator | `BEFORE_ENABLEMENT` | Approved disposable data and native restore/erasure drill covering messages, embeddings, provider copies, logs, exports, backups and signed URLs. |
| PI-7 fresh independent follow-up review | Independent reviewer | `BEFORE_ENABLEMENT` | Review exact remediation commit and reproduce permitted local evidence; do not infer acceptance from implementer tests. |
| HXE-0 installed preview | Build/release owner + independent reviewer | `BEFORE_ENABLEMENT` | Source-free SDK and app, native-fenced signed installed server, trusted dependency origin and exact-commit review. See the [HXE-0 inventory](../harness-excellence/README.md). |
| HXE-1 MCP and ingestion | Source issuer, security and build/release owners | `BEFORE_ENABLEMENT` | Authenticated installed transport and independent peer/client canaries, verified external rights, exact account/operation cost admission, atomic send/revoke and restore reconciliation. See the [HXE inventory](../harness-excellence/README.md). |
| Private local inference and real-task utility | Local runtime operator + independent reviewer | `BEFORE_ENABLEMENT` | Reproduce the pinned local model under native egress fencing with migrated canonical accounting and bounded source-aware tasks. Preserve frozen planning and benchmark identities. Hosted expansion requires separate verified current account, privacy, quota, and exact counter evidence. |
| Governed workflow enablement | Execution, storage and security owners + independent reviewer | `BEFORE_ENABLEMENT` | Exact-commit review, independently monotonic scoped keys across mixed-age restore, native sandbox and installed consumer proof, fresh issuer-bound permits for any external send, and durable human approval and reconciliation for effects. Background dispatch needs independent worker and queue evidence. See [workflow authority](../decisions/0025-workflow-lifecycle-authority.md). |
| MEM-2 promotion | Memory/security owner + independent reviewer | `BEFORE_ENABLEMENT` | Existing default-off behavior remains; obtain its own acceptance and deployed identity, lifecycle and host-tool evidence. |
| MEM-3+ | Product owner | `POST_PI_FEATURE` | Frozen. Requires a separate explicit unfreeze and separately reviewed plan after PI obligations; not part of PI-8 closure. |
| Post-PI dynamic reasoning, broader retrieval, optimization and evaluation features | Product owner | `POST_PI_FEATURE` | Future roadmap only; no PI-8 scope expansion or change to current defaults. |

`FIX_NOW` is reserved for bounded audit-tooling defects that can be corrected
without enabling external behavior. PI-8 R01–R04 are handled in the dated
remediation report. Inherited R05/R06/R08 and the R07 hypothesis remain
pre-enablement gates above; no runtime or migration behavior is changed here.

## PI-8 trust chain

The v1 ledger remains byte-identical to blob
`cd4c4dda26b878e8b1ea35843d9032c68d143b69` at review commit
`a80236648e2635a267f122ba0fd958cafa09c096`. The v2 checker requires an
independently supplied exact commit SHA and a clean checkout, then reports that
the v1 structure is valid and its execution evidence is author-reported. The
reviewer pins the commit/tree outside the authored ledger. A commit cannot
contain its own commit SHA or tree ID without a hash cycle; use the full commit
SHA in the delivery and get the tree ID from the checker's output.
