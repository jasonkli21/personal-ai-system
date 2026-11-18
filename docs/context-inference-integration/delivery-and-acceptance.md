# Delivery and acceptance

**DRAFT / NOT DEPLOYED.** [Current state](../current-state.md) governs production NO_GO. A passing gate admits only the named configuration, data class and execution mode. Each evidence record needs revision, configuration, fixture or consent reference, environment, observed counts, failure cases, reviewer and expiry. Keep credentials and personal content out of evidence.

## Build order and exits

| Slice | Dependencies and bounded deliverable | Exit evidence required |
| --- | --- | --- |
| Independent source reads | [Provider contract](application-context-contract.md), current identity and assembler. Implement a synthetic registry plus travel and fitness adapters, describe/search/fetch and explicit snapshot assembly. No external listener or real data. | Hermetic two-owner matrix below, exact output/ordering and token counts, zero model calls for retrieval. |
| ChatGPT reads | Source slice. New protected-resource edge, connector account linking, two read tools and manual export UX. | Installed OAuth negative tests and authorized direct/indirect prompts on a named ChatGPT surface. Admit manual mode separately. |
| Local plan execution | Source slice. Extend the existing local bridge with connected-app and dependency checks. Independently gate this slice from MCP. | Prove user custody, supported serializer, model discovery, authorized terminal stream and denial on mismatch/disconnect for a named local distribution. |
| Configurable routing and costs | Stable source and dispatch contracts. Add user policy, inspector, payer-bound price registry, atomic holds and reconciliation. Subscription stays absent from candidates until its own gate passes. | Native concurrency/replay and audited cost bounds. Only separately authorized billing verification can admit a paid endpoint. |
| Shared context service | Source and identity gates plus each enabled integration's gates. Tenant-scoped registries, receipts, deletion fences, isolated runtime binding. | Deployed private invocation, egress controls, two-user isolation and restore drills. Managed plan proxy remains blocked. |
| Independent acceptance | Per-mode evidence from preceding slices. Review source rights, identity, actual provider behavior, recovery, privacy and usefulness. | Dated independent decision with allowed scope, rollback trigger and owner. Remaining modes stay disabled. |

## Acceptance matrix

Run a Cartesian fixture of owners A/B with both travel and fitness registered for each. Give each owner an isolated workspace per app, one scoped grant, an independent host and account. Reuse the same opaque record ref in all four partitions. Give A a second travel workspace without a grant. Use controlled time, varying revisions and distinct sentinel values per partition. Count source reads, disclosures, physical sends, allowance debits, charges and durable receipts.

| Scenario | Required observation | Minimum evidence |
| --- | --- | --- |
| Travel and fitness positive reads | Return only exact current leg or workout projection for its owner/app/workspace, with revision, sensitivity and citation. Same input and clock produce identical ordered bytes. | Hermetic fake |
| Swap owner, workspace, app, ref, cursor, grant scope, recipient or actor independently | Uniform denial for unauthorized lookup, zero foreign records/titles, sends or ledger effects. Repeat in both directions and on exported data. | Hermetic plus installed local |
| Revision or grant changes after search, package, before send, midstream | Stale fetch fails, unsent package denied, further disclosures stop, past send recorded. Expired or revoked snapshot fails PAS reuse. | Fake barriers plus installed send-boundary integration |
| Current app fact disagrees with memory, summary or old evidence | Current authorized revision controls the answer. With unavailable source, report missing evidence. No stale summary substitution. | Hermetic plus longitudinal answer evaluation |
| Malicious record contains tool or billing instructions | Only projected data returned. Zero extra tools, expanded sources or paid sends. Inspect generated answers separately. | Fake plus live quality review |
| Connector auth expired, issuer/audience/client wrong, missing scope, same-email wrong subject | Zero disclosed records and zero outbound reads before admission. Valid installed connection returns cited synthetic result. | Installed OAuth plus live connector |
| Direct and indirect ChatGPT prompt, unavailable installation | Record selection and citation accuracy separately. Direct request retrieves authorized fixture. Unsupported surface can preview/export limited fields for manual use. | Live named surface plus local export |
| Eligible local SIWC, identity-only, expired, disconnected, wrong app/account/host or foreign trigger | Positive account-visible model completes supported stream. All invalid cases have zero plan dispatch after denial. No remote token persistence. | Installed custody plus live authorized account |
| Remote control uncertain, managed host, background consent absent/revoked | Zero plan sends even when operator routing preference lists subscription first. | Installed and deployed isolation |
| New account, misclassified model, free quota exhausted | Zero paid or plan calls. Use only another verified free route or stop. | Hermetic and installed physical send counter |
| Custom order, one eligible candidate at each rank | First eligible subscription/free/approved-paid endpoint wins. Denied endpoint/model/payer, missing price or exhausted ceiling produce zero paid sends. | Hermetic plus native ledger |
| Concurrent paid requests, price change, month boundary, duplicate settlement | Settled plus outstanding liability obeys caps. Each approved send has one pre-send hold and one eventual settlement. Retain unknown exposure. | Native transactions plus authorized provider billing comparison |
| Conclusive no-send, ambiguous send, stream break, crash and retry | Only proven safe failure advances. Unknown attempts retain hold and fence across restart, replay and new provider selection. | Hermetic fault injection plus native crash/restart |
| Owner deleted, host remapped or revoked grant restored from backup | Quarantine until current tombstones/epochs and receipt fences are reconciled. No data, quota or logs visible to other owner. | Deployed recovery drill |

## Baselines and decision ledger

On fixed cold and warm synthetic corpora, compare no-source turns to one-source and maximum-size turns. Record p50/p95 added latency, calls, bytes, input-token delta and skipped records with a pinned counter. Targets are zero extra model calls for retrieval, zero over-budget turns, bounded fetch counts and identical selection on replay. Measure authorization-to-send delay under load and revocation races. Establish a reviewed numerical p95 latency and race-window ceiling from those measurements before promotion. Evaluate answer correctness and citation revision against labeled facts, including missing evidence and changed itineraries. Establish acceptance thresholds on held-out prompts before live quality trials. Measure maximum reserved versus invoiced cost and reconciliation lag for each price revision. Require zero uncovered liability and duplicate charges. Set a maximum unresolved age for escalation, never automatic release.

| Status and decision/risk | Evidence owner and next action | Until resolved |
| --- | --- | --- |
| DECIDED — domain ownership, one assembler, distinct authorizations, free-only factory | Architecture owner checks [interfaces](architecture.md) and [policy](inference-routing-policy.md) in implementation review | Reject alternate paths around these checks |
| PROPOSED — typed provider, paging and deterministic budget | Source owner builds the first slice and records baseline | Synthetic data only |
| BLOCKED_UNVERIFIED — private source identity, host authority and revocation race | Security owner demonstrates authenticated source delegation and final dependency check at physical send, measures race, validates logs, deletion and backup recovery | No real personal records or shared deployment |
| BLOCKED_UNVERIFIED — MCP availability | Connector owner verifies named workspace, registered client and live tool schemas | Manual export subject to its own consent and data gate |
| BLOCKED_UNVERIFIED — specific connected app, local or exclusively controlled remote runtime | Integration owner documents feature/distribution and free access, proves local credential custody, control, account-specific eligibility, plan-only billing and scoped consent | No real plan credential use until authorized controlled trial, no admitted route before successful trial |
| BLOCKED_PENDING_APPROVAL — managed SIWC or generic multi-app inference | Distribution owner obtains written provider authorization covering the exact app, host and custody model and independent review | No managed plan execution or subscription pooling |
| BLOCKED_UNVERIFIED — live free pricing, paid ceilings, ambiguous settlement | Accounting owner verifies current attestation, enforceable maximum, provider receipts and native ledger under replay | Omit unverified free endpoints. Disable paid traffic except separately approved gated verification. |
| OPEN — quality and latency thresholds | Evaluation owner locks measured baselines, held-out rubric and per-mode targets | No quality or performance promotion |

The supplied planning reference currently triggers the repository naming check at two historical numbering references. Documentation owner should resolve the planning text separately before relying on a green repository-wide naming gate.

## Implementation-readiness checklist

- [ ] Pin the draft versions, fixture clock, source schemas, identity tuples and denial counters before writing the adapters.
- [ ] Assign owners for grant/epoch authority, revocation barrier, receipt fencing and evidence retention. No live data needed for the first slice.
- [ ] Before real credentials, document terms review, specific app eligibility, user control, local storage and disconnect/recovery results. Obtain explicit test-user authorization and a bounded trial plan.
- [ ] Before personal data or shared hosting, independently verify deployed identity, private invocation, source rights, recipient disclosure, isolation, egress, deletion and restore.
- [ ] Before paid verification, obtain explicit payer approval for exact pricing, amount, account and test period. Demonstrate native holds and unknown-send handling first.
- [ ] Record evidence separately for static review, hermetic fake, installed local integration, native persistence, live provider, deployed recovery and longitudinal usefulness. Platform admission and answer quality need separate decisions.
