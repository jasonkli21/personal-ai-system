# Configurable inference routing verification

2026-11-18 · Source-free synthetic implementation and disposable PostgreSQL witness. Independent review is pending. E3 remains blocked and production remains `NO_GO`.

## Revision and scope

Base `a97427f52f2f1a306dad238044d04fd76cfdbca7` matched the clean checkout and reviewed upstream. The review target is the single commit containing this report. Its exact SHA is the result of `git log -1 --format=%H -- docs/context-inference-integration/evidence/2026-11-18-configurable-inference-routing.md`.

The attached implementation prompt and plan were read as companion inputs outside the repository. The [gate ledger](../delivery-and-acceptance.md), [current state](../../current-state.md), and [SIWC repair record](2026-11-18-siwc-repair.md) govern dependencies. Independent Stage 0 exit and final source acceptance, mixed-source budgets, MCP physical cancellation and installed-client acceptance, SIWC terminal attestation, and frozen source-identity review remain open. The fixture uses source-free foreground input and verified synthetic principals. It confers no earlier acceptance, credential custody, source permission, or provider approval.

| Changed paths | Behavior |
| --- | --- |
| `routing/{owner_policy,isolated,price}.py` | Strict v2 read/write semantics, exact scope and operator grant intersection, ordered candidates, bounded root, typed pricing and settlement, and source-free fixture composition. |
| `routing/{service,registry,decision_models}.py` | Exact internal route reuses the canonical decision and finalize–claim–dispatch path. The public automatic route accepts only strict-free requests. |
| `auth/dispatch_grants.py`, `services/external_turns/dispatch.py`, `local_bridge/{lifecycle,runtime}.py` | The local issuer signs the fenced root and package with a bounded deadline. Offers for that root use exact admitted model evidence and deny credential refresh and discovery. The existing signature and execution path for other offers still apply. |
| `persistence/migrations/037_inference_policy_accounting.sql`, `persistence/postgres/inference_policy.py`, `persistence/postgres/usage/{accounting,monetary,retention}.py` | Owner CAS and root fences, exact USD hold and claim in the existing transactions, authoritative settlement, and durable unresolved exposure. Existing usage rows acquire no implied monetary settlement. |
| `tests/test_isolated_inference.py`, `tests/test_chatgpt_local_turn.py`, `tests/persistence/test_inference_monetary_accounting.py` | Synthetic routing, local offer, and native accounting witnesses. |
| `docs/current-state.md` and this report | Living status and review evidence. |

## Evidence classes

- **E1 hermetic.** Routing ran through the Python audited offline runner. Four terminal classes each produced one invocation of the injected innermost fixture callback and zero repeat callbacks. The positive local offer published one signed package after the root fence. The local mock recorded one Responses POST and zero refresh or discovery calls, including replay. Missing consent, distribution, account/model, or included-only eligibility recorded zero provider fixture calls. No real sends or spend.
- **E2 native accounting.** Tests used a disposable PostgreSQL 17.8 server with pgvector, isolated test databases, and separate pool connections. The witness exercised migration/idempotence, first-write and shared-payer contention, rollback on permit/claim publication failure, definitive no-send cancellation, claim crash and restart, authoritative settlement, retention, owner fence, and an earlier cloned database with an independent fixture recovery witness. The single-send test observed the committed attempt claim and monetary state from a separate database transaction before its one synthetic callback. A separate cancellation race permitted zero or one callback according to which transaction won. No real provider billing or sends.
- **E3 external.** Unverified. No live OAuth, provider transport, real account, upstream billing or credit check, shared-host credential storage, live source, deployment, or production migration. Local SIWC remains `BLOCKED_UNVERIFIED`; managed SIWC remains `BLOCKED_PENDING_APPROVAL`. OS provider isolation requires a supported host and was skipped.

## Command record

Commands ran from the repository root except native pytest, which ran under `backend/` with a disposable loopback `PERSISTENCE_TEST_POSTGRES_DSN`. Python 3.11.18 used the locked backend dependencies. The bridge used protected temporary storage under `/dev/shm`; the Python audit fence remained active. The native database test intentionally uses loopback. MCP ran on Python 3.12.14 with `mcp==2.3.0`.

| Command | Result |
| --- | --- |
| `make naming-policy-check`; `backend/.venv/bin/python -m ruff check backend`; `git diff --check` | Exit 0 each. |
| `make source-contract-check` | Exit 2. Frozen planning and offline runtime identities already failed at the clean base. The candidate changes additional bound files. Frozen identities were preserved. |
| `python backend/scripts/offline_test_runner.py -q` on `test_isolated_inference.py`, `test_quota_aware_routing.py`, `test_routing_decision_lifecycle.py`, `test_provider_usage.py`, `test_inference_execution.py`, and `test_endpoint_registry.py` | Exit 0. 203 passed. Zero blocked Python network attempts. |
| Same runner on the focused source-free local turn and policy offer cases with `--basetemp` on protected storage | Exit 0. 32 passed, including 24 external execution contract cases. Zero blocked Python network attempts. |
| Same runner on `test_chatgpt_local_turn.py`, `test_chatgpt_bridge_transport.py`, `test_chatgpt_local_lifecycle.py`, and `test_chatgpt_local_operator.py` with protected storage | Exit 1. 164 passed, 11 failed. Zero blocked network attempts. The clean base reproduced the same 11 failures with 159 passes. These comprise fixture/setup expectations and the earlier bridge replay behavior. |
| `make mcp-context-check MCP_ADAPTER_PYTHON=<Python 3.12 environment>` | Exit 0. 99 passed, zero blocked network attempts. |
| `make hermetic-capability-check PLATFORM_PYTHON=<Python 3.11 environment>` | Exit 2 at `memory-research-check` (1 failed, 44 passed, 67 errors in that target). The clean base reproduced the same result. The sealed reasoning suite passed on Python 3.11. |
| `python -m pytest -q tests/persistence/test_inference_monetary_accounting.py tests/persistence/test_routing_decisions.py tests/persistence/test_provider_usage_accounting.py` | Exit 0. 53 passed (14 new monetary and policy cases, 39 routing and usage regressions). No skips. |

## Acceptance crosswalk

E1 refers to `test_isolated_inference.py`, local refers to `test_chatgpt_local_turn.py`, and E2 refers to `test_inference_monetary_accounting.py`. These are development witnesses.

| Case | Executed witness or remaining evidence |
| --- | --- |
| ROUTE4-01 | E1 `test_legacy_and_bad_settings_infer_no_grants` and `test_settings_requires_current_verified_owner_and_management_scope`; existing `test_inference_execution.py` factory gates. |
| ROUTE4-02 | Existing `test_inference_execution.py` fake and explicit mode cases; E1 uses a distinct synthetic callback with no external attribution. |
| ROUTE4-03 | E1 `test_settings_requires_current_verified_owner_and_management_scope`, `test_scope_and_payload_fences_never_call_transport`; E2 `test_shared_payer_last_unit_and_first_settings_write_race`. |
| ROUTE4-04 | Existing `test_endpoint_registry.py` and `test_quota_aware_routing.py` cover profile, privacy, counters and quality; the isolated candidate reuses the canonical checks. Live operator kill-switch orchestration remains outside the fixture. |
| ROUTE4-05 | E1 `test_class_order_and_exact_intersection`, `test_scope_and_payload_fences_never_call_transport`; nonempty external source acceptance stays blocked. |
| ROUTE4-06 | Local `test_policy_offer_fences_before_publication_and_stays_local` and `test_issuer_requires_paired_foreground_principal_and_denies_explicit_sources`. |
| ROUTE4-07 | Local `test_policy_offer_fences_before_publication_and_stays_local` parameterized eligibility denials. |
| ROUTE4-08 | E1 `test_scope_and_payload_fences_never_call_transport`; policy-aware operations reject auxiliary capabilities. |
| ROUTE4-09 | E1 `test_quota_preflight_moves_only_to_next_authorized_candidate`; E2 `test_abandon_releases_only_unclaimed_and_preserves_root_order`. |
| ROUTE4-10 | Existing `test_endpoint_registry.py`; E1 `test_class_order_and_exact_intersection` rejects stale and mismatched grants. Live evidence stays blocked. |
| ROUTE4-11 | E1 `test_class_order_and_exact_intersection`; within-class input rank comes from trusted internal composition and is preserved. A multi-class benchmark of comparative ranking against current live quota is open. |
| ROUTE4-12 | Local `test_policy_offer_fences_before_publication_and_stays_local`; package binds the canonical issuer reservation and locally verified installation. |
| ROUTE4-13 | E1 `test_exact_price_rounding_and_unsupported_inputs`; E2 `test_no_send_on_rollback_or_preclaim_drift` and `test_money_and_quota_commit_together_and_reconcile_exact_attempt`. Real sponsor/account ownership is unverified. |
| ROUTE4-14 | E1 `test_exact_price_rounding_and_unsupported_inputs` includes 3 × 250,000 micros per million, exceeding the 1-micro ceiling, unbounded input/output and unsupported types. |
| ROUTE4-15 | E2 `test_money_and_quota_commit_together_and_reconcile_exact_attempt` and `test_claim_crash_restart_and_purge` verify owner exposure and unsettled retention. `test_owner_cap_spans_apps_and_payers_and_excess_freezes_profile` exercises owner totals across apps and payers and records excess liability. Long-running calendar rollover remains unverified. |
| ROUTE4-16 | E2 `test_shared_payer_last_unit_and_first_settings_write_race` uses different owners, endpoints and credential/quota scopes. Provider calendar evidence is synthetic. |
| ROUTE4-17 | Same E2 last-unit race yields exactly one 8-micro reservation. |
| ROUTE4-18 | E2 `test_money_and_quota_commit_together_and_reconcile_exact_attempt` and `test_no_send_on_rollback_or_preclaim_drift`. |
| ROUTE4-19 | E1 `test_scope_and_payload_fences_never_call_transport`; E2 `test_claim_crash_restart_and_purge`. |
| ROUTE4-20 | E2 `test_abandon_releases_only_unclaimed_and_preserves_root_order`, `test_revoked_owner_policy_stops_fallback_but_releases_unclaimed`, and `test_claim_races_unclaimed_cancellation_on_independent_connections`. |
| ROUTE4-21 | E1 `test_only_one_synthetic_transport_callback_and_no_public_bypass`; E2 `test_claim_crash_restart_and_purge`. The isolated signed-offer replay test records zero additional calls. Earlier unsigned-root bridge cases still repeat discovery before denial. |
| ROUTE4-22 | E2 `test_money_and_quota_commit_together_and_reconcile_exact_attempt` proves usage receipt alone leaves a hold, independent settlement reduces it, and conflicting replay fails. |
| ROUTE4-23 | E2 `test_no_send_on_rollback_or_preclaim_drift` and `test_revoked_owner_policy_stops_fallback_but_releases_unclaimed`; no separate live credential-rotation witness. |
| ROUTE4-24 | E1 `test_exact_price_rounding_and_unsupported_inputs` denies missing synthetic payer grant/exclusivity; public provider regressions enforce paid gating. Live provider exposure evidence remains blocked. |
| ROUTE4-25 | E2 `test_owner_fence_keeps_financial_audit_and_denies_policy_read`, `test_restored_older_database_cannot_reissue_claim_with_external_witness`, and the stale-attempt/purge case. A live recovery authority, external account reconciliation and physical deletion remain unverified. |
| ROUTE4-26 | E1 `test_scope_and_payload_fences_never_call_transport`; local source-free cases check scope before disclosure. No mixed-source or auxiliary network operation is admitted. |
| ROUTE4-27 | E1 `test_settings_requires_current_verified_owner_and_management_scope` and no-route/replay cases assert opaque diagnostics. |
| ROUTE4-28 | Factory, registry and MCP regressions ran as above. Broad SIWC and source-contract failures retain their recorded status. Native OS provider isolation was skipped. |
| ROUTE4-29 | Separate E1, E2 and E3 evidence above. Production remains `NO_GO`. |
| ROUTE4-30 | E1 `test_scope_and_payload_fences_never_call_transport`, quota preflight and terminal replay cases; E2 root, budget and claim race cases. The logical root allows at most 16 candidates and one claim. |

Independent review should recreate E1 and E2 at the exact review commit and inspect payload binding, financial lock order, post-commit fences, and the three closed live-provider gates. Verify any current-source identity updates in a separate reviewed change.
