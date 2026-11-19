# Shared application service implementation evidence

2026-11-18. **E1 synthetic implementation candidate. E2 disposable PostgreSQL witness. E3 production `NO_GO`.** Independent review is pending.

## Entry and review target

Jason Kli, requesting maintainer, authorized implementation of the handoff in this session at `9e2661c483795d05269b62d91117a424d4452d9a`. The authorization covers a private, default-off synthetic composition and disposable PostgreSQL checks. The supplied prompt governs the work and the companion plan defines the acceptance inventory. Existing documentation changes and untracked handoffs were preserved. No frozen source identities, published schemas, migration files or fixtures were regenerated.

The result is the single commit introducing this report. Use the exact result revision for independent review.

```sh
git log -1 --format=%H -- docs/context-inference-integration/evidence/2026-11-18-shared-application-service.md
git show --stat --oneline "$(git log -1 --format=%H -- docs/context-inference-integration/evidence/2026-11-18-shared-application-service.md)"
```

| Prerequisite | Exact disposition carried into the result |
| --- | --- |
| Authority design | Independent entry failed at `a669b3fc`. The actor/dependency mapping and both snapshot outcomes await independent disposition after repair. The shared fixture verifies the direct-human actor before projecting its opaque source identity. |
| Application sources | Independent result blocked at `16d02a78`. The maintainer accepted scoped remediation. Aggregate mixed-provider budgets, independent final acceptance and post-change CI remain open. This composition uses a single source installation and one projection per request. [Source remediation](2026-11-18-synthetic-application-context-review-remediation.md) |
| Outbound MCP | Independent E1 failed at `50bff63e`. Remediation at `be210388` awaits independent re-review. Physical synchronous cancellation and installed-client E2 remain open. The shared service has no MCP dependency. [MCP remediation](2026-11-18-synthetic-context-mcp-independent-remediation.md) |
| Local SIWC | Independent E1 failed at `be9dcee9` and again for rooted offers at `f847f927`. The selected-account catalog and root checks at `9e2661c` await independent re-review. Terminal usage, zero-credit evidence, local live provider behavior and managed eligibility remain open. The standalone regression is source-free. [SIWC verification](2026-11-18-synthetic-local-chatgpt-inference.md) |
| Routing | Source-free E1 and earlier native accounting E2 await independent review. The pinned base exhibits frozen source drift and a paid receipt expectation failure. The shared candidate exercises only strict-free dispatch. Paid settlement, source-identity review and hosted provider isolation remain separate gates. [Routing verification](2026-11-18-configurable-inference-routing.md) |

## Implementation inventory

| Changed paths | Earlier behavior and candidate behavior |
| --- | --- |
| `backend/src/personal_ai/auth/application_clients.py`, `auth/middleware.py` | Existing exact token/client policy remains. The isolated test app requires direct external bearer identity and current owner, client, app and workspace access. It binds an opaque conversation namespace to the verified client tuple and omits external workspace identifiers from request logs. |
| `backend/src/personal_ai/entities/conversation.py`, `persistence/dynamodb/_helpers.py`, `storage/fake.py` | Historical conversation identities remain in their original scopes. Newly created isolated conversations retain an internal client namespace. Prepared assistant rows can carry payload-free source dependencies. DynamoDB JSON hydration supports the additive fields. Client-partitioned listing is enabled on the fixture repository, with an explicit storage denial when that port is unavailable. |
| `backend/src/personal_ai/services/conversations.py`, `services/chat/service.py`, `api/routes.py`, `api/chat_stream.py`, `main.py` | The existing handlers gain opt-in client-partitioned create/read/replay, actual source revalidation on preview and status, whole-response denial and a content-free end to revoked streams. Private grant metadata stays out of external response projections. The shared lane refuses reuse of a user-only or failed intent. Advisory launch scope mismatches receive a safe input error. |
| `backend/src/personal_ai/context/authority.py`, `context/history.py`, `llm/disclosure.py` | Shared authority checks recognize dual-grant source snapshots, carry prepared dependencies into subsequent checks, and expose payload-free reference digests to the request-local dispatch guard. The existing assembler renders the approved projection as untrusted data. |
| `backend/src/personal_ai/routing/service.py` | The direct strict-free lifecycle can cancel an exact authorized reservation under its canonical root lock. An already claimed attempt keeps its fence. Isolated paid and plan flows retain their existing lifecycle. |
| `backend/tests/app_context_support/context.py`, `source.py`, `wire.py`, `shared.py`, `shared_inference.py` | The frozen Travel and Fitness fixtures remain valid. Test adapters support a typed third source, exact signed revision attestations, revision-checked owner controls, per-client capacity and an injected strict-free recipient. |
| `backend/tests/test_shared_application_service.py`, `persistence/test_shared_application_service_postgres.py` | The end-to-end consumer and native tests cover normal handlers, SDK reconnection, retained authority, attempted bypasses, two database pools, a crash boundary, ownership fences and a native snapshot restore. |
| `backend/src/personal_ai/applications/README.md`, `docs/context-inference-integration/README.md`, `delivery-and-acceptance.md`, `shared-application-service.md`, this report, `docs/current-state.md` | The integration guide, scoped maintainer decision and evidence are linked from the owning documentation. Production remains `NO_GO`. |

Paths abbreviated inside an inventory row are relative to that row's first directory prefix. The changed-file list from `git show` gives all repository-relative paths.

## Reproduction and command results

Environment used CPython 3.11.15, uv 0.11.13, FastAPI 0.142.2, Starlette 1.7.0, Pydantic 2.13.5, httpx 0.28.1, pytest 8.4.2, Ruff 0.16.10, psycopg 3.3.6, Hatchling 1.27.0 and google-auth 2.59.1. The installed SDK wheel and sdist reported `personal-ai-sdk==0.1.0` and used consumer contract 1.2.0. The native cluster used Homebrew PostgreSQL 17.11 with pgvector on loopback and disposable test databases.

Run the following from the repository root. `UV_CACHE_DIR` points to a writable local cache. The first attempt to use the default cache hit the workspace sandbox. Subsequent runs used a fresh writable cache with `UV_OFFLINE=1`.

```sh
export UV_CACHE_DIR="$(mktemp -d /tmp/pas-shared-uv.XXXXXXXX)"
make naming-policy-check
make source-contract-check
UV_OFFLINE=1 make consumer-contract-check
UV_OFFLINE=1 make sdk-install-check
PATH="$PWD/backend/.venv/bin:$PATH" make backend-lint
make hermetic-capability-check
backend/.venv/bin/python backend/scripts/consumer_contract_check.py --check
git diff --check

sdk_probe="$(mktemp -d /tmp/pas-shared-sdk.XXXXXXXX)"
UV_OFFLINE=1 uv venv --python backend/.venv/bin/python "$sdk_probe"
UV_OFFLINE=1 uv pip install --python "$sdk_probe/bin/python" --no-deps \
  sdk/python/dist/personal_ai_sdk-0.1.0-py3-none-any.whl
sdk_site="$sdk_probe/lib/python3.11/site-packages"
SHARED_SERVICE_SDK_SITE="$sdk_site" \
PYTHONPATH="$sdk_site:examples/project-checklist/client/src:examples/project-checklist/host/src" \
  backend/.venv/bin/python -B backend/scripts/offline_test_runner.py -q --tb=short \
  sdk/python/tests backend/tests/{test_application_scope,test_applications,test_external_consumer_http,test_synthetic_application_context,test_external_turns,test_external_turn_composition,test_shared_application_service,test_context_authorization,test_routing_decision_lifecycle,test_travel_context,test_research_routes,test_domains,test_booking_extractions,test_itinerary_proposals}.py

bridge_tmp="$(mktemp -d /tmp/pas-shared-bridge.XXXXXXXX)"
backend/.venv/bin/python -B backend/scripts/offline_test_runner.py --basetemp="$bridge_tmp" -q \
  backend/tests/{test_isolated_inference,test_local_inference,test_chatgpt_bridge_transport,test_chatgpt_oauth}.py
```

The base comparison used the same tools and an archive of the trusted base for tracked-file checks, omitting the new fixture. The first focused run needed the Checklist example packages on `PYTHONPATH` for collection. The final focused runs used the independently installed SDK wheel in preference to the SDK source tree and asserted its import location. The bridge used a protected disposable temporary directory. No credential values, model inputs or domain records are included in this report.

```sh
# Run with an authorized, disposable local cluster and a role that can create databases.
export PERSISTENCE_TEST_POSTGRES_DSN=postgresql://postgres@127.0.0.1:55481/postgres
backend/.venv/bin/python -m pytest -q --tb=short \
  backend/tests/persistence/{test_shared_application_service_postgres,test_inference_monetary_accounting,test_routing_decisions,test_provider_usage_accounting}.py
```

| Check | Pinned base | Candidate |
| --- | --- | --- |
| Focused backend and SDK, offline | Exit 0. 442 passed, including 203 in the six requested existing backend modules. Zero blocked network attempts. | Exit 0. 464 passed, including 22 new shared-service cases. Zero blocked network attempts. |
| Standalone bridge and isolated inference, offline | Exit 0. 186 passed. | Exit 0. Same 186 passed. Zero blocked network attempts. |
| `make naming-policy-check` | Checkout exit 2 on pre-existing untracked handoffs. Clean tracked archive exit 0. | Checkout exit 2 on user-owned untracked handoffs. The candidate overlaid on a clean tracked archive exited 0. |
| `make source-contract-check` | Exit 2. Existing planning and offline information handling source-identity drift. | Exit 2. Edited runtime paths are source-locked and require independent source-identity review. Frozen manifests were preserved. |
| `UV_OFFLINE=1 make consumer-contract-check` | Exit 2 at `core_evaluation_probe.py` due to planning source-identity drift. | Exit 2 at the same probe. The direct static OpenAPI check exited 0 with `CONSUMER_CONTRACT=PASS`. |
| `UV_OFFLINE=1 make sdk-install-check` | Exit 0. Wheel and sdist checks passed. | Exit 0. Wheel and sdist checks passed. |
| `make backend-lint` | Exit 0. | Exit 0. |
| `make hermetic-capability-check` | Exit 2 at memory research, with one failure and 67 setup errors in the memory research suite tied to the frozen source identity. | Exit 2 at adaptive conformance with `adaptive_conformance_source_changed`. The changed runtime bytes require a separately reviewed identity. |
| PostgreSQL shared and accounting suites | Exit 1. 52 passed. `test_money_and_quota_commit_together_and_reconcile_exact_attempt` expected a conflict but got `inference_charge_receipt_unverified`. | Exit 1. 56 passed and the same paid regression failed. The shared-only rerun exited 0 with four passing cases. The initial sandboxed database run could not open loopback, so native execution ran with reviewed access to the disposable cluster. |
| `git diff --check` and changed-document links | No implementation patch. | Exit 0 for the implementation patch. |

## Bounds and negative observations

| Boundary | Actual fixture limit and observed behavior |
| --- | --- |
| Consumer input | Body limit 131,072 bytes and ten-second body read deadline. The exact byte limit reached the handler and the next byte got 413. Content caps at 20,000 characters and title at 200. Malformed JSON, extra identity or credential fields and launch scope substitution fail before domain reads or messages. |
| Projection and signed metadata | One registered same-app source, one search and one exact fetch, one projected result, 4,096 turn exchange/projection bytes, 256 local estimated source units and a two-second source deadline. The existing source wire caps a message at 8,192 bytes and a string at 2,048 UTF-8 bytes. A second record produced one search and zero additional fetches. The source budget tests exercised the exact byte, token, call and clock boundaries. Signed revision attestations have a separate 128-read request cap and carry no projection payload. |
| Turn and stream | The fixture uses a 4,096-token context setting, holds 100 output tokens and a 20-token margin, and runs under a five-second request deadline. One active source/stream request per exact external client and two in total. The saturation and cancellation tests hold worker slots until synchronous work exits. The SDK enforces 262,144 bytes per event and 2,000,000 bytes per stream. |
| Dispatch | Exactly one physical claim per continuation, zero auxiliary calls and zero automatic reselections. The final authorization checks the exact source and recipient in the claim transaction and again after commit immediately before the transport handoff. The postcheck-to-write interval remains a residual race. The bytes sent before a subsequent revocation cannot be recalled. |
| Denial counters | Unenrolled, wrong scope, invalid binding, unsupported operation and missing-recipient preview cases produced zero foreign projection lookups, generation sends and message writes. One source-side membership denial verified a signed exchange before denying with zero record lookups. A failed continuation can retain its user intent and failure state. After-claim revocation produced one retained claim and zero transport writes. The lost terminal replay made one original send and zero repeat sends. No memory lanes or live provider, MCP or OAuth transports were installed. |

## Outputs

| Output | Observation and witness | Tier and boundary |
| --- | --- | --- |
| O5-01 | Maintainer decision, named base, tool versions, clean comparison and pre-existing failures recorded above. | Static entry. Independent prerequisite decisions are open. |
| O5-02 | `test_independent_clients_owners_workspaces_and_generic_onboarding` ran one registry and service for three contributions with normal conversation operations. | E1. Hosted onboarding remains closed. |
| O5-03 | `test_identity_and_operation_denials_precede_source_reads_or_writes` used the real middleware and verifier logic with injected claims. | E1. Signature network path and deployed IAM require separate witnesses. |
| O5-04 | `test_install_grants_client_rotation_and_owner_disconnect` saw zero implicit grants, one CAS winner and an owner-control disconnect. | E1. Synthetic source authority is in memory. |
| O5-05 | `test_current_source_rights_gate_preview_replay_status_and_detail` and `test_source_acl_is_independent_of_pas_grant_and_signature` maintained exact scoped, revisioned dependencies. | E1. Mixed-source budgets and live ACLs are open. |
| O5-06 | `test_wheel_consumer_journal_and_exact_recipient` drove create, preview, continue and original-key status with the installed SDK. The injected recipient saw the one projected field once. | E1. No live model or external deployment. |
| O5-07 | `test_shared_stream_slots_hold_until_worker_exit_and_other_client_available`, `test_cancelled_response_keeps_physical_slot_until_worker_really_exits` and rotation tests exercised scoped output, capacity and lookup denials. | E1. Distributed limits and native conversation listing are open. |
| O5-08 | Native quota/restart, cancellation race, worker-loss and restored-snapshot tests exercised independent PostgreSQL connections and a witness outside the restored database. | E2 PostgreSQL for identity, routing and accounting. Conversation and synthetic source stores remain in memory. Native conversation restore and deployed recovery remain open. |
| O5-09 | The [integration guide](../shared-application-service.md) covers client binding, workspace rules, separate grants, no-AI behavior, journaling and disconnect. Existing scope, Travel and domain tests ran unchanged. | Static/E1. No legacy backfill. |
| O5-10 | Command results, inventory, exact target and crosswalk recorded here. | E1/E2 candidate only. E3 stays `NO_GO`. |

## Acceptance crosswalk

Shared E1 names below identify nodes in [the ASGI suite](../../../backend/tests/test_shared_application_service.py). Native names identify nodes in [the PostgreSQL suite](../../../backend/tests/persistence/test_shared_application_service_postgres.py). Unqualified legacy nodes retain their original suites.

| ID | Observation and test node | Tier and limitation |
| --- | --- | --- |
| PAS5-01 | `test_independent_clients_owners_workspaces_and_generic_onboarding` completed Travel and Fitness turns with separate bindings and one PAS process. | E1, synthetic identities and sources. |
| PAS5-02 | The same node completed a Reading turn using its own contribution, workspace and typed adapter. | E1, third fixture app. |
| PAS5-03 | `test_identity_and_operation_denials_precede_source_reads_or_writes` denied unknown client, wrong party, expired or disabled binding, inactive owner, issuer, email and domain failures. Equal-party absent `azp` worked in the positive run. Denials incurred zero record lookups. | E1, synthetic verification boundary. |
| PAS5-04 | The identity node denied service-only, forwarded and typed-task assertions on the conversation route. | E1, explicit human subject admission. |
| PAS5-05 | The onboarding node observed two distinct owners for one admitted email. The identity and malformed-input nodes denied an app-supplied owner. | E1, issuer/subject mapping. |
| PAS5-06 | The identity and malformed-input nodes denied header substitution, wrong workspace and conflicting launch metadata. | E1, source stores untouched. |
| PAS5-07 | The identity node denied a valid Fitness token for a declared workspace when the authorizer was absent. | E1. |
| PAS5-08 | `test_install_grants_client_rotation_and_owner_disconnect` checked the installed source and empty grant store before link. | E1, operator setup in process. |
| PAS5-09 | The same node rejected wildcard fields and a stale expected revision. Dependency tests enforced expiry, actor and installation epoch. | E1, source control store in memory. |
| PAS5-10 | The identity, rotation and onboarding nodes denied other actors, bindings and partitions before disclosure. Distinct recipient and purpose grants did not unlock model projection. | E1, exact scopes. |
| PAS5-11 | The rotation/grant node tried manual, MCP and local SIWC grants with the runtime grant. Each combination denied before projection. | E1, no installed ChatGPT client. |
| PAS5-12 | `test_source_acl_is_independent_of_pas_grant_and_signature` denied one valid signed exchange when the source removed membership. Zero record lookups followed. | E1, in-process source authority. |
| PAS5-13 | The onboarding and source-reuse nodes kept identical refs and request keys separate across owners, apps and workspaces and denied disabled installations. | E1, named partitions. |
| PAS5-14 | `test_current_source_rights_gate_preview_replay_status_and_detail` denied stale record revision, changed watermark, expiry, revoked grants and disabled installations. `test_source_short_read_and_missing_prepared_dependency_deny_whole_response` denies a removed dependency. | E1, no live source race timing. |
| PAS5-15 | The wheel node verified exact fields, untrusted rendering and sensitivity/provenance through the shared assembler. `test_one_projection_fanout_and_work_budgets` exercised bounds. | E1, local estimate. |
| PAS5-16 | The fanout node refused a second record without any additional fetch. The fixture registers one source installation per application per request. | E1, mixed-provider budget remains open. |
| PAS5-17 | The wheel node observed injection text only as a JSON field inside the untrusted data envelope at the synthetic recipient. | E1, no tools in the transport. |
| PAS5-18 | The grant/install and input denial nodes observed zero sends and zero domain lookups before user intent. Offline checks observed zero network attempts. | E1, memory disabled and no polling or paid lane installed. |
| PAS5-19 | The identity node denied account export, developer usage, guessed artifacts and execution discovery. | E1, static consumer operation set. |
| PAS5-20 | The wheel node, SDK suite and static contract passed. The installed SDK retained its local version check and completion protocol. | E1, independent package installation with an ASGI transport. |
| PAS5-21 | The wheel node journaled original target, creation key/title, conversation and body. A lost continuation response recovered canonical status by the original key. | E1, caller journal on local disk. |
| PAS5-22 | `test_request_size_and_malformed_inputs_have_no_domain_side_effects` exercised the body boundary, required schema and selector denials. The host wire remained v1.2.0. | E1, socket timeout behavior is separate. |
| PAS5-23 | The wheel node saw a sourced free transport. The standalone bridge and isolated inference suite separately passed 186 tests with source-free SIWC positives. | E1, no provider or allowance evidence. |
| PAS5-24 | `test_plan_selection_no_ai_and_uncertain_original_status` verified a standalone signature, denied its replay and choice substitution, and observed zero sends. The identity node denied execution discovery. | E1, no external offer port. |
| PAS5-25 | The same node denied body credential fields. `test_native_sourced_request_restart_quota_and_payer_separation` denied a stored subscription-only preference without provider attempts. | E1/E2, no SIWC custody port. |
| PAS5-26 | The plan/no-AI node verified the free-only default and zero sends when quota exhausted. The native quota node checked the actual shared account bucket. | E1/E2, synthetic profile. |
| PAS5-27 | The plan/no-AI and cancelled-response nodes retained unknown status and denied original-key reuse after uncertain work, with no second send or fallback. | E1/E2 retained physical fence. |
| PAS5-28 | The onboarding node interleaved owners and apps with the same keys. Payload, owner, workspace and attempt UUID stayed distinct at the worker. | E1, concurrent threads and ASGI tasks. |
| PAS5-29 | The onboarding node denied foreign UUID detail, preview, continuation and status. The identity node denied guessed artifacts and policy/account paths. | E1, access denials before source reads. |
| PAS5-30 | `test_revocation_fences_physical_claim_or_closes_output` and `test_revocation_after_a_provisional_delta_stops_further_stream_disclosure` denied new output after revocation, with already committed physical fences retained. | E1/E2. Bytes already delivered stay with the recipient. |
| PAS5-31 | `test_native_restore_before_revocation_is_quarantined_without_grant_resurrection` observed a pre-claim snapshot, current unknown attempt, owner tombstone and no recreated mapping. Restored and missing-witness paths denied access and sent zero bytes. | E2 PostgreSQL control-plane and attempt evidence. Physical source and conversation erasure remain open. |
| PAS5-32 | The wheel node exercised client restart. `test_native_loss_after_claim_retains_fence_across_worker_restart` kept a claimed row pending after simulated PAS loss and retained the claim when reconciliation marked it unknown. | E1/E2. Conversation state in the fixture survives only within the fixture process. |
| PAS5-33 | The native quota node routed two owners into one provider-account quota of two and denied the next attempt. Owner preference and payer holds remained separate, with zero monetary holds. | E2, no real payer or subscription billing. |
| PAS5-34 | The fanout, stream-slot, cancellation and malformed-input nodes exercised the stated limits and zero lookups on overflow. The second client used its bounded slot under saturation. | E1 with E2 account quota. No load-test or multi-instance claim. |
| PAS5-35 | The wheel and denial tests asserted omission of credential, workspace, private title and source body from exposed diagnostics. Stream and history projections kept grants internal. | E1, synthetic error/log assertions. Production telemetry is unverified. |
| PAS5-36 | Command results and tier-specific gates are recorded here and in [current state](../../current-state.md). | E1 synthetic candidate, E2 PostgreSQL witness, E3 `NO_GO`. |

Independent review should use the result commit and reproduce the exact recipient, client rotation, revocation between claim and transport, bounded synchronous cleanup, and restored-state quarantine. The record does not advance independent source, MCP, SIWC, paid, CI, or hosted production gates.
