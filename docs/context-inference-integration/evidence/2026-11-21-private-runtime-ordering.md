# Independent local runtime send-start ordering review

**2026-11-21 · R3-A ordering gate failed · Interprocess execution disabled · Independent acceptance pending**

The maintainer explicitly authorized this offline phase and waived pending predecessor acceptance as an entry requirement. The clean initial checkout at `f059b8223e441db40a0844017d610e9b32d0d8f0` fast-forwarded to remote main, `c96fce21ef7f31aa51cf37b709b1a347c1513351`. The first-parent sequence was `f059b82 → 0f2c34c → 28bb98e → f5d12d8 → f3da718 → 327971b → 4f98c2a → a4d4f7f → c96fce2`. R0 remains provisional, Phase 6 A01 and independent E1 remain open, and the dated Phase 6 report left A13 and three native PostgreSQL nodes unexecuted. The R1 adoption ADR remains proposed. R2-A remains implementation review pending and R2-B remains blocked externally. The waiver opens implementation entry. The current phase's ordering gate independently requires execution to stay disabled when serialization is absent. [R0 handoff](../runtime-r0/R0-exit-review-and-next-phase-handoff.md) · [R1 ADR](../runtime-contract-adoption.md) · [Phase 6 ledger](2026-11-21-private-application-inference.md) · [R2 evidence](2026-11-21-source-free-runtime.md)

The result SHA is the single direct child introducing this report. The result diff is this report and a living status entry. In the ledger, **base** means the full SHA above and **result** means the revision resolved below. Behavioral observations are synthetic and were reproduced by the implementer. No independent E1, native E2, or production E3 acceptance is claimed.

```sh
base=c96fce21ef7f31aa51cf37b709b1a347c1513351
report=docs/context-inference-integration/evidence/2026-11-21-private-runtime-ordering.md
result=$(git log -1 --diff-filter=A --format=%H -- "$report")
git diff --stat "$base" "$result"
git diff --check "$base" "$result"
test "$(git rev-parse "$result^")" = "$base"
```

## Authority and persistence

| Authority | Active baseline fixture and relevant writer | Native composition and recovery boundary |
| --- | --- | --- |
| Verified user, effective client, registered application, workspace, owner | Middleware binds current request authority. Its closure rereads the registered client policy, principal lifecycle, app registration, conversation access and workspace membership. The fixture uses fake verified claims, a file-backed client-policy test fixture, the synthetic application catalog, `HumanDirectory`, and `OwnerSourceControls`. Membership and client-policy changes are outside the runtime lock. Directory deactivation is a separate owner mutation. [Middleware](../../../backend/src/personal_ai/auth/middleware.py#L589) · [Fixture directory and controls](../../../backend/tests/app_context_support/shared.py#L140) | PostgreSQL has principal and account lifecycle adapters. Its owner advisory transaction lock covers participating PostgreSQL writers. It ends at transaction exit and establishes no exclusion over source-owner mutations, DynamoDB branch writes, or a runtime filesystem fence. [Factory](../../../backend/src/personal_ai/persistence/factory.py#L227) · [Owner lock](../../../backend/src/personal_ai/persistence/postgres/owner_lifecycle.py#L8) |
| App source, installation, current revision, recipient grants | `OwnerSourceControls.owner_control` removes an onward grant and updates the revision under its own `RLock`. The source has separate state and lock for records and attestation. `SourcePermissions.is_current` returns after checking the grant again. Source changes, grant revoke, installation updates, and expiry have independent lifetimes. The plan checks snapshots for PAS, local and model disclosure. [Grant writer](../../../backend/tests/app_context_support/shared.py#L202) · [Permission read](../../../backend/tests/app_context_support/shared.py#L384) · [Source](../../../backend/tests/app_context_support/source.py#L304) | The native plan test factory still uses these fixture authorities. The PostgreSQL federation store has its own revisioned writes and does not provide the fixture's external source transaction. Domain/source native restore was unexecuted. [Federation storage](../../../backend/src/personal_ai/persistence/postgres/federation.py#L103) |
| PAS memory, branch and conversation | Shared fixture uses `InMemoryConversationRepository` and `InMemoryMessageRepository`. Plan memory opens in-memory memory and lifecycle repositories and in-memory recipient disclosures. The rights cases modify memory consent, content, forget state and branch visibility through fixture-owned state. The disclosure guard is request-local, and the service revalidates it as well as current source snapshots. [Chat fixture](../../../backend/tests/app_context_support/shared.py#L873) · [Plan fixture](../../../backend/tests/app_context_support/application_plan.py#L91) · [Disclosure guard](../../../backend/src/personal_ai/llm/disclosure.py#L13) | The persistence factory maps conversation/message state to DynamoDB and memory/control to PostgreSQL, including a DynamoDB memory effect guard. PostgreSQL control applies lifecycle events in its own transaction. The native plan cases do not open those adapters. [Factory](../../../backend/src/personal_ai/persistence/factory.py#L73) · [Memory composition](../../../backend/src/personal_ai/persistence/factory.py#L178) · [Memory control](../../../backend/src/personal_ai/persistence/postgres/control.py#L72) |
| PAS intent, offer, claim, and proof | `ApplicationPlanService` owns pending previews/reservations, the release closure, and the active `ContextVar`. Loss of process state ends release eligibility. The diagnostic opens `MemoryRoots` for observations and roots with a separate in-memory witness dictionary under the same fixture root lock. PAS owns the Ed25519 signer. The runtime compares signed v2 scope, caller, profile and digests. [Plan service](../../../backend/src/personal_ai/services/external_turns/application_plan.py#L131) · [Fixture authority](../../../backend/tests/app_context_support/application_plan.py#L64) · [Bridge handoff](../../../backend/src/personal_ai/local_bridge/runtime.py#L308) | The three native nodes replace roots and observations with `PostgresInferencePolicy` and `PostgresRoutingDecisionRepository`. Two wire in `PostgresPrincipalDirectory`. The test-only `PlanWitness` lives outside both database snapshots with its epoch, exact per-claim records, and owner fence when explicitly recorded. It checks retargeted root state and owner deletion. There was no authorized disposable PostgreSQL DSN or running native engine for this run. [Native wiring](../../../backend/tests/persistence/test_application_plan_postgres.py#L44) · [Native deletion case](../../../backend/tests/persistence/test_application_plan_postgres.py#L164) |
| Local registration, account, credentials, fence and receipt | `PairedApplicationRuntime.deliver` checks handoff, checks the catalog, rechecks handoff before releasing the existing package, then calls `LocalChatGPTBridge.execute`. Bridge caller authorization and fake provider credentials remain at the bridge. `ProtectedLocalStore` writes registrations, revision, clock high water and receipts to `state.json`. The original dispatch identity's independent fence is a separate file in `send-fences` within the store directory. Disconnect updates registration under `runtime.lock`. The transport adapter uses `httpx.MockTransport`. [Paired runtime](../../../backend/src/personal_ai/local_bridge/application_plan.py) · [Store](../../../backend/src/personal_ai/local_bridge/store.py#L141) · [Disconnect writer](../../../backend/src/personal_ai/local_bridge/lifecycle.py#L424) |
| Caller journal and canonical reads | The installed HTTP witness persists synthetic create intent and exact continuation under distinct original UUIDs, with fsync of file and parent directory. It repeats original-key create, then uses status and matching active-branch detail after ambiguous continue. The journal stays in the caller's fixture directory. [HTTP journal](../../../backend/tests/test_private_application_plan_http.py#L263) | There is no journal restore or fresh-process TLS recovery in this review. Canonical endpoints use the synthetic repositories above. |

## Ordering at the fence

The current acquisition order is local pre-send mutex and `dispatch.lock`, then local `runtime.lock`. Under that store transaction `mark_send_started` invokes `authorize_send`. This callback rechecks the signed dispatch and PAS root authority in the existing request context, then checks local registration and credential/proof/session expiry. PAS reads client, owner, membership, source, memory and disclosure state and reads the exact root and witness in a separate observations transaction. Those reads, their locks and that transaction end before the callback returns. The runtime next checks the previously sampled store time against expiry, creates the fence with exclusive create, fsyncs the file and directory, saves the mutable receipt, and releases the local locks. Provider invocation follows. The last wall-clock sample precedes the fence write, so the existing checks also leave a potential expiry interval during a stall. [Local call sequence](../../../backend/src/personal_ai/local_bridge/runtime.py#L476) · [Store call sequence](../../../backend/src/personal_ai/local_bridge/store.py#L528) · [Fence persistence](../../../backend/src/personal_ai/local_bridge/store.py#L416) · [PAS decision](../../../backend/src/personal_ai/services/external_turns/application_plan.py#L505)

The counterexample uses the onward-recipient grant, a mandatory authority. A single missing writer suffices to fail the ordering gate. The diagnostic uses the real owner-control revoke with the expected revision. Returning from that writer witnesses removal under the grant lock. The fence observer checks absence before the original write and readability after the original fsyncs. The mock POST counter runs in the provider transport handler independently of terminal status. Hooks execute inline at the specified boundaries, so no sleeps or probabilistic scheduling determine the order.

| Ordering at the barrier | Observed order | Released packages / mock POSTs / PAS success terminal |
| --- | --- | --- |
| Revoke before the PAS decision | Grant removed → callback denied → no fence | 1 / 0 / absent |
| PAS decision, then revoke before the fence | Callback allowed → grant removed → durable fence → mock POST | 1 / 1 / absent. **Violates the gate.** |
| Fence before revoke | Callback allowed → durable fence → grant removed → mock POST | 1 / 1 / absent. Send-start was already consumed. |
| Positive control | Callback allowed → durable fence → mock POST | 1 / 1 / present |

All cases observed zero packages and mock POSTs after preview and before continue in the existing in-process fixture. In the two cases with a POST after revocation, later checks withheld success. That cannot prevent the already observed provider effect. Synthetic package counts come from the bridge receive hook. There is no receiving-process TLS plaintext witness because R3 delivery stayed disabled.

Moving the callback across a socket loses `_active` and request scope. A PAS-side inquiry routed back into the live request context could restore identity for revalidation, but returning a fresh Boolean still permits the observed order. An existing local lock includes registration writers only. Extending the PostgreSQL owner advisory lock would leave the external source and DynamoDB writers outside it, and dropping it on PAS death or timeout could still leave a runtime authorized to fence. The proof therefore lacks an authority shared by all relevant revocation writers and the durable send-start boundary, including bounded cancellation, partition, death, and expiry at that boundary. A protocol that supplies this property is a design escalation under the implementation prompt. No listener, IPC binding, TLS keys, or execution seam was added.

The root commit and exact witness write are also distinct. Death before the witness denies the active offer because `claim_current` requires its exact record. A surviving witness can detect an older database snapshot missing a root or tombstone. Joint rollback may remove the evidence needed for that comparison, and an empty or freshly created witness cannot establish continuity. The local fence protects receipt-only rollback while that directory and original identity survive. Joint restore of all authoritative state, independent generation, and owner tombstones remain unobserved and require quarantine when continuity cannot be established. [Claim ordering](../../../backend/src/personal_ai/services/external_turns/application_plan.py#L142) · [Witness checks](../../../backend/tests/persistence/test_application_plan_postgres.py#L108)

## Acceptance ledger

`AP` is `backend/tests/test_application_plan_inference.py`, `BT` is `backend/tests/test_chatgpt_bridge_transport.py`, `LT` is `backend/tests/test_chatgpt_local_turn.py`, and `HTTP` is `backend/tests/test_private_application_plan_http.py`. The command table gives the exits for these modules. “Baseline control” identifies exercised earlier behavior and gives no R3 behavioral pass. `FAIL` denotes the ordering counterexample. `REVIEW_REQUIRED` denotes an inspection or compatibility observation awaiting independent review. Rows marked `NOT_RUN` depend on the failed ordering gate unless a separate prerequisite is named.

| ID | Result · tier · SHA | Node or inspection and observation |
| --- | --- | --- |
| R3-01 | REVIEW_REQUIRED · Git and document inspection · base/result | Entry authorized. Exact ancestry above. Predecessor independent dispositions remain open. |
| R3-02 | REVIEW_REQUIRED · source inspection · base/result | Authority and persistence inventory above. No second source owner. |
| R3-03 | NOT_RUN · E1 · result | Ordinary startup has no private interprocess seam. Existing `PairedApplicationRuntime` only. |
| R3-04 | NOT_RUN · E1 · result | No independent PAS/runtime peer, handshake, substitution or ciphertext observation. |
| R3-05 | NOT_RUN · E1 · result | Existing v2 pairing has no configured mutual TLS identities or channel binding. |
| R3-06 | NOT_RUN · E1 · result | Channel rotation, attachment, replay and delivery read ordering require the missing seam. |
| R3-07 | NOT_RUN · E1 · result | Connected-unconfirmed interprocess case absent. Baseline diagnostic and HTTP `test_installed_profile_three_contributions_and_foreign_owner` observe zero release and sends before confirm. |
| R3-08 | NOT_RUN · E1 · result | In-process `_PlanGeneration.release` and positive diagnostic deliver one original package. Interprocess release unobserved. |
| R3-09 | NOT_RUN · E1 · result | Existing signed v2 package and scope checks run in AP and BT. No frame codec or tamper run. |
| R3-10 | NOT_RUN · E1 · result | AP `test_current_rights_at_each_disclosure_boundary[<change>-handoff]` covers ten in-process changes with zero delivered packages and POSTs. No receiving-process plaintext observation. |
| R3-11 | FAIL · synthetic ordering diagnostic · base/result | `test_completed_revocation_order[after-decision]` observes approval → completed revoke → persisted fence → mock POST. No writer-wide serialization or distributed expiry proof. |
| R3-12 | FAIL · synthetic ordering diagnostic · base/result | Same case observes one package and one POST where zero POSTs are required. `[before-decision]` observes one package and zero POSTs. `[after-fence]` witnesses the other order. |
| R3-13 | NOT_RUN · E1 · result | Fixture uses fake local OAuth and Responses only. New PAS/runtime storage and diagnostics boundary absent. |
| R3-14 | REVIEW_REQUIRED · inspection and baseline POSIX control · base/result | `mark_send_started` remains the existing fence writer. BT `test_foreground_process_fence_survives_receipt_rollback` and AP `test_interrupted_stream_restart_and_older_local_state_retain_physical_fence` exercise retained fences. No R3 restore pass. |
| R3-15 | NOT_RUN · E1 · result | BT `test_foreground_process_fence_survives_receipt_rollback[race]` and AP `test_same_key_race_and_replay_keep_one_transport_and_opaque_foreign_status` are baseline controls only. |
| R3-16 | NOT_RUN · E1 · result | BT `test_foreground_send_uncertainty_survives_receipt_rollback` and AP interrupted-stream case cover baseline uncertainty with no second mock send. |
| R3-17 | REVIEW_REQUIRED · baseline installed SDK · base/result | HTTP `test_lost_create_and_continue_recover_under_original_binding[200]` and `[429]` use original-key canonical status/detail and one mock POST. R3 interruption unobserved. |
| R3-18 | NOT_RUN · E1 · result | No independent peer frame stream, ordering, bounds, terminal or EOF run. |
| R3-19 | NOT_RUN · E1 · result | Diagnostic withholds success after revoke. AP same-key replay denies after memory forget. No per-frame R3 result. |
| R3-20 | NOT_RUN · E1 · result | No transport lease, process partition or disconnect-drain witness. Local account and disconnect checks exercised only in baseline. |
| R3-21 | NOT_RUN · E2 · base/result | Three PostgreSQL nodes collected. No authorized disposable DSN. Exact nodes below. Joint restore and witness-write crash unobserved. |
| R3-22 | NOT_RUN · E1/E2 · result | Existing BT `[before_fence]` and `[after_fence]` worker kills protect local baseline. No PAS/runtime restart or witness/receipt joint restore. |
| R3-23 | NOT_RUN · E2 · base/result | Native DynamoDB conversation, message and branch; external domain/source and installation; PostgreSQL memory, consent, lifecycle and owner state unexecuted. No native caller journal restore. |
| R3-24 | REVIEW_REQUIRED · diff inspection · result | No migration or storage change. Retention/export/erasure review remains with storage owners. |
| R3-25 | NOT_RUN · E1 · result | No new handshake, frame, session, queue, slot or drain limits to measure or exercise. |
| R3-26 | NOT_RUN · E1 · result | HTTP `test_private_profile_denials_precede_protected_reads` and the foreign-owner control cover existing identity denials. No socket host/account substitution run. |
| R3-27 | REVIEW_REQUIRED · synthetic audit and trace · base/result | Numeric loopback only for installed-client cases, socket-free audit for ordering and broad suites. No external network or live provider calls observed. Separate DNS denial verifies the observer. No independent TLS peer trace. |
| R3-28 | REVIEW_REQUIRED · installed and baseline offline · base/result | Installed SDK 0.2.0 wheel and sdist, 0.1.0 automatic control, old-server denial, direct consumer contract, and source-free bridge cases exercised. Make-level inherited gates below. |
| R3-29 | REVIEW_REQUIRED · Git and startup inspection · result | No daemon, public listener, deployment or hosted/mobile/web execution added. E3 remains `NO_GO`. |
| R3-30 | REVIEW_REQUIRED · command and node log · base/result | See verification below. Failures and exclusions retain their original scope. |
| R3-31 | BLOCKED_EXTERNAL · external eligibility · result | Existing R0 eligibility matrix remains authoritative for its scope. R3-B, R4, Health eligibility and R7 MCP remain with their owners. No new provider readiness matrix. |
| R3-32 | REVIEW_REQUIRED · rollback inspection · result | Leave interprocess delivery unconfigured. Preserve existing owner rights, roots, witnesses, fences, receipts and caller journals as described below. |

The ten AP rights controls use the change suffixes `local-grant`, `onward-grant`, `source-revision`, `source-membership`, `memory-consent`, `memory-edit`, `memory-forget`, `owner-deletion`, `workspace-removal`, and `offline-witness` before `-handoff` or `-send-start`. The latter intercepts entry to `mark_send_started`, before the lock-held callback. The diagnostic adds the required post-decision interval.

## Verification and reproduction

The comparison used Debian 13 x86-64, Linux 6.18.57, overlayfs, CPython 3.12.14, uv 0.13.6, OpenSSL 3.5.7 and strace 6.13. PostgreSQL and DynamoDB engine versions are unobserved. Dependencies came from `backend/uv.lock` via `uv sync --locked --extra dev --group build` (exit 0). Setup initially tried `--group dev`, which exited 2 because dev is an extra. A first verification attempt lacked a writable uv cache and an SDK import path. The equivalent comparison uses an explicit temporary cache and `PYTHONPATH=sdk/python/src` for the broad suite.

Verification ran with `env -i`, `LITELLM_LOCAL_MODEL_COST_MAP=True`, `UV_OFFLINE=1` for builds, a writable disposable `UV_CACHE_DIR`, and `backend/.venv/bin` on `PATH`. Temporary credential fixtures were rooted under writable `/var/tmp` outside the repository. The restricted shell could not create a user/network namespace or write `/var/tmp`. The execution environment's approved command runner created a separate `unshare -Urn` namespace for each run. Socket-free cases left loopback down. Only installed HTTP cases brought up `lo`, with no other interface or IPv4/IPv6 default route. The default socket fence stayed intact.

| Command | Pinned base exit | Result exit | Observation |
| --- | --- | --- | --- |
| `make backend-lint` | 0 | 0 | Ruff passed. |
| `make naming-policy-check` | 2 | 2 | Two existing phase references in the R0 exit handoff. |
| `make sdk-install-check` | 0 | 0 | Client-only installation smoke passed for wheel and rebuilt sdist. |
| `make source-contract-check` | 2 | 2 | Planning and offline information-handling locked source identities drifted on both trees. |
| `make consumer-contract-check` | 2 | 2 | Builds and dependency inventory completed. Portable planning source identity stopped the target before the later contract and artifact checks. |
| `make hermetic-capability-check` | 2 | 2 | Socket fence, reasoning and orchestrator checks ran before `backend/tests/test_reasoning_grounded.py::test_sealed_evaluation` failed. Later dependencies of the target did not run. |
| `backend/.venv/bin/python backend/scripts/consumer_contract_check.py --check` | 0 | 0 | Direct consumer-contract check passed. |
| `git diff --check` and `git diff --cached --check` | 0 | 0 | Whitespace checks passed. |
| Broad offline selection below | 1 | 1 | 542 passed and three failed on each tree. |
| Foreground selection below | 0 | 0 | 37 passed and 121 deselected on each tree. |
| Rooted and permissions controls below | 1 | 1 | One passed, two failed and 179 deselected on each tree. |
| Ordering diagnostic below | 0 | 0 | Four diagnostic assertions passed on each tree. They reproduced the R3-11/R3-12 failure in the post-decision case. |
| Installed HTTP 0.2.0 wheel and sdist separately | 0 each | 0 each | Six passed and two deselected per artifact on each tree. |
| Installed HTTP 0.1.0 wheel | 0 | 0 | One passed and seven deselected on each tree. |
| Listener DNS denial control | 0 | 0 | One passed and exactly one deliberately denied DNS attempt on each tree. |
| PostgreSQL `--collect-only` below | 0 | 0 | Three collected and zero executed on each tree. No disposable DSN. |

The broad suite's initial permissions control used the executor's restrictive umask. Under that umask the test's requested mode `0755` was masked to a safe directory mode. The focused retry uses the predecessor's `umask 022`. The focused retry passed `test_unsafe_store_permissions_symlinks_and_corruption_fail_explicitly`. The two rooted v1 rollback tests, `test_rooted_v1_grant_keeps_fence_after_receipt_snapshot_restore` and `test_rooted_v1_grant_keeps_fence_after_receipt_only_rollback`, sign a proof one second in the future and failed with `InvalidDispatchGrant` before exercising the fence on both runs. These are observed baseline test limitations, with executable sources unchanged in the result. The paid-accounting gate remains the production composition's missing charge-receipt authority. A fake POST, local receipt or provider terminal establishes no request-specific payer or cost. [Current inference status](../../current-state.md) · [Source-free verification limits](2026-11-21-source-free-runtime.md)

Run from each tree's root. The broad `-rA` result reports the collected node IDs. Namespace and clean environment wrapping are described above.

```sh
export PYTHONPATH=sdk/python/src
backend/.venv/bin/python -B backend/scripts/offline_test_runner.py -q -rA \
  --basetemp "$scratch/offline" -m 'not loopback_http' sdk/python/tests \
  backend/tests/{test_application_plan_inference,test_shared_application_service,test_local_inference,test_chatgpt_bridge_transport,test_chatgpt_local_turn,test_isolated_inference,test_chatgpt_oauth,test_chatgpt_local_lifecycle,test_chatgpt_local_operator,test_external_execution_contracts,test_travel_context,test_research_routes,test_domains,test_booking_extractions,test_itinerary_proposals}.py
unset PYTHONPATH

umask 022
backend/.venv/bin/python -B backend/scripts/offline_test_runner.py -q -rA \
  --basetemp "$scratch/foreground" backend/tests/test_chatgpt_local_turn.py \
  backend/tests/test_chatgpt_bridge_transport.py -k 'policy_offer or foreground'
backend/.venv/bin/python -B backend/scripts/offline_test_runner.py -q -rA \
  --basetemp "$scratch/rooted" backend/tests/test_chatgpt_bridge_transport.py \
  backend/tests/test_chatgpt_local_lifecycle.py \
  -k 'test_rooted_v1_grant_keeps_fence or test_unsafe_store_permissions_symlinks_and_corruption_fail_explicitly'

backend/.venv/bin/python -B backend/scripts/offline_test_runner.py --collect-only -q \
  backend/tests/persistence/test_application_plan_postgres.py
```

The three collected native nodes, all `NOT_RUN`, are in `backend/tests/persistence/test_application_plan_postgres.py`.

- `test_native_ambiguous_plan_fence_and_owner_deletion_survive_restore_boundary`
- `test_worker_loss_after_native_claim_preserves_original_key_and_prevents_resend`
- `test_concurrent_native_claim_witnesses_survive_restore`

For HTTP, build from the 0.2.0 sdist with `uv build --wheel --no-build-isolation --python "$PWD/backend/.venv/bin/python" --out-dir "$scratch/rebuilt" sdk/python/dist/personal_ai_sdk-0.2.0.tar.gz`. Archive `sdk/python` at `f059b8223e441db40a0844017d610e9b32d0d8f0` and use the same wheel build flags for 0.1.0. Install each wheel in its own venv with `uv pip install --no-index --no-deps --python "$venv/bin/python" "$wheel"`. Set `APP_PLAN_SDK_VERSION` to the installed version and `SHARED_SERVICE_SDK_SITE` and `PYTHONPATH` to its site-packages. Bring up `lo` in the isolated namespace and verify it is the only interface and there are no default routes. Run the following with `select='not legacy_wheel and not external_dns'` for each 0.2.0 artifact and `select=legacy_wheel` for 0.1.0.

```sh
strace -f -qq -e trace=socket,connect,bind,sendto,sendmsg -o "$scratch/http.trace" \
  backend/.venv/bin/python -B backend/scripts/signed_http_checks.py -q -s -rA \
  --basetemp "$scratch/http" backend/tests/test_private_application_plan_http.py -k "$select"

# Use the 0.2.0 wheel environment for the listener's separate positive denial control.
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 backend/.venv/bin/python -B -m pytest \
  -p anyio.pytest_plugin -q -s -rA --basetemp "$scratch/dns" \
  backend/tests/test_private_application_plan_http.py::test_private_profile_listener_denies_external_dns
```

The 0.2.0 runs passed `test_installed_profile_three_contributions_and_foreign_owner`, `test_lost_create_and_continue_recover_under_original_binding[200]`, `test_lost_create_and_continue_recover_under_original_binding[429]`, `test_private_routes_absent_and_new_extension_refuses_old_server`, `test_private_profile_denials_precede_protected_reads` and `test_installed_profile_rejects_malformed_response_and_request`. The 0.1.0 control passed `test_legacy_wheel_retains_automatic_consumer_path`. The signed HTTP audit counters were zero unexpected attempts. Syscall traces for the six installed-client runs showed numeric loopback networking and zero off-loopback IP operations. The traced ordering diagnostic showed one failed `::1` bind from the IPv6 capability probe before collection and no IP connects or sends. The socket-free audit reported zero blocked attempts. No real OAuth, provider traffic, or spending was exercised.

### Ordering diagnostic

Save the following Python block as `$scratch/test_send_start_ordering.py`. It asserts the observed ordering to make the defect reproducible. Run it with all interfaces down and the scratch directory outside Git.

```sh
PYTHONPATH="$PWD/backend:$PWD/sdk/python/src" \
  backend/.venv/bin/python -B backend/scripts/offline_test_runner.py \
  -c backend/pyproject.toml -q -s -rA --basetemp "$scratch/test" \
  "$scratch/test_send_start_ordering.py"
```

The command reports `backend::test_completed_revocation_order` with `[before-decision]`, `[after-decision]`, `[after-fence]` and `[no-revoke]` in this pytest configuration. For syscall observation, prefix the runner with the same `strace -f -qq -e trace=socket,connect,bind,sendto,sendmsg` options used above.

```python
"""Diagnostic for the existing in-process fixture's send-start ordering."""

import httpx
import pytest

from tests.test_application_plan_inference import (
    confirmed,
    create,
    invalidate,
    plan_factory,
    plan_http,
    shared_factory,
    travel,
)


@pytest.mark.parametrize("edge", ["before-decision", "after-decision", "after-fence", "no-revoke"])
def test_completed_revocation_order(plan_factory, monkeypatch, edge):
    host = plan_factory()
    target = travel(host)
    conversation = create(host, target)
    body = confirmed(host, target, conversation)
    assert target.local_payloads == target.provider.sends() == []

    timeline = []

    def revoke():
        invalidate(host, target, "onward-grant")
        timeline.append("revoked")

    mark = target.store.mark_send_started

    def observe_decision(*args, authorize, **kwargs):
        def decide(state, registration):
            if edge == "before-decision":
                revoke()
            authorize(state, registration)
            timeline.append("allowed")

        return mark(*args, authorize=decide, **kwargs)

    persist = target.store._persist_send_fence

    def observe_fence(identity, receipt):
        assert target.store._read_send_fence(identity) is None
        if edge == "after-decision":
            revoke()
        persist(identity, receipt)
        assert target.store._read_send_fence(identity) is not None
        timeline.append("fenced")
        if edge == "after-fence":
            revoke()

    def handle(request):
        if request.method == "POST":
            timeline.append("mock-post")
        return target.provider.handle(request)

    monkeypatch.setattr(target.store, "mark_send_started", observe_decision)
    monkeypatch.setattr(target.store, "_persist_send_fence", observe_fence)
    monkeypatch.setattr(target.provider.provider, "transport", httpx.MockTransport(handle))
    response = plan_http(host, target, conversation, "continue", body)
    terminal = "event: response.completed" in response.text
    print(edge, timeline, len(target.local_payloads), len(target.provider.sends()), terminal)
    assert timeline == {
        "before-decision": ["revoked"],
        "after-decision": ["allowed", "revoked", "fenced", "mock-post"],
        "after-fence": ["allowed", "fenced", "revoked", "mock-post"],
        "no-revoke": ["allowed", "fenced", "mock-post"],
    }[edge]
    assert len(target.local_payloads) == 1
    assert len(target.provider.sends()) == (0 if edge == "before-decision" else 1)
    assert terminal == (edge == "no-revoke")
```

## Disable and recovery

The independent transport has no composition to enable, close or drain. Keep it unconfigured. Preserve existing grants and revocations, PAS roots and exact claims, independent generation and owner tombstones, runtime fences and mutable receipts, and caller journals under current retention controls. Keep ambiguous attempts on the original key and use authorized canonical status and detail to reconcile. If independent restore continuity is missing, quarantine the attempt. No new permission, key or empty recovery witness can settle an unknown send. Evaluate erasure of sensitive contents separately from retention of the minimal facts needed to prevent replay.

An independent review can replay the revocation barrier and compare the base/result range. Before interprocess delivery can open, a design must account for every current authority writer, the durable fence and bounded failure behavior across both processes. Kernel TLS observations, frame bounds, native split/joint restore, and the remaining interprocess cases depend on that design. Travel and Health retain domain-only defaults. Local SIWC requires separate app, host, license, account, model, included-allowance and receipt authorization. Partner hosting requires named custody and source-owner consent. Developer-paid APIs require separate project, budget and receipt authority. Production requires confidential delivery, recovery and IAM approval. [Eligibility matrix](../runtime-r0/R0-eligibility-matrix.md) · [External blockers](../runtime-r0/R0-external-blockers-and-questions.md)
