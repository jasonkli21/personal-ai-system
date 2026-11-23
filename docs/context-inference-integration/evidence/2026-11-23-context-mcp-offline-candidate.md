# Offline context MCP candidate · 2026-11-23

## Provenance and disposition

PAS checkout `/workspace/personal-ai-system` started clean on `work`, at
`07b43ece590634ecc290ee8ba2b5a99763206f30`. Local `FETCH_HEAD` records the same
commit. The checkout has no local or remote-tracking `main` ref. Read-only
`git ls-remote origin refs/heads/main` exited 128 because the configured proxy
was unreachable. Current remote ancestry remains **BLOCKED**. The candidate is
an uncommitted working-tree change over the pinned commit. A temporary Git
index produced tree `1c41960753265dc1f3446a6927ab8c2abe499007` for the candidate
before adding this evidence file.

The offline target is MCP SDK and MCP Types `2.3.0`, stateless Streamable HTTP
`2026-07-28`, Python 3.12, in-process ASGI, a signed test issuer, and one adapter
composition with process-local selector, rate and citation tables. The
[existing lock](../../../adapters/mcp_source/requirements-macos-arm64-py312.txt)
has SHA-256 `c1e16280bdb1e18c8a373d93d6ba1d6f76285b0909abe27142743d015dcaed64`
and targets macOS ARM64. This workspace is Linux x86_64 with CPython 3.12.14 and
an unrelated global MCP 1.29.0. The code and fixtures are ready for independent
inspection. **Withhold release acceptance.**

The [November 18 remediation](2026-11-18-synthetic-context-mcp-independent-remediation.md)
reported 99 maintainer source passes, 99 maintainer wheel passes, and 44 inbound
adapter passes on macOS. Baseline independent E1 acceptance is open. MCP2-001
physical cancellation is blocked for the synchronous transport. MCP2-002
hosted macOS CI remains unverified. MCP2-003–006 keep their historical local
dispositions. Stage 0 and aggregate R-03 remain open. This report records a
separate candidate run and adds no external admission.

## Author verification

| Command | Exit and observation |
| --- | --- |
| `make mcp-context-check` | 2. The configured optional adapter interpreter is absent. |
| `make mcp-adapter-check` | 2. The configured optional adapter interpreter is absent. |
| `uv --no-cache pip install --offline --dry-run --python "$(command -v python3.12)" --require-hashes -r adapters/mcp_source/requirements-macos-arm64-py312.txt` | 1. Exact lock resolution stopped because `anyio==4.15.1` is uncached. |
| `backend/.venv/bin/python -m ruff check adapters/mcp_context` | 127. The backend interpreter is absent. |
| `make backend-lint` | 2. Ruff is unavailable in the global interpreter. |
| `make naming-policy-check PLATFORM_PYTHON=python3.12` | 2. Two existing `Phase 6` text violations in the runtime handoff document. A clean pinned archive produced identical checker output. |
| `python3.12 -I -m unittest discover -s backend/scripts -p test_naming_policy_check.py` | 0. Five tests passed and zero skipped. |
| `make source-contract-check PLATFORM_PYTHON=python3.12` | 2. Planning and offline benchmark source identities differ from the existing locks. A clean pinned archive checked with the original Git ancestry produced identical output. |
| `make hermetic-capability-check` | 2. Its first target could not start without the backend interpreter. |
| `UV_NO_CACHE=1 UV_OFFLINE=1 make sdk-install-check` | 2. The SDK build could not start without the backend interpreter. |
| `env -i PATH="$PATH" LITELLM_LOCAL_MODEL_COST_MAP=True PYTHONPATH=backend/src python3.12 backend/scripts/consumer_contract_check.py --check` | 1. The fallback interpreter lacks the Google backend dependency. |
| `uv --no-cache build --offline --no-build-isolation --python adapters/mcp_source/.venv/bin/python --wheel --out-dir /tmp/pas-mcp-context-wheels adapters/mcp_context` | 2. The configured interpreter is absent. The same offline build with global Python exited 2 because Hatchling is absent. Clean target install, import-path verification and the installed-wheel suite remain blocked. |
| `python3.12 -m compileall -q adapters/mcp_context` | 0. All changed Python files compiled. |
| `git diff --cached --check HEAD` using the temporary candidate index | 0. Includes newly added paths, with the checkout index left intact. |

An inline, network-fenced CPython 3.12 source-fixture probe exited 0. It observed
six protected Travel reads across two tenants and two grants for one owner,
one acknowledged source cancellation before its first lookup, seven fixture
entries and exits, zero active work at completion and zero IP network attempts.
It also checked that Fitness resolves a required workspace. This probe bypassed
MCP and ran with the global Pydantic build. It observes fixture behavior within
that scope. A separate exploratory thread-backed probe exceeded its test
timeout on this sandbox, including during asyncio executor shutdown. No
threaded source or locked transport result is inferred from these probes.

Locked E1 pass/skip counts, source counters, release bytes and network attempts
are **UNOBSERVED** because the source and wheel suites did not reach collection.
The runner in the existing Make target denies Python network access. Its local
suite must run against an unchanged lock to produce E1 observations.

## Acceptance matrix

The following matrix preserves the original candidate dispositions. The author
E1 source and wheel suite statuses for its collected witnesses are superseded by
the remediation follow-up below; independent E1 acceptance and every external
tier remain open.

File prefixes are `server` for `adapters/mcp_context/tests/test_context_server.py`,
`profiles` for `adapters/mcp_context/tests/test_context_profiles.py`, and `work`
for `adapters/mcp_context/tests/test_context_work.py`. Entries identify the
author's intended witness and expected observation. Each E1 witness below
requires `make mcp-context-check` against source and the isolated wheel, exit
0, plus independent reproduction. Both candidate runs are **BLOCKED** as
recorded above.

| ID | Packet and tier | Witness, expected observation and current status |
| --- | --- | --- |
| R7-01 | A · documentary | Local base and lock pin and seven packet documents inspected. Remote head and baseline independent acceptance remain **BLOCKED**. |
| R7-02 | A · E1 | `server::test_factory_requires_explicit_test_mode_and_dependencies` and `backend/tests/test_synthetic_application_context.py::test_default_startup_has_no_optional_mcp_and_no_side_effects`. Expect no optional imports, tool routes or model, provider, payer or memory calls at normal startup. **BLOCKED**. |
| R7-03 | A · E1 | `server::test_real_sdk_search_and_exact_fetch`, `test_stateless_discovery_and_direct_calls` and `test_malformed_tool_envelopes_never_resolve_source_authority`. Exact headers and revision, with zero source authority resolutions for malformed tool calls. **BLOCKED**. |
| R7-04 | A · E1 | `server::test_stateless_discovery_and_direct_calls` and `test_real_sdk_search_and_exact_fetch`. Two read-only tools, matching schemas, OAuth metadata and tool-only capabilities. **BLOCKED**. |
| R7-05 | A · E1 | `server::test_tool_input_rejected_before_authoritative_lookup`, `test_frame_limits_utf8_and_duplicate_keys`, `test_duplicate_control_headers_are_rejected_before_source_lookup`, and `test_malformed_tool_envelopes_never_resolve_source_authority`. Expect zero protected reads. **BLOCKED**. |
| R7-06 | A · E1 and E3 | `server::test_protocol_and_origin_denials_are_prelookup`, `test_alias_paths_cannot_reach_the_protected_resource` and `test_direct_http_is_rejected` with forwarded spoof. E1 **BLOCKED**. Public TLS and trusted ingress E3 **NO_GO**. |
| R7-07 | A · E1 | `server::test_serialized_tool_result_limit_counts_both_representations_and_utf8`, `test_search_returns_one_bounded_page_without_a_cursor_or_total`, `profiles::test_citation_output_byte_overflow_releases_no_handle_or_browser_locator`. Expect one read, at most ten hits and at most 8,192 bytes for the full tool result. **BLOCKED**. |
| R7-08 | D · E1 | `server::test_real_sdk_search_and_exact_fetch` and `profiles::test_citation_profile_uses_exact_audience_and_sdk_shapes`. Default URL-free schema and distinct citable resource, audience and schema. **BLOCKED**. |
| R7-09 | A · documentary and E1 | `server::test_rfc_resource_metadata_and_synthetic_issuer_discovery`. Resource metadata belongs to PAS and OAuth issuer endpoints to the authorization server. E1 **BLOCKED**. |
| R7-10 | A · E1 and E2-I | Static issuer metadata names PKCE S256. The full code exchange and redirect, mix-up, resource binding, logout and callback-mode behavior have no new observations. E1 metadata **BLOCKED**, installed OAuth **BLOCKED_UNVERIFIED**. |
| R7-11 | A · E1 | `server::test_oauth_rejected_before_frame_or_source_lookup`. Invalid human access or claim deny with 401 and zero protected reads. **BLOCKED**. |
| R7-12 | A · E1 | `server::test_oauth_rejected_before_frame_or_source_lookup`, `test_authorities_revalidated_between_read_and_release` and `test_rfc_resource_metadata_and_synthetic_issuer_discovery`. Scope challenge and public metadata without source disclosure. **BLOCKED**. |
| R7-13 | B · E1 | `server::test_only_explicit_current_mcp_recipient_receives_content` and `profiles::test_wrong_workspace_policy_or_account_denies_before_domain_read`. Same email is insufficient, and unmapped, ambiguous or crossed accounts result in zero protected reads. **BLOCKED**. |
| R7-14 | B · E1 | Same two witnesses. Only the exact MCP recipient, purpose, installation and current grant admit a read. **BLOCKED**. |
| R7-15 | B · E1 and E2-N | `server::test_authorities_revalidated_between_read_and_release` and `profiles::test_workspace_less_authority_changes_after_one_read_withhold_results_and_publication`. Expect one charged attempt with zero released records and zero newly published selectors. E1 **BLOCKED**, native revocation **NOT RUN**. |
| R7-16 | A · E1 and E2-I | `server::test_oauth_rejected_before_frame_or_source_lookup` and `profiles::test_wrong_workspace_policy_or_account_denies_before_domain_read`. Client credentials and forwarded identity cannot supply human/domain authority. E1 **BLOCKED**, installed client identity **BLOCKED_UNVERIFIED**. |
| R7-17 | B · E1 | `profiles::test_workspace_less_travel_uses_exact_record_grants_and_fitness_keeps_workspace` and `test_wrong_workspace_policy_or_account_denies_before_domain_read`. Explicit null only on the registered Travel installation, with exact owner/trip ACL. Locked E1 **BLOCKED**. |
| R7-18 | B · E1 | Same profile tests. Exact required Fitness workspace and isolation of app, tenant and source grants. **BLOCKED**. |
| R7-19 | B · E1 and E2-N | `profiles::test_workspace_less_authority_changes_after_one_read_withhold_results_and_publication` and `server::test_stale_selector_denied_before_or_after_exact_read`. Revision, watermark, ACL, expiry and field changes deny. E1 **BLOCKED**, native **NOT RUN**. |
| R7-20 | B · E1 | `profiles::test_workspace_less_travel_uses_exact_record_grants_and_fitness_keeps_workspace`. Same empty projection for unauthorized, cross-tenant and absent records. **BLOCKED**. Timing comparisons **UNOBSERVED**. |
| R7-21 | B · E1 | `server::test_untrusted_source_content_stays_in_the_authorized_projection` and the workspace-less typed projection tests. Content remains data and fields stay allowlisted. **BLOCKED**. |
| R7-22 | B · E1 gate | `profiles::test_wrong_workspace_policy_or_account_denies_before_domain_read`. No Health source or substitution via preview/federation. E1 negative fixtures **BLOCKED**. Sensitive-data source admission remains **BLOCKED**. |
| R7-23 | B · E1 | `profiles::test_wrong_workspace_policy_or_account_denies_before_domain_read` and `server::test_failed_source_attempt_consumes_budget_and_never_retries`. Ambiguity reads zero records and a failed attempt consumes one charge. **BLOCKED**. |
| R7-24 | C · E1 | `server::test_handle_cannot_cross_user_client_or_application_and_refresh_uses_current_authority` and `test_stale_selector_denied_before_or_after_exact_read`. Opaque scoped handle and at most 60-second validity. **BLOCKED**. |
| R7-25 | C · E1 and E2-N | `profiles::test_process_local_selectors_miss_in_second_running_app`. A second app instance misses without reading, and process_count greater than one is denied. E1 **BLOCKED**, reviewed multi-instance continuity **NOT RUN**. |
| R7-26 | C · E1 and E2-N | `server::test_handle_cannot_cross_user_client_or_application_and_refresh_uses_current_authority` and `test_stale_selector_denied_before_or_after_exact_read`. Current exact binding and revision required. E1 **BLOCKED**, native restore/replay **NOT RUN**. |
| R7-27 | D · E1 | `profiles::test_citation_profile_uses_exact_audience_and_sdk_shapes` and `test_browser_reauthenticates_and_checks_current_citation_grant`. Search and fetch share an HTTPS URL and the approved browser sees the title and text. **BLOCKED**. |
| R7-28 | D · E1 and E2-I | `profiles::test_browser_reauthenticates_and_checks_current_citation_grant` and `test_browser_change_during_open_or_expired_locator_denies`. Denial releases zero bytes for missing session, guessed URL, crossed tenant, stale dependencies and revocation. E1 **BLOCKED**, installed browser click **BLOCKED_UNVERIFIED**. |
| R7-29 | D · E1 | `profiles::test_browser_reauthenticates_and_checks_current_citation_grant`. Fixed origin/path, no query or redirect, private no-store and no-referrer. Synthetic log/URL negative counters **UNOBSERVED**. **BLOCKED**. |
| R7-30 | D · E2-I | Real OAuth, discovery, search/fetch and citation click/revoke per installed mode with separate authorization. **BLOCKED_UNVERIFIED**. |
| R7-31 | D · E1 | `server::test_real_sdk_search_and_exact_fetch`, `test_stale_selector_denied_before_or_after_exact_read`, and `profiles::test_citation_profile_uses_exact_audience_and_sdk_shapes`. Exact prior revision, watermark and title, with authorized typed fields and bounded response. **BLOCKED**. |
| R7-32 | C · E1 | `work::test_timed_out_synchronous_exchanges_keep_eight_worker_slots_until_exit` and `test_cancellable_source_acknowledges_cleanup_before_timeout_response`. Deadline, no late bytes/publication and acknowledged cleanup for the async fixture each **BLOCKED** pending execution. Forced termination of the legacy sync transport remains independently **BLOCKED**. |
| R7-33 | C · E1 | The same synchronous work witness and `server::test_per_principal_rate_includes_failures_and_survives_client_change`, `test_unlinked_subject_churn_does_not_consume_linked_rate_buckets` and `test_selector_table_eviction_and_restart_invalidate_handles`. Eight physical slots, ninth denied, recovered progress and bounded linked-subject/selector tables. **BLOCKED**. |
| R7-34 | C · E1 and E2-N | `server::test_selector_table_eviction_and_restart_invalidate_handles`, `test_stale_selector_denied_before_or_after_exact_read`, and `profiles::test_process_local_selectors_miss_in_second_running_app`. E1 **BLOCKED**, native kill/restore/rolling operation **NOT RUN**. |
| R7-35 | C · E1 | Suite-wide `side_effect_fence` and offline runner cover zero network, provider, model, billing and memory effects. The tool list permits read operations only. **BLOCKED**. |
| R7-36 | A · E1 | Default-startup test, `make mcp-adapter-check`, SDK install, consumer contract and hermetic capability checks. **BLOCKED**. |
| R7-37 | A · isolation | Diff scope is the optional adapter, its tests and read-direction documentation. Source-contract failure reproduced at the pinned base and was left for the shared contract owner. Integrated shared-capability comparison **NOT RUN**. |
| R7-38 | E · E2-I and E3 | Separate approval for a real issuer and client, private HTTPS, test owners, exact source and non-sensitive data, click and revocation. E2-I **BLOCKED_UNVERIFIED**, E3 **NO_GO**. |
| R7-39 | E · E3 | Production privacy, consent, tenant isolation, audit, retention, erasure, secret rotation, rollback, canary and incident ownership require operator and source-owner sign-off. **NO_GO**. |
| R7-40 | E · evidence | Author record and row mapping prepared. Exact result commit, locked source/wheel and native/installed/production receipts and independent dispositions remain open. |

## Independent review and rollback

Reproduce the source and wheel suites independently at the reviewed result
SHA using the November 18 commands and verify that Python imports the wheel
from its clean target. Record the resolved SDK version, observed read, byte,
selector, work-exit, network and skip counts for each applicable row. Route
observed discrepancies to the owning packet with the smallest failing fixture
and exact revision. Record independent closure separately.

Rollback is disabling citation composition or the entire optional adapter.
Revoke the relevant connections and grants and invalidate the process-local
bindings on restart. Rehearse live ingress, cache and revoke behavior only
under separately approved operator work. The report records no client
registration, deployment, live source, provider call or real credentials.

## Remediation follow-up · 2026-11-23

Reviewed candidate base: `016a2ea249c220d533a2a0450781f7be28401fb3`.
Author remediation result: `78b3e841d860766383b94a6a04d95c0a1a25e8e1`.

The author remediation fixes the two independent-review source and wheel failures:
the citation SDK test now creates a fresh app for each one-shot MCP session
manager lifespan, and the eight-worker saturation witness waits asynchronously
without consuming a thread-pool slot. Its fixture gives the event loop nine
executor workers so eight real synchronous source operations can reach the
barrier; the production and assertion cap remains eight.

Workspace-less `SourceInstallation` registration now includes the tenant in its
exact identity. A same-app/source/installation registration for tenant A denies
tenant B before any protected Travel lookup. Linked-subject rate admission now
occurs after current binding resolution at MCP tool entry. A binding change
after that point cannot erase its charge. Authenticated citation browser reads
share the same issuer/subject budget and are charged after principal ownership
and current-binding checks, before protected reads. Browser denial on exhaustion
returns HTTP 429 with no body. Existing 8,192-byte serialization and per-read
budget checks remain in force for both projections.

| Command | Exit and observation |
| --- | --- |
| `/tmp/r7env/bin/python -m ruff check adapters/mcp_context` | 0. All checks passed. |
| `make mcp-context-check MCP_ADAPTER_PYTHON=/tmp/r7env/bin/python` | 0. 139 passed; 0 blocked network attempts. Linux x86_64, CPython 3.12.14, locked MCP 2.3.0 environment. |
| Offline wheel build, isolated target install, then `make mcp-context-check MCP_CONTEXT_IMPORT_PATH=/tmp/r7remediation-installed:backend/src MCP_ADAPTER_PYTHON=/tmp/r7env/bin/python` | 0. 139 passed; 0 blocked network attempts; tests imported the installed wheel. |
| `make mcp-adapter-check MCP_ADAPTER_PYTHON=/tmp/r7env/bin/python` | 2. 11 failed, 33 passed. An archive of pinned base `07b43ece590634ecc290ee8ba2b5a99763206f30` reproduced the same 11 failures and 33 passes. The `/tmp` trust checks reject pytest temporary directories and the `/tmp/r7env` Python executable. The inbound adapter is unchanged. |

These are author-run Linux offline E1 observations only. Independent acceptance,
hosted macOS CI, Stage 0 and R-03 remain open. E2-N remains **NOT RUN**, E2-I
remains **BLOCKED_UNVERIFIED**, and E3 remains **NO_GO**. No remote write was
performed.
