# User-owned application inference verification

2026-11-18. The maintainer authorized the private hermetic scope, including disposable persistence checks. The pinned Phase 5 candidate is `f391c0563cfd0336c839fbe4f4e39af710c5cffb`, from `9e2661c483795d05269b62d91117a424d4452d9a`. Its independent verdict is deferred to the combined review. The [Phase 5 record](2026-11-18-shared-application-service.md) and [delivery ledger](../delivery-and-acceptance.md) retain independent source, MCP, SIWC, routing, paid reconciliation, frozen identity, CI and live admission gates. Production is `NO_GO`.

At entry, main was one commit ahead of origin. Local changes included a deleted reasoning PRD, its untracked relocated copy and related plans, and untracked integration plans and handoffs. Those are outside the implementation commit.

## Entry crosswalk

| Case | Owning code and contract at entry | Adjacent witness |
| --- | --- | --- |
| A1 | SDK `Client.preview` / `continue_turn` / `status`, external client middleware, application registry, consumer 1.2 contract and Phase 5 ledger | `test_wheel_consumer_journal_and_exact_recipient` |
| A2–A3 | Application contributions, `SharedSourceProvider`, `ContextAssembler`, `MemoryContextProvider`, `MemoryPermissionRevalidator`, local installation | Shared onboarding, source projection and canonical memory tests |
| A4 | Client namespace, `DispatchGrantVerifier`, `LocalChatInstallation.require_registration`, `LocalChatGPTBridge._require_dispatch`, Responses serializer | Shared identity and standalone bridge proof/catalog tests |
| A5 | `source_snapshots_current`, shared source attestations, canonical memory dependencies, chat output guard, `ProtectedLocalStore.mark_send_started` | Shared revocation tests, memory source tests and rooted bridge tests |
| A6 | `ContextAssembler`, source `TurnBudget`, shared worker slots and local output/elapsed limits | Shared fanout/slot cases and bridge bounds |
| A7 | Chat preparation CAS, canonical routing root repository, local send fence, provider terminal receipt and original-key status | Shared PostgreSQL crash/restore and local bridge restart/fence cases |
| A8 | Consumer automatic choice, `ExternalTurnDisclosure._request_sources`, `ExternalTurnDispatch.dispatch`, `CompatibilityGate` and account catalog | Shared no-AI, Travel, external-turn and standalone bridge regressions |

The standalone grant asserts a foreground source-free turn for the `personal_ai` application. Its external-turn preparation excludes memory, app sources, inherited sourced dependencies, launch and explicit selection features. The Phase 5 shared consumer selects strict-free automatically and has separate PAS-read and strict-free-recipient grants. Neither grants account-plan disclosure.

## Implementation and review target

The result is the single commit introducing this evidence file. Locate the full result SHA and review both ranges together.

```sh
base=f391c0563cfd0336c839fbe4f4e39af710c5cffb
result="$(git log -1 --format=%H -- docs/context-inference-integration/evidence/2026-11-18-user-owned-application-inference.md)"
git show --name-status --oneline "$result"
git log --oneline 9e2661c483795d05269b62d91117a424d4452d9a.."$base"
git log --oneline "$base".."$result"
```

| File | Change |
| --- | --- |
| `backend/src/personal_ai/auth/dispatch_grants.py` | Added the signed v2 foreground application permit and a content-free verification step. Kept the v1 canonical bytes and signature domain. |
| `backend/src/personal_ai/context/adapters.py` | Marked memory projections with app-plan permission edges. |
| `backend/src/personal_ai/context/authority.py` | Requires complete canonical-origin, runtime and model memory edges, plus three separate source permissions for application-plan source snapshots. |
| `backend/src/personal_ai/local_bridge/README.md` | Documented the separate app-bound runtime and local receipt boundary. |
| `backend/src/personal_ai/local_bridge/application_plan.py` | Paired runtime performs an authenticated package release, current catalog check and exact success-receipt verification. |
| `backend/src/personal_ai/local_bridge/http.py` | Keeps app-bound runtimes out of the standalone loopback factory. |
| `backend/src/personal_ai/local_bridge/runtime.py` | Pins local registration, account and host, checks the signed app envelope and provider serialization, and rechecks current authority at send-start and output. |
| `backend/src/personal_ai/local_bridge/store.py` | Persists the app-plan send fence outside replaceable receipt state before handing control to the transport. Exact old or absent receipt state reconciles against a retained fence as unknown. |
| `backend/src/personal_ai/services/chat/service.py` | Reuses one confirmed assembly and the existing append, stream, status, attribution and replay lifecycle. Keeps original message IDs and excludes prior sourced turns from plan input. Skips post-completion memory writes for this lane. |
| `backend/src/personal_ai/services/external_turns/application_plan.py` | Owns scope resolution, bounded exact preview and confirmation, transactional routing-root claim, recovery witness, signed handoff and streamed receipt use. |
| `backend/src/personal_ai/services/external_turns/plan_memory.py` | Reads one explicitly granted canonical PAS memory, checking origin rights, lifecycle/source state and exact recipient-specific epochs. |
| `backend/tests/app_context_support/application_plan.py` | Mounts the private ASGI composition with per-app paired runtimes, independent fake credentials and source/memory/recovery authorities. |
| `backend/tests/app_context_support/shared.py` | Extends the test source provider and owner grant controls with a third, exact runtime-handoff grant. Retains the single external projection and the existing free fixture. |
| `backend/tests/persistence/test_application_plan_postgres.py` | Exercises routing roots, owner tombstones, an independent OS worker, restored database state and an external recovery witness in disposable PostgreSQL. |
| `backend/tests/test_application_plan_inference.py` | Drives the installed SDK through three generic app registrations and exercises rejection, revocation, bounds, replay and local restoration. |
| `docs/context-inference-integration/README.md` | Links the user-owned inference contract. |
| `docs/context-inference-integration/delivery-and-acceptance.md` | Records scoped maintainer authorization and the combined review boundary. |
| `docs/context-inference-integration/user-owned-application-inference.md` | Documents data flow, onboarding, limits and provider admission. |
| `docs/current-state.md` | Records the current implementation and E1/E2/E3 boundaries. |
| This record | Pins the exact review range, commands and acceptance witnesses. |

## Acceptance and counters

E1 refers to the test-only ASGI app and protected local files with injected Google claims, source ACLs, ChatGPT registrations, account discovery and provider I/O. E2 covers the explicitly named native stores and process boundaries below. Conversation, app-source, memory and memory-lifecycle stores are in memory even in E2.

| ID | Witness and observations |
| --- | --- |
| A1 | The entry crosswalk names the landed base and the unaccepted dependencies. The actual path is SDK `Client.preview/continue_turn/status` → Google/client/workspace middleware and registry → `ChatTurnService.preview_bound_context` → canonical memory reader and bounded source assembler → `PlanAttempts.claim` → signed runtime handoff → `ProtectedLocalStore.mark_send_started` → injected Responses transport and durable terminal receipt. The two ranges above form the deferred independent review. |
| A2 | `test_two_owners_and_three_independent_app_registrations` runs Travel and Fitness with distinct PAS humans and local registrations. Across all three apps the test sees three local packages and three Responses writes, one of each per confirmed turn, with exact projected data and disjoint provider tokens. Unapproved title, other owners' memory text and credential material are absent from the prepared and provider payloads. `test_one_canonical_memory_can_be_shared_to_another_app_only_by_exact_consent` exercises explicit cross-app sharing by the same owner and loss of origin membership. |
| A3 | The third registered app is Reading. The [onboarding contract](../user-owned-application-inference.md#enroll-a-synthetic-app) names the existing contribution and fixture files. The new integration test adds one entry to the same selected-contributions tuple and supplies fixture book data and consent. It exercises the same SDK operations, assembler, root claim, runtime and serializer. |
| A4 | `test_foreground_confirmation_and_pas_scope_are_exact` rejects substituted content, confirmation, client, actor and workspace with zero roots or disclosed packages. `test_runtime_binding_and_signed_payload_fail_closed` rejects caller, origin, host, registration, account, recipient, package digest, signature and expiry. Only the deliberately substituted package at the runtime verifier reaches the local delivery observer. All nine cases send zero Responses requests. Distinct credentials are checked against the other stores and the PAS/app logs. |
| A5 | `test_current_rights_at_each_disclosure_boundary` runs ten changes at each of two edges. These cover both source recipient grants, record revision, source ACL, memory consent, memory edit, forgetting, owner deletion, workspace removal and unavailable witness. The pre-handoff cases disclose zero packages and send zero Responses writes. The pre-send cases disclose one package to the then-authorized local runtime and send zero Responses writes. The conservatively claimed PAS root stays fenced. `test_regrant_cannot_revive_a_preview_and_public_loopback_refuses_the_app_runtime` verifies a new memory epoch cannot revive a prior approval. `test_revocation_after_a_delta_blocks_subsequent_output_and_replay` permits one provisional delta, then withholds subsequent output, status content and detail after forgetting. |
| A6 | `test_aggregate_context_budget_and_single_external_projection` tests aggregate 8,192 bytes and 3,072 estimated token allocations, then lowers each cap by one and observes zero new source lookups. Both successful boundaries share one assembly, one search and one exact fetch. The source exchange retains its 4,096-byte / 256 local estimated-unit cap and two-second deadline. The memory read admits one record, caps raw memory text at 1,024 UTF-8 bytes, and bounds the projected item together with its metadata at 4,096 bytes. The one preview uses up to 10,240 context units with 100 output and 20 safety units reserved. Canonical local and provider bodies cap at 8,192 bytes each, with 100 output bytes and characters. `test_private_preview_shares_worker_slots_and_deadline` exercises one active slot per client, independent availability for a second under the two-slot global cap and deadline denial. The ASGI body remains on the existing 131,072-byte / ten-second ingress limit and the turn has a five-second deadline. Authority attestations retain the shared 128-read limit. |
| A7 | `test_same_key_race_and_replay_keep_one_transport_and_opaque_foreign_status` observes one physical send across the original race and replay, uniform foreign/absent status and revocation of replay. `test_interrupted_stream_restart_and_older_local_state_retain_physical_fence` interrupts after one provisional delta and one physical send, observes unknown, restarts the local store against an older receipt snapshot, and sees the independent send fence deny a second claim. Native `test_native_ambiguous_plan_fence_and_owner_deletion_survive_restore_boundary` observes one ambiguous physical send, a PostgreSQL root and owner tombstone, and quarantine against older PostgreSQL state and a missing witness. Native `test_worker_loss_after_native_claim_preserves_original_key_and_prevents_resend` commits from a separate OS process and exits before signing. An independent database pool observes the fence and rejects another claim. The original key stays unknown and zero local packages or provider sends occur at that crash boundary. All cases observe zero fallback sends. |
| A8 | `test_ineligible_plan_has_safe_no_ai_and_no_fallback` denies missing registration, missing model visibility, uncertain credits, disconnected account, missing source or memory consent and the old consumer parser. Normal conversation operations remain available. The pinned pre-change grant parser rejects v2 and reproduces the exact v1 canonical bytes. Installed SDK, legacy Travel, external turns and standalone local bridge regressions run independently. |

## Provider reconciliation

The official SIWC terms effective November 4, 2026 require app-specific identity, supported sign-in, secure persistent local token custody, user consent and revocation, app-specific purpose and user-controlled execution. They restrict pooling, limit bypass and use of one subscriber for another user's requests. The plan controls describe separate authorization for plan use, per-app limits, and situations where available personal or workspace credits can be charged. An eligible sign-in or a listed model therefore gives insufficient evidence of zero credit spend. [SIWC terms](https://openai.com/policies/sign-in-with-chatgpt-terms/) · [Plan and credit controls](https://help.openai.com/en/articles/20001542-using-your-chatgpt-plan-in-other-apps-and-sites)

E3 requires approval or verified eligibility for each exact distribution topology and registration, deployed principal and client verification, independently authenticated confidential runtime delivery, secure custody, fresh revocation and eligibility observations, enforceable included-only cost controls and trustworthy terminal and usage evidence. The last authority check and the physical write are separate, so revocation can race an already committed send. The fixture keeps previews in bounded process memory until consumed or expired and swept on a later preview. Its recovery witness is injected, and native evidence covers routing roots and identity fences rather than deployed recovery, physical erasure or live revocation. Production remains `NO_GO`.

## Reproduction and results

The environment used CPython 3.11.15, uv 0.11.13, the installed `personal-ai-sdk==0.1.0` wheel, consumer contract 1.2.0 and disposable PostgreSQL 17.11 with pgvector. Both runtime suites ran through the offline network fence. A local clone preserved Git history for the pinned comparison. For naming, a second clean clone overlaid only the implementation paths. The initial archive comparison lacked Git history, so the results below use the history-preserving clone.

```sh
export UV_CACHE_DIR="$(mktemp -d /private/tmp/pas-app-plan-uv.XXXXXXXX)"
export UV_OFFLINE=1
export PATH="$PWD/backend/.venv/bin:$PATH"
make backend-lint
make naming-policy-check
make source-contract-check
make consumer-contract-check
make sdk-install-check
make hermetic-capability-check
backend/.venv/bin/python backend/scripts/consumer_contract_check.py --check
git diff --check

sdk_probe="$(mktemp -d /private/tmp/pas-app-plan-sdk.XXXXXXXX)"
uv venv --python backend/.venv/bin/python "$sdk_probe"
uv pip install --python "$sdk_probe/bin/python" --no-deps sdk/python/dist/personal_ai_sdk-0.1.0-py3-none-any.whl
sdk_site="$sdk_probe/lib/python3.11/site-packages"
SHARED_SERVICE_SDK_SITE="$sdk_site" \
PYTHONPATH="${sdk_site}:examples/project-checklist/client/src:examples/project-checklist/host/src" \
backend/.venv/bin/python -B backend/scripts/offline_test_runner.py -q --tb=short \
  sdk/python/tests backend/tests/{test_application_plan_inference,test_application_scope,test_applications,test_external_consumer_http,test_synthetic_application_context,test_external_execution_contracts,test_external_turns,test_external_turn_composition,test_shared_application_service,test_context_authorization,test_routing_decision_lifecycle,test_travel_context,test_research_routes,test_domains,test_booking_extractions,test_itinerary_proposals,test_memory,test_memory_control_context}.py

bridge_tmp="$(mktemp -d /private/tmp/pas-app-plan-bridge.XXXXXXXX)"
backend/.venv/bin/python -B backend/scripts/offline_test_runner.py --basetemp="$bridge_tmp" -q --tb=short \
  backend/tests/{test_isolated_inference,test_local_inference,test_chatgpt_bridge_transport,test_chatgpt_oauth,test_chatgpt_local_lifecycle}.py

# Use a disposable PostgreSQL instance and a role that can create test databases.
# The recorded run used a private Unix socket with TCP listening disabled.
backend/.venv/bin/python -m pytest -q --tb=short \
  backend/tests/persistence/{test_application_plan_postgres,test_shared_application_service_postgres,test_inference_monetary_accounting,test_routing_decisions,test_provider_usage_accounting}.py
backend/.venv/bin/python -m pytest -q --tb=short \
  backend/tests/persistence/{test_application_plan_postgres,test_shared_application_service_postgres}.py
```

The pinned runs omit the two new test modules and put the pinned backend source first on `PYTHONPATH`. The SDK and standalone tests use protected temporary directories. The database setup needed reviewed local access after sandboxed `initdb` could not allocate shared memory. The database endpoint used `PERSISTENCE_TEST_POSTGRES_DSN=postgresql://postgres@localhost:55483/postgres?host=<private-socket-dir>`. The configuration and test databases were disposable.

| Command | Pinned base | Implementation |
| --- | --- | --- |
| Installed SDK and focused suites through `offline_test_runner.py` | Exit 0. 540 passed. | Exit 0. 589 passed, including 49 new plan cases. Zero blocked network attempts in both runs. |
| Standalone bridge, local OAuth lifecycle and isolated routing | Exit 0. 230 passed. | Exit 0. 230 passed. Zero blocked network attempts. |
| Native shared service, app plan and accounting regression | Exit 1. 56 passed and the existing paid-receipt test failed. | Exit 1. 58 passed and the same paid-receipt test failed. The shared and app-plan-only native run exited 0 with six passing cases. |
| `make naming-policy-check` | Exit 0 in the clean clone. | Exit 2 in the workspace on pre-existing untracked handoffs. The implementation-only clean overlay exited 0. |
| `make source-contract-check` | Exit 2. Pinned planning and offline-information-handling source drift. | Exit 2. The workspace check detects modified bound sources. The frozen identities are unchanged and require separate review. |
| `make consumer-contract-check` | Exit 2 at `core_evaluation_probe.py` with `planning_portable_baseline_changed_requires_new_version`. | Exit 2 at the same probe. The direct static contract command exited 0 with `CONSUMER_CONTRACT=PASS`. |
| `make hermetic-capability-check` | Exit 2 at `reasoning-adaptive-conformance` with `adaptive_conformance_source_changed`. | Exit 2 at the same gate. The preceding fence, reasoning, orchestrator, grounded and adaptive suites passed. |
| `make sdk-install-check` | The same consumer artifacts are used for the pinned focused comparison. | Exit 0. Both wheel and source-distribution install probes passed. |
| `make backend-lint` | Phase 5 evidence records exit 0. | Exit 0. |
| Pinned dispatch-model compatibility probe | Loads a candidate v1 envelope and emits identical canonical bytes. Rejects V2 at version and unknown-field checks. | Exit 0 for the two-revision probe. |
| `git diff --check` and changed Markdown links | The comparison tree contains no patch. | Exit 0. 61 local links resolved across six changed documents. |

The paid failure is `test_money_and_quota_commit_together_and_reconcile_exact_attempt`. It expects a conflict from an altered charge receipt and receives `inference_charge_receipt_unverified` in both revisions. The paid lane, frozen manifests, public schemas, migrations and provider/emulator gates are carried forward. This verification exercised no live OAuth, payment, deployment, provider call or emulator.
