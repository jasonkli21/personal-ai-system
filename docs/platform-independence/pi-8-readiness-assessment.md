# PI-8 readiness assessment

2026-11-03. Implementation-session assessment on baseline
`9b4b0f4db358ac97c156a615831dbb81a0a636a9` plus the audit-only commit.
See the [case ledger](pi-8-verification.json) for individual evidence thresholds.

| Usage profile | Verdict | Operator boundary |
| --- | --- | --- |
| Static audit and in-process tests with synthetic inputs | Approved for local development | Retain fake transports, the Python audit fence and cleared environment. |
| Installed offline core and Reading Logbook | Blocked for fresh acceptance | Repeat native-fenced wheel installs, child egress probes, installed HTTP and signed membership/replay. Obtain trusted build dependencies independently. |
| PI-5 local retrieval and tools | Local candidate; production blocked | Synthetic retrieval/use-rights tests pass. Require trusted monotonic source authority, physical-send authorization, original-key durability and export policy. [PI-5 gate](pi-5-completion-gate.md) |
| PI-6 scripted evaluation | Locally complete, unpromoted | Historical v2 reports are synthetic and author-exposed. P6-02/29 and distributed/live P6-15/32 remain open. [PI-6 gate](pi-6-completion-gate.md) |
| Disposable PostgreSQL/pgvector and DynamoDB | Blocked | Docker absent. Obtain approved local image IDs, disposable context and native fence. [PI-7 runbook](pi-7-operations-runbook.md) |
| Static cloud plan | Approved for static inspection | Apply refused. Eight bindings remain unverified. |
| Hosted, live model/search, paid, personal data, physical deletion and recovery | No-go | Require reviewed identity, network, account caps, vendor terms, native restore, erasure and independent acceptance. |
| PI-0–4 and PI-7 release | Pending predecessor acceptance | PI-0–4 formal acceptance remains open. PI-7 stays changes_required. [PI-7 remediation](pi-7-review-remediation-2026-11-03.md) |
| PI-8 release acceptance | Pending independent review | This assessment records same-session evidence. |

## Trust boundaries and attack cases

| Boundary | Threat and present control | Evidence needed beyond this run |
| --- | --- | --- |
| Consumer, issuer and source app | Forged headers or same-owner confused deputy. Token, client binding and workspace membership are separate checks. Profile selection binds owner, actor, application, workspace, revision and expiry. | Fresh signed installed HTTP and deployed identity. |
| Registry, retrieval, model and provider | Client-supplied tool metadata or source content escalates to execution. Tool registry is operator-selected and closed; separate purpose gates protect model context and export. Streaming and exact local count were exercised on distinct fake provider profiles. | Remote issuer rights and withdrawal, legal basis for model processing, network and SDK boundary proof. |
| Retained output | Stale dependency after count or first SSE delta, cached re-use, summary laundering or export. Local rechecks guard multiple surfaces; returned bytes may persist in recipients and logs. | Inventory old unattributed rows, proxy/telemetry/client/cache/export canaries and retention proof. |
| Quota, store and effect | Lost acknowledgement or revoked source between checks. Reservations, bounded transport and original-key observation limit replay within tested authority. | Cross-worker native P19, send-time issuer fencing, restart and same-key reconciliation under outage. |
| Backups and physical erasure | Mixed restore generations, resurrection of revoked/forgotten data, provider copies and URLs outliving access. | Retain a monotonic authority separately, quarantine both stores and verify all sinks under an approved drill. [PI-7 lifecycle](pi-7-data-lifecycle-runbook.md) |
| Operator, dependency and cloud | Modified prepared files, misplaced role or hidden billing. RECORD comparison, static plan and local configuration each cover narrower boundaries. | Trusted wheelhouse, live identity/account bindings, enforced caps, actual billing and effective network denial. |

## Findings and residual risk

- **P0** — No confirmed P0 in the inspected and executed scope. Live and
  cross-store failure modes remain unmeasured.
- **P1, inherited authority gap (P8-18)** — At
  `backend/src/personal_ai/services/chat/service.py:928`, the guard reads
  current authority and then hands off to a provider. Expected invariant is a
  revocation-aware linearization point at physical send. Reproduce the local
  negative with `test_revocation_after_preparation_before_model_send` in
  `test_pi5_context.py`. It passes, but inspecting the guard shows a read
  check without a held issuer lease. An update after the last check remains
  outside this proof. The context/provider owners need an issuer-bound,
  exact-attempt permit and a native two-worker test that gates dispatch while
  revocation commits. PI-5 production remains blocked.
- **P1, inherited recovery gap (P8-21/24)** — At
  `backend/src/personal_ai/retrieval/journal.py:81`, the original-key fence is
  a SQLite row in the opened file. The invariant is that an old snapshot can
  never restore an absent key into eligibility. Review
  `test_pi5_context_pi7_stale_derived_restore_keeps_revocation_and_original_keys`
  in `test_pi7_lifecycle.py`. The synthetic test restores messages while
  retaining the current journal. A journal restored from before reservation
  lacks that row by construction. The storage owner must retain attempt and
  revocation authority outside snapshots, reconcile before serving and verify
  mixed-age restores against both native stores. No actual restore was run.
- **P2, provenance (P8-27)** — At
  `backend/scripts/pi7_local_smoke.py:228`, the smoke copies prepared
  distributions after RECORD verification. Installed content integrity and
  independent dependency origin are distinct. Reproduce same-version byte
  refusal with `test_changed_same_version_dependency_bytes_refuse` in
  `test_pi7_operations.py`. The packaging owner needs an independently
  digest-pinned wheelhouse and a clean no-index native-fenced install.
- **P2, export coverage hypothesis (P8-19/26)** — At
  `backend/src/personal_ai/retrieval/export.py:6`, refusal detects marker
  metadata throughout the bounded snapshot. Expected invariant is continued
  denial when a migration or new serializer loses provenance. Compare
  `test_retained_output_detail_replay_history_and_export_deny` with a
  synthetic legacy record lacking both markers. Marker-free content cannot be
  classified by this helper alone. No leak was reproduced. The export owner
  should quarantine unknown historical attribution and test the full export
  inventory against new serializers before release.
- **P3, audit tooling corrected** — The first archive inspector assumed two
  directory entries, and its first retry excluded an inherited `.gitignore`.
  Explicit archive globs and the known sdist layout reproduced the static
  check. The initial Ruff warning was fixed before the final lint run.

For outages, quarantine the candidate, disable the selected provider/retrieval
profile through existing flags, stop retries with unknown effects, and reconcile
using original keys and current authorization. Roll back code to a reviewed
configuration after confirming compatible data and migrations. Preserve
monotonic revocations, forgets, quotas and receipts. Never reopen from a
snapshot alone. For live gates, record operator approval for exact resources,
provider/source terms, account caps, request ceilings, time and teardown.
Measure caps and billing independently, including outages, retries and ancillary
search/count/embed calls. The [strict-zero gate](../../infrastructure/policy/strict_zero/strict_zero_release_gate.py)
requires actual report evidence before any strict-zero claim.
