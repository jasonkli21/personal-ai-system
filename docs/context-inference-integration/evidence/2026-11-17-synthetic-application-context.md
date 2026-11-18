# Synthetic application context verification · 2026-11-17

**COMPLETE for the private hermetic implementation.**

This records the implementation session's historical maintainer authorization only. It is not an independent Stage 0 entry decision or independent Phase 1 acceptance. The independent prerequisite was not supplied; see the current [delivery gate](../delivery-and-acceptance.md) and [2026-11-18 remediation record](2026-11-18-synthetic-application-context-review-remediation.md).

## Entry decision

**ACCEPT for private hermetic implementation.** The project maintainer gave this decision in the implementation session on 2026-11-17 after the entry check reported that independent acceptance was absent at base `e7ff57e695f22d6d790fcee910a0178246f5daa9`. The maintainer authorized entry on that base. Independent review remains pending.

The acceptance covers two fixture installations, the frozen five-row suite, and the same-app mapping. The verified nullable actor belongs on `ContextPermissionDependency`, which uses the owning `source_scope`, matching `entity_ref` and `source_revision`, and trusted grant identity, revision/epoch, purpose and owner. The paired cross-app IDs are omitted. It also covers the bounded positive snapshot case with a separate manual-recipient grant and explicit digest confirmation, and the negative case that denies the entire snapshot when a second selected record has changed.

The patch adds the private source, authority, wire, provider and snapshot composition under `backend/tests/app_context_support/`, its acceptance suite, and scoped contract/status updates. The feature scope is hermetic. Production remains **NO_GO**. Live provider and OAuth calls, cloud smoke, native persistence, hosted operation, MCP, SIWC, and real recipient delivery were outside this verification. The exact review diff is the single commit that adds this record, relative to the base above. Recover it with `git show "$(git log -1 --diff-filter=A --format=%H -- docs/context-inference-integration/evidence/2026-11-17-synthetic-application-context.md)"`.

## Acceptance cases

Each test name below is in [the synthetic acceptance suite](../../../backend/tests/test_synthetic_application_context.py) unless otherwise specified. The fixture clock was `2030-01-02T09:00:00Z`.

| ID | Test evidence | Observed result |
| --- | --- | --- |
| AC-01 | `test_installs_without_grants_and_default_startup_has_no_synthetic_routes` | Two distinct revision-1 installations before seeding authority. Zero synthetic app, capability, or route registrations in the default app. |
| AC-02 | `test_verified_request_scope_and_same_email_subject_do_not_confer_authority` | Service-only, local, forged owner, body owner, and mismatched app credentials denied. Zero source exchanges. |
| AC-03 | `test_exact_owner_records_and_repeatable_wire_bytes`, `test_opaque_denials_hide_ungranted_workspace_and_absent_records` | Four matching record identities and typed projections across the authorized partitions. The fifth row contributed zero results. |
| AC-04 | `test_verified_request_scope_and_same_email_subject_do_not_confer_authority` | Same-email foreign subject and mismatched issuer denied with zero source exchanges. |
| AC-05 | `test_wrong_authority_denies_without_foreign_lookup`, `test_opaque_denials_hide_ungranted_workspace_and_absent_records`, `test_title_requires_its_own_grant_but_other_fields_can_be_fetched` | Tuple and authority mismatches yielded zero data lookups. Absent and unauthorized wire errors carried only the same opaque error code and a correlation ID. |
| AC-06 | `test_operator_mutations_are_revision_checked_and_atomic`, `test_installs_without_grants_and_default_startup_has_no_synthetic_routes` | Data-principal mutation count stayed zero, one of two simultaneous updates advanced the revision, and disable denied subsequent reads. |
| AC-07 | `test_delegation_claims_are_verified_before_lookup`, `test_single_use_nonce_is_atomic_and_signature_is_required` | Invalid credentials and claims produced zero lookups. Concurrent replay produced one successful lookup and one denial. |
| AC-08 | `test_cursor_search_order_literal_visibility_and_turn_limits`, `test_source_search_cannot_emit_an_oversized_page`, `test_response_transport_cap_precedes_decoding_and_sizes_failed_calls` | Stable sort, literal filtering, titles admitted before pagination, a one-page turn, ten exact fetches, and early raw byte caps. Oversized pages yielded zero disclosed results. |
| AC-09 | `test_cursor_reauthorized_before_stale_hints` | Authorized watermark, grant epoch, policy and expiry changes returned stale. Changed owner, query or cursor handle returned unavailable. Stale exact fetch had zero payload lookups. |
| AC-10 | `test_transport_caps_before_decode_and_rejects_malformed_bytes`, `test_signed_requests_reject_types_unknown_fields_and_query_overflow`, `test_identifier_must_round_trip_through_context_bounds_before_fetch`, `test_source_response_is_bound_to_exact_request_and_verified_metadata`, `test_expiry_is_the_earliest_source_ttl_record_installation_or_grant` | Strict request and response parsing, substituted envelopes, unrepresentable IDs and invalid intervals denied. Each of the four expiry dependencies capped disclosure in its own case. |
| AC-11 | `test_context_item_keeps_exact_same_app_dependency_and_typed_payload`, `test_classification_ceilings_are_independent` | Real validators and serialization retained exact source/version/record identity, complete field labels and trusted permission metadata. Installation, grant and application ceilings each denied independently. |
| AC-12 | `test_context_assembly_renders_only_allowed_data_and_manifest`, `test_source_text_remains_in_the_rendered_payload_data_field`, `test_source_budget_exhaustion_preserves_required_conversation`, `test_deadline_and_failed_attempts_share_the_turn_budget`, `test_failed_second_source_read_discards_earlier_result_without_fallback` | Actual model input and manifest observed for both applications. Required conversation survived optional budget exhaustion. Source text stayed in the rendered data field. A second failed read discarded the earlier projection with zero fallback source calls. |
| AC-13 | `test_after_read_revocation_or_source_change_blocks_disclosure`, `test_final_context_disclosure_revalidates_permissions` | Grant, membership, installation or revision changes prevented disclosure. Revocation at the builder boundary omitted the item as `permission_revoked`. |
| AC-14 | `test_snapshot_requires_a_separate_grant_and_confirms_once_with_redacted_fields`, `test_snapshot_confirmation_changes_invalidate_entire_preview`, `test_concurrent_snapshot_confirmation_returns_one_ordered_snapshot` | Runtime authority made zero fetches for the snapshot. The separate grant produced a redacted preview and one typed confirmation with a count-only receipt. A stale second record left three combined preview/confirmation fetch lookups and zero receipts or returned records. |
| AC-15 | `test_exact_owner_records_and_repeatable_wire_bytes`, `test_cursor_search_order_literal_visibility_and_turn_limits`, `test_context_item_keeps_exact_same_app_dependency_and_typed_payload` | Fresh delegations returned byte-identical successful projections and pages at fixed state, and owner-specific item identifiers never collided. |
| AC-16 | `side_effect_fence` across the suite and `test_installs_without_grants_and_default_startup_has_no_synthetic_routes` | Zero network, model, provider-send, billing or durable-memory calls and zero synthetic registrations in default startup. |
| AC-17 | [Application context contract](../application-context-contract.md) and [delivery gate](../delivery-and-acceptance.md), with the context and snapshot witnesses above | Executable same-app mapping and bounded snapshot behavior documented, including maintainer decision and pending independent review. |
| AC-18 | Focused context provider, authorization, builder, planner, application and auth suites, with the offline gate below | 231 focused passes, including 118 new synthetic cases. Broader gate status is recorded below. |

The suite records registry, PAS membership, grant, source membership and version checks separately from search/fetch payload lookups. Invalid authority, absent or hidden records, and unauthorized recipients had zero payload lookups in their denial witnesses. The fixture does not measure latency indistinguishability or a live atomic check-to-wire guarantee.

## Commands and outcomes

Run from the repository root with the backend virtual environment active, except where the command explicitly enters `backend`.

| Check | Exit and observation |
| --- | --- |
| `cd backend && python -m pytest -q --tb=short tests/test_synthetic_application_context.py tests/test_context_provider.py tests/test_context_authorization.py tests/test_context_builder.py tests/test_context_planner.py tests/test_auth.py tests/test_applications.py tests/test_application_scope.py` | 0. 231 passed. The three dependency warnings concern Python support and Starlette's HTTP test client. |
| `make backend-lint` | 0. |
| `make backend-test-offline` | 2 on initial run and on the archived base. Collection of the existing HTTP consumer test needed the SDK source on `PYTHONPATH`. |
| `PYTHONPATH=../sdk/python/src:../examples/project-checklist/client/src:../examples/project-checklist/host/src make backend-test-offline` | 0 with loopback socket access. 3,501 passed, one installed-only standalone probe skipped, and 204 deselected. The restricted run exited 2 with 11 failures and 92 errors at loopback socket binding. The archived base reproduced the binding error in the application lifecycle and signed information-handling fixtures. |
| `make naming-policy-check` | 2 in the working tree. The checker returned 1 with eleven findings reproduced on the archived base plus the same pre-existing untracked roadmap and handoff. Three flags concern the handoff filenames and eight concern phase labels in those files and the roadmap. The same Make target passed on an archived base with only the scoped patch overlaid. The five unit tests passed separately with `backend/.venv/bin/python -I -m unittest discover -s backend/scripts -p test_naming_policy_check.py`. |
| `make source-contract-check` | 0. Portable source passed for planning baseline v39 and offline source manifest generation 13. Strict historical runtime replay and installed native capability were unrun. |
| `git diff --check` and `git diff --cached --check` | 0 for both working and staged changes. |

Updated Markdown links resolved and all JSON examples in the application context contract parsed as strict JSON.
