# Private application inference verification

21 November 2026. The maintainer explicitly authorized implementation without the pending independent entry re-review. The base was `f059b8223e441db40a0844017d610e9b32d0d8f0` with a clean checkout at the remote main revision. Searches of the tracked history and repository issues and pull requests found no later combined E1 decision for R1, R2, R4 and R5. The waiver permits delivery of the private profile. Independent E1 acceptance remains unverified, R3 remains an E2 witness finding, and E3 remains `NO_GO`.

The supplied reconstructed implementation prompt and plan have SHA-256 digests `0965a9c2f7f7001d73c9736f81e4bc2e5a32595f4ec460acd2422f486f8827f9` and `47e8c5952a3fcd547e6dac79856b97e313bc2034a324431b78caee0ba50a33a3`. Their base, predecessor and repair revisions agreed with Git. The original handoffs and separate review prompt were unavailable. The [machine ledger](2026-11-21-private-application-inference.json) records all fourteen design obligations with witness names, outcomes and observations.

## Result and scope

The result revision is the commit introducing this report. The implementation replaces header-matched fixture routes and the SDK opener override with an explicit isolated host adapter and SDK 0.2.0. The adapter adds only the versioned preview and continue paths. It shares the consumer identity middleware, application-client and workspace checks, request body ceiling, chat assembly, SSE framing, canonical create/status/detail, permission rechecks and durable worker lifecycle. Fixture authority, pairing, transport and credentials remain synthetic test inputs. [Private contract](../../platform-independence/private-application-inference-v1.md) · [Isolated adapter](../../../backend/src/personal_ai/api/private_application_plan.py)

```sh
base=f059b8223e441db40a0844017d610e9b32d0d8f0
report=docs/context-inference-integration/evidence/2026-11-21-private-application-inference.md
result="$(git log -1 --diff-filter=A --format=%H -- "$report")"
git log --oneline "$base..$result"
git diff --check "$base" "$result"
git show --stat "$result"
```

Both the independently installed wheel and the sdist-built wheel ran the same five socket tests. The positive test exercised two owners, three app contributions and a same-app foreign owner. Per distribution there were three authorized previews, each with one search and one fetch, three releases, three fake Responses sends across three approved turns, zero foreign releases or sends, and no additional source exchange or send for completed replay. The denial fixture kept its exact source counters unchanged under malformed, forwarded, unauthenticated, workspace and client-policy substitutions. The journal test recovered one conversation after losing the create response, then reconciled a lost continue response by status and detail with one physical fake send. The socket audit fence admitted only its assigned numeric listener and denied the explicit external DNS attempt before resolution. [Socket tests](../../../backend/tests/test_private_application_plan_http.py)

The older wheel completed an ordinary automatic turn against the updated host. The new SDK received one unavailable response from the old route map, including a run against the actual pinned base server and performed zero fallback POSTs. The pinned dispatch reader is `f391c0563cfd0336c839fbe4f4e39af710c5cffb:backend/src/personal_ai/auth/dispatch_grants.py`, blob `9cae4d574f3fcb2b1e53d408d67bafaec917fe33`. A synthetic v1 vector produced identical canonical bytes in both readers with SHA-256 `072dd31c35b7b9971340c60ee144a2dc9829f49603ee10b9d1999a2c0dc10582`. The old reader rejected v2 at the version and new-field checks. The exact vector used `synthetic-pas`, `synthetic-key`, the UUID ending in `0001` for all identities, an all-`a` 64-character package hash, `synthetic-provider`, `synthetic-model`, `synthetic-policy`, `personal`, issued at 1 and expiring at 50.

| SDK input | SHA-256 |
| --- | --- |
| 0.1.0 wheel at the base | `51613a46932a7a56c9a4158996e5cdafd6e6bc766b38ca0083b05a52cb150c4c` |
| 0.2.0 wheel | `ebb6a4eb1a293ab501b70c88d80f4b0a0db4baabb5e2c5b0f58283a0c10c2b5d` |
| 0.2.0 sdist | `051d2d1b7be144fda2cb9546ad24fc6b1ceba27dfee4ecc1fb65713478f2bc32` |

The wheel and sdist probes loaded `personal_ai_sdk/__init__.py` from their own `wheel/lib/python3.12/site-packages` and `sdist/lib/python3.12/site-packages` environments under the disposable install directory. The old wheel loaded from a third `lib/python3.12/site-packages` environment. Each import resolved to its installed environment.

## Reproduction and review

Use the locked backend environment and Python 3.12.14 for the recorded comparison. Run the Makefile checks in clean checkouts with full Git history. The base and candidate use the same tool and dependency versions. For the socket suite install the 0.2.0 wheel and an independently built wheel from the 0.2.0 sdist in two temporary environments with `uv pip install --no-index --no-deps`. Rebuild from the pinned base for the 0.1.0 control. The synthetic socket cases need an isolated temp directory outside Git trees. The permissions fixture uses `umask 022`. The workspace runner required approved local execution to avoid artificial Git markers in its temporary directories.

```sh
umask 022
make sdk-install-check
make backend-lint
make naming-policy-check
make source-contract-check
make consumer-contract-check
make hermetic-capability-check
backend/.venv/bin/python backend/scripts/consumer_contract_check.py --check
backend/.venv/bin/python -m unittest discover -s backend/scripts -p test_release_artifacts.py
git diff --check

# Set sdk_site to the selected installed environment's site-packages directory.
# Use the old wheel with APP_PLAN_SDK_VERSION=0.1.0 and -k legacy_wheel.
SHARED_SERVICE_SDK_SITE="$sdk_site" PYTHONPATH="$sdk_site" APP_PLAN_SDK_VERSION=0.2.0 \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 backend/.venv/bin/python -B -m pytest \
  -p anyio.pytest_plugin -s -q --basetemp="$isolated_tmp/socket" \
  backend/tests/test_private_application_plan_http.py -k 'not legacy_wheel'

SHARED_SERVICE_SDK_SITE="$sdk_site" \
  PYTHONPATH="$sdk_site:examples/project-checklist/client/src:examples/project-checklist/host/src" \
  backend/.venv/bin/python -B backend/scripts/offline_test_runner.py \
  --basetemp="$isolated_tmp/offline" -q -m 'not loopback_http' sdk/python/tests \
  backend/tests/{test_application_plan_inference,test_shared_application_service,test_local_inference,test_chatgpt_bridge_transport,test_isolated_inference,test_chatgpt_oauth,test_chatgpt_local_lifecycle,test_travel_context,test_research_routes,test_domains,test_booking_extractions,test_itinerary_proposals}.py
```

| Check | Pinned base | Result |
| --- | --- | --- |
| `make sdk-install-check` | Exit 0, 0.1.0 wheel and sdist. | Exit 0, 0.2.0 wheel and sdist. |
| `make backend-lint` and `git diff --check` | Both exit 0. | Both exit 0. |
| `make naming-policy-check` | Exit 2 on the unavailable combined-review link in current state. | Exit 0 with the current evidence linked. |
| `make source-contract-check` | Exit 2 on planning and offline information handling source drift. | Exit 2. The new private adapter and admission changes also require source-identity review. |
| `make consumer-contract-check` | Exit 2 at the portable planning source-identity check. | Exit 2 at the same check. The direct static contract probe exited 0. |
| `make hermetic-capability-check` | Exit 2 at `adaptive_conformance_source_changed` in the clean comparison. An earlier baseline run stopped in the grounded sealed evaluation. | Exit 2 at `adaptive_conformance_source_changed`. |
| Installed SDK offline regressions | 474 passed, zero blocked network attempts. | 476 passed, zero blocked network attempts. |
| Private loopback suite | New client refusal against the pinned host passed the compatibility control. | Five passes per candidate distribution, plus one old-wheel control pass. |
| Application plan PostgreSQL module | Three collected and skipped. | Three collected and skipped. No isolated DSN was configured. |

The native cases concern PostgreSQL routing roots and owner tombstones, an independent worker process, and the separate claim witness. The local file fence exercised by E1 leaves native multi-store recovery unverified. Paid-accounting mismatch evidence remains separately attributable to the pinned base. The check suite issued no real provider requests, credential exchanges, billing operations, deployment or package publication.

A separate reviewer can reproduce the exact range above and inspect the machine ledger, authorization changes, no-fallback controls, and provider and output counters. On rollback, disable the private composition and preserve unknown receipts, routing roots, claim witnesses, revocation epochs and caller journals. The earlier Phase 5 and 5.5 combined verdict is unchanged.
