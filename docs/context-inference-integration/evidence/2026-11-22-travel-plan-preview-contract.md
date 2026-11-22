# Travel private plan preview contract probe · 2026-11-22

**BLOCKED_CONTRACT for an integrated preview and dispatch.** The source-level probe reproduced two independent contract failures. The actual isolated PAS application and Travel middleware could not start with the available offline dependencies. This record supplies partial observations for the joint decision. Integrated E1 and native E2 remain unverified. Live E3 remains `BLOCKED_EXTERNAL`.

| Checkout | Tested product revision | Working tree at outset |
| --- | --- | --- |
| PAS | `f5f60fb6f871dad9d59071f2ebf91ecb8e1c69f1`, parent `cfc4d7430e53a401e31327231dbb4e0fd0341ede` | Clean |
| Travel | `61a708b257cb9862bc415ce8a7151201489d3472`, parent `4836fb82d45a66ed2fab726eff4e31e09f9ae8fa` recorded in the shallow tip | Clean |

The probe reads the pinned Travel handler, schemas and service methods from Git objects. It imports PAS's unchanged Travel provider, typed context contracts and planner. It invokes the actual private intent parser and the source-version condition extracted from PAS's pinned preview method. A small ASGI app mounts the Travel handler with an injected fabricated owner and a disposable SQLite repository in place of the unavailable SQLAlchemy stack. PAS's adapter sees the actual captured response bytes through an injected client. The synthetic memory namespace marker isolates the PAS version condition. The canonical PAS memory service, full private host, anchor store and recipient-authority stores were outside this probe.

## Observations

| Check | Observed result |
| --- | --- |
| Existing PAS planner | With an empty candidate tuple, the existing Travel rule omitted the source with `entity_reference_required`. Supplying a fixture ref to the planner as a separate control selected the existing four-result, 24,576-byte rule. |
| Private request shape | The actual private parser accepted the base request and rejected each additional property `entity_refs`, `launch_context` and `workspace_id` with 422. |
| Source read | Four consecutive ASGI reads interleaved A, B, A, B under one fixture owner, with conversation labels CA, CB, CA, CB in the harness. The handler returned revisions 4, 9, 4, 9. It accepted a subsequent B selector under the same owner even though the harness association CA→A was unchanged. The existing request and route carry no conversation association. |
| Foreign owner and revision | The SQLite owner-query substitute returned no matching row for a foreign owner. The actual Travel service and route produced 404 without the title. The verify projection observed revision 10 after a state change. After reassignment to another owner the same verify request returned 404 without the title. Eight owner/trip queries ran. |
| Projection and PAS mapping | Each current read returned exactly the two requested fields and used less than 4,096 bytes. The v2 source ID, source revision, observation time, absent expiry, sensitivity and field classifications, source fingerprint and Travel permission ID/version were checked. The existing PAS adapter preserved the source identity and version in the context item. Its authority snapshot preserved the permission version and source fingerprint. |
| PAS preview condition | The unchanged condition raised `context_no_ai_route` for each actual Travel authority snapshot with decimal revision 4 or 9 alongside the expected memory namespace marker. No integrated inventory was published. |
| Reverse authentication | Travel's actual Ed25519 wire verifier accepted a fresh fabricated assertion against the exact v2 request in isolation. It denied expiry, changed trip body and unregistered audience. The pinned legacy task ingress rejected `personal_ai_context` with 401 `task_identity_denied` before the injected service verifier ran. This is evidence that the current Shopping-gated ingress cannot provide the private reverse hop. |

The probe's HTTP transport was entirely in process. A Python audit hook blocked outbound DNS and socket connect calls, and the probe completed with zero observed attempts under that hook. The diagnostic had no runtime release or provider send path. Independent syscall capture failed because the sandbox denied `ptrace`. The synthetic Ed25519 assertion was local. No live credentials, provider session, charge or deployment was exercised.

## Open interfaces

1. PAS's `preview_bound_context` authorizes the route conversation before planning but supplies no candidate entities. The ordinary Travel rule needs a trip candidate and its existing bounds exceed the private profile. After planning, the assembler passes the authorized conversation in `ContextProviderInputs.pending_message` to a request-bound provider factory. This is a possible seam if a separate bounded private rule admits one source and the factory carries verified owner, actor, target, client, lane and conversation into the authorized source call. A factory receiving a message is insufficient evidence that those authorities reached Travel. The private `mount_application_plan` assembler dependency is another possible composition point, provided it defers data access until conversation authorization. [Chat preview](../../../backend/src/personal_ai/services/chat/service.py#L389) · [Assembler](../../../backend/src/personal_ai/context/assembler.py#L363) · [Provider factory](../../../backend/src/personal_ai/context/providers.py#L639) · [Route](../../../backend/src/personal_ai/api/private_application_plan.py#L71)
2. Travel's existing task ingress only admits the Shopping purpose on the non-command branch. A jointly approved private reverse-hop contract would need an independent service identity and fresh signed human delegation bound to the exact target, lane, client, conversation, purpose and operation. Travel would resolve a write-once association and recheck current owner and trip authority. The same-owner alternate selector remains admissible on the legacy v2 route by design. [Travel task ingress](https://github.com/jasonkli21/travel-app/blob/61a708b257cb9862bc415ce8a7151201489d3472/backend/src/personal_travel/auth/task_ingress.py#L47) · [Travel source route](https://github.com/jasonkli21/travel-app/blob/61a708b257cb9862bc415ce8a7151201489d3472/backend/src/personal_travel/api/routes/personal_ai_context.py#L587)
3. PAS's embedded source-version prefix is a separate blocker even if both selection and reverse authentication are solved. The smallest proposed PAS review item is to admit a typed application-plan authority attestation that is distinct from the original Travel source revision, with exact current owner, client, private lane, target, conversation, field and recipient dependencies. The existing shared-source authority path and wire compatibility need to be preserved. Merely prefixing Travel's decimal revision would provide no attestation. [Preview check](../../../backend/src/personal_ai/services/external_turns/application_plan.py#L330) · [Travel mapping](../../../reference-apps/src/personal_ai_reference_apps/context/travel.py#L512)

The coordinated runtime fixture's lock does not participate in Travel SQL writer transactions or arbitrary PAS native memory and source writes. Release, pre-send, outward content, replay and recovery remain open. [Prior runtime evidence](2026-11-21-coordinated-private-runtime.md)

## Reproduction and checks

The source-level probe ran with Python 3.12.14, FastAPI 0.141.1, HTTPX 0.28.1, Pydantic 2.13.4 and cryptography 50.0.0 from the installed runtime. The paired `travel-context-read-v2-reservation.json` checksum was `5e5aa6e161c4d8461a3098eeaafb098e8661b78a0a87de2e85f63df2b937076d` in both repositories. The PAS private schema checksum was `40e4c1e3515fab057488042c791e298e15f2942008fe1ffba597a9020b700081`.

| Command | Exit and result |
| --- | --- |
| `python backend/scripts/travel_plan_contract_probe.py --travel /tmp/r4travel` | 0. Recorded the source-level observations above. |
| `python -m py_compile backend/scripts/travel_plan_contract_probe.py` | 0. |
| `git diff --check` and `git diff --no-index --check /dev/null backend/scripts/travel_plan_contract_probe.py` | 0. No whitespace findings. |
| PAS backend `UV_CACHE_DIR=/tmp/r4-uv uv sync --offline --locked --extra dev` | 1. Missing cached `charset-normalizer==3.5.2`. |
| Travel backend `UV_CACHE_DIR=/tmp/r4-uv uv sync --offline --locked` | 1. Missing cached `mypy==2.4.0`. |
| PAS backend `python -m pytest -q tests/test_private_application_plan_http.py tests/test_application_plan_inference.py tests/test_application_plan_process_delivery.py` | 1 before collection. Pytest missing. |
| Travel backend `python -m pytest -q tests/test_personal_ai_context.py tests/test_personal_ai_client.py` | 1 before collection. Pytest missing. |
| `make backend-lint` | 2. Ruff absent. |
| `make naming-policy-check` | 2. Existing R0 handoff has two phase-coded text findings. |
| `make source-contract-check` | 2. The unpopulated locked environment lacks Pydantic. |
| `python -I backend/scripts/source_contract_check.py --check` | 1. System Python recomputed existing planning and offline-information-handling source-identity differences against the frozen ledger. No product source files changed. |
| `UV_CACHE_DIR=/tmp/r4-uv UV_OFFLINE=1 make consumer-contract-check` and separately `UV_CACHE_DIR=/tmp/r4-uv UV_OFFLINE=1 make sdk-install-check` | 2 each. Build backend Hatchling absent. |
| `PYTHONPATH=backend/src python backend/scripts/consumer_contract_check.py --check` | 1. Import of the PAS application stopped at missing Google API package. |
| `make hermetic-capability-check` | 2. Locked environment lacks urllib3 before suite collection. |
| `strace -qq -f -e trace=network -o /tmp/r4-probe-network.log python backend/scripts/travel_plan_contract_probe.py --travel /tmp/r4travel` | 1. Sandbox denied tracing. |

Restricted package sync attempts failed at TCP connect, and automatic review declined network-enabled PyPI installation because the authorized work was offline. No packages were downloaded. The real Travel route import failed on missing SQLAlchemy. The actual direct-bearer middleware, independent service authentication, verified bound anchor, canonical memory, recipient grant isolation and interleaved private preview inventory remain `NOT_RUN`. Travel source rectification and the PAS attestation change require a joint decision before any integration or dispatch. Existing R1 adoption review, R2-A independent review and R3-A independent acceptance remain open. The four previously recorded R3 native PostgreSQL cases retain their original scope. [Prior runtime evidence](2026-11-21-coordinated-private-runtime.md)
