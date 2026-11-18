# Synthetic context over MCP · 2026-11-18

**E1 implemented, awaiting independent acceptance.** Installed-client E2 is
`BLOCKED_UNVERIFIED`. Production E3 is `NO_GO`.

The base was `c1500ce9be41a789131ef1fca323e9d97bdf11fe` on `main`, which
matched GitHub. The historical candidate was
`50bff63ec8f28b45b6196b2a824944b01c21b380`. The worktree had unrelated planning files and a
reasoning PRD relocation. Those changes were excluded from the candidate.

## Entry decision and scope

The project maintainer authorized implementation in the session on 2026-11-18
after the entry check reported the missing independent decisions. The authorized
slice uses the existing synthetic source mapping, a separate `chatgpt-mcp`
recipient grant for `answer-context`, and the URL-free custom schemas. Each
invocation selects one installation and can issue one delegated source request
with zero retries. Ambiguous connections are rejected before source access. The
independent Stage 0 mapping and snapshot acceptance and Stage 1 disposition
remain pending. R-03 remains open for shared budgets across multiple providers.
[Delivery ledger](../delivery-and-acceptance.md) · [Prior remediation](2026-11-18-synthetic-application-context-review-remediation.md)

The edge reuses the application context policy and typed disclosure projection,
source-side membership, audience-bound delegation, and request-local
`TurnBudget` through the test composition. It uses an explicitly injected
verifier with a fixed synthetic signing key and current revocation state. The
OAuth token stays at the resource edge. Default PAS startup has no optional
MCP route. The source release check and subsequent HTTP send do not form an
atomic transaction across systems. The in-process test verifies revocation
observed before release. It cannot establish remote timing or recall bytes
already delivered.

## Acceptance mapping

Test names below refer to the [optional HTTP suite](../../../adapters/mcp_context/tests/test_context_server.py)
unless linked otherwise. The suite uses the Python MCP SDK over ASGI with no
network listener. Source lookup, source exchange and side-effect counters are
observed independently of responses.

| Case | Evidence |
| --- | --- |
| MCP-01 | `test_default_startup_has_no_optional_mcp_and_no_side_effects` uses a fresh backend process and startup lifespan with an empty mutation inventory, and counts network, model, provider, payer and memory operations. [Backend suite](../../../backend/tests/test_synthetic_application_context.py) |
| MCP-02 | `test_real_sdk_search_and_exact_fetch`, `test_stateless_discovery_and_direct_calls` and `test_protocol_and_origin_denials_are_prelookup` cover modern discovery, direct calls, schema and annotation metadata, version/header agreement and unsupported revision. |
| MCP-03 | `test_oauth_rejected_before_frame_or_source_lookup` checks credential syntax, signature, issuer, exact resource audience, expiry, not-before, token type and approved OAuth client. |
| MCP-04 | `test_only_explicit_current_mcp_recipient_receives_content` denies absent PAS mapping, forged owner and missing grant before any source exchange. |
| MCP-05 | The same recipient test separately rejects runtime and manual snapshot grants. |
| MCP-06 | `test_real_sdk_search_and_exact_fetch` covers owner A and B for travel and fitness, including separate records with the same internal reference. |
| MCP-07 | The recipient test covers wrong app, workspace, source, purpose and client, plus same-email distinct subjects. `test_handle_cannot_cross_user_client_or_application_and_refresh_uses_current_authority` verifies cross-account and cross-client denials. |
| MCP-08 | `test_tool_input_rejected_before_authoritative_lookup`, `test_frame_limits_utf8_and_duplicate_keys` and `test_protocol_and_origin_denials_are_prelookup` cover extra keys, bad input types, invalid UTF-8, extra bytes, malformed/duplicate frames and header mismatch. |
| MCP-09 | Cross-user and client replay tests, and `test_stale_selector_denied_before_or_after_exact_read` for epoch, tenant and reconnect. |
| MCP-10 | Stale selector and `test_authorities_revalidated_between_read_and_release` cover source watermark, revision, expiry, delete, installation, grant revocation and field narrowing, membership and mapping changes. |
| MCP-11 | Revocation between read and release, subsequent credential denial, a freshly signed credential, and fail-closed missing revocation state. |
| MCP-12 | `test_untrusted_source_content_stays_in_the_authorized_projection` preserves untrusted title text as a value and emits no citation field, auxiliary tool execution or private projection fields. |
| MCP-13 | SDK positive path, untrusted content test, and `test_serialized_tool_result_limit_counts_both_representations_and_utf8` check agreed representations, provenance, wire bytes and content-free diagnostics. |
| MCP-14 | `test_search_returns_one_bounded_page_without_a_cursor_or_total`, selector eviction/restart, per-principal rates, concurrent capacity and disconnect, deadline, failed source budget and whole-page denial tests. |
| MCP-15 | `test_rfc_resource_metadata_and_synthetic_issuer_discovery`, OAuth HTTP 401/403 tests, protocol Origin guard, alias-path denial and separate tool-level challenges in post-read tests. |
| MCP-16 | The four scoped SDK paths and the cross-client/application replay tests use explicit bindings for the same account and multiple clients. The recipient test rejects an ambiguous connection. |
| MCP-17 | `test_factory_requires_explicit_test_mode_and_dependencies` rejects disabled, local and production startup and missing dependencies. The backend process test observes the default API lifespan. |
| MCP-18 | Installed ChatGPT was outside the authorized scope. There are no installed-client receipts. |
| MCP-19 | The positive and injection tests require the URL-free schema. Citation eligibility remains gated in the [ChatGPT contract](../chatgpt-integration-boundaries.md). |
| MCP-20 | The shared [side-effect fence](../../../backend/tests/app_context_support/fences.py) observes zero model, provider, payer, network and memory operations for every optional-suite test. |

## Commands and results

Local macOS ARM64 checkout with full Git history. Backend checks used CPython
3.11.15. The optional MCP environment used CPython 3.12.13 and MCP SDK 2.3.0
from the [shared optional lock](../../../adapters/mcp_source/requirements-macos-arm64-py312.txt).
All 28 dependency versions matched that lock.
The SDK preflight over in-process HTTP verified modern discovery/list/call,
`-32022` for an unsupported revision, and Origin rejection before adapter
implementation. The [MCP transport](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports)
and [authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)
specifications and [OpenAI data tool format](https://developers.openai.com/api/docs/mcp)
were consulted on 2026-11-18.

| Command | Result |
| --- | --- |
| `make mcp-context-check` | 0, **95 passed**, zero blocked network attempts. |
| `uv --no-cache build --offline --no-build-isolation --python backend/.venv/bin/python --wheel --out-dir /tmp/pas-mcp-context-wheels adapters/mcp_context` | 0, built the optional wheel offline. |
| `make mcp-context-check MCP_CONTEXT_IMPORT_PATH=/tmp/pas-mcp-context-wheels/personal_ai_mcp_context-0.1.0-py3-none-any.whl:backend/src` | 0, **95 passed** from the wheel import path, zero blocked network attempts. |
| `make mcp-adapter-check` | 0, **44 passed** for the inbound adapter, zero blocked network attempts. |
| `PATH="$PWD/backend/.venv/bin:$PATH" make backend-lint` and `backend/.venv/bin/python -m ruff check adapters/mcp_context` | 0, both passed. |
| `make source-contract-check` | 0, portable source check passed. Strict historical runtime replay and native installed capability were skipped. |
| `make hermetic-capability-check` | 0, all prerequisite suites passed under the offline runner. |
| `make naming-policy-check` | 2 from Make because the checker reports pre-existing untracked planning and handoff files. No candidate path was flagged. |
| `backend/.venv/bin/python -I -m unittest discover -s backend/scripts -p test_naming_policy_check.py` | 0, **5 passed**. |
| `git diff --check` and `git diff --cached --check` | 0. Local Markdown link targets were checked. |

Focused regression from `backend`:

```sh
LITELLM_LOCAL_MODEL_COST_MAP=True .venv/bin/python -m pytest -q --tb=short \
  tests/test_synthetic_application_context.py tests/test_context_provider.py \
  tests/test_context_authorization.py tests/test_context_builder.py tests/test_context_planner.py \
  tests/test_auth.py tests/test_applications.py tests/test_application_scope.py
```

Exit 0, **236 passed**, with three dependency deprecation/support warnings.

The initial broader regression used `make backend-test-offline` with
`PATH="$PWD/backend/.venv/bin:$PATH"`, `LITELLM_LOCAL_MODEL_COST_MAP=True` and
`PYTHONPATH="$PWD/sdk/python/src:$PWD/examples/project-checklist/client/src:$PWD/examples/project-checklist/host/src"`.
It exited 2 from Make with 3,402 passed, 11 failed, 1 skipped, 92 errors and 204
deselected. Loopback HTTP setup hit a sandbox bind denial. A local-only bind
probe confirmed that the fixture ports work outside that restriction. The
rerun used the same target with a clean environment and a temporary Python
audit hook in `sitecustomize.py`. The hook rejects non-loopback DNS and
IPv4/IPv6 bind, connect and send operations. The command was:

```sh
env -i PATH="$PWD/backend/.venv/bin:$PATH" TMPDIR="${TMPDIR:-/tmp}" \
  PYTHONPATH="/tmp/pas-mcp-loopback-fence:$PWD/sdk/python/src:$PWD/examples/project-checklist/client/src:$PWD/examples/project-checklist/host/src" \
  LITELLM_LOCAL_MODEL_COST_MAP=True make backend-test-offline
```

Exit 0, **3,506 passed**, 1 skipped, 204 deselected and four dependency
warnings. The loopback HTTP suites ran in this local check.

Hosted full-history GitHub Actions runs for Python 3.11 and 3.12 were not
verified at the candidate revision. Live OAuth registration and exchange,
installed ChatGPT selection and follow-up behavior, authenticated citations,
physical send timing, provider, persistence integration and cloud smoke
remain outside the evidence.
