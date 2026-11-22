# Travel and PAS private preview attempt · 2026-11-22

**`BLOCKED_CONTRACT` for integrated preview and dispatch.** The unchanged
PAS preview fails before Travel data access. The offline environment also
lacks dependencies needed to run the normal isolated PAS application and
the Travel source against its SQLAlchemy/PostgreSQL store. No paired E1 or
native E2 acceptance is claimed. Live E3 remains `BLOCKED_EXTERNAL`.

| Checkout | Product revision inspected and exercised |
| --- | --- |
| PAS | `d66963b49dc5de8802510e7449a9a9ac6cb7fcd8`, product code from parent `f5f60fb6f871dad9d59071f2ebf91ecb8e1c69f1` |
| Travel | Local preview candidate `77f3c7a1257b6231ca6cbcffb8a93d121372c861` |

The working trees were clean at entry. This attempt changed only PAS diagnostics
and documentation. Private request/response schemas, Travel's v2 source shape
with `workspace_id=null`, and the legacy paths use their pinned implementations.
Compatibility suites could not run here.

## Executed observations

| Check | Observed result and limits |
| --- | --- |
| Unchanged PAS preview service | The actual `ApplicationPlanService.preview`, `ChatTurnService.preview_bound_context`, installed Travel registry metadata, shared assembler and planner ran with an in-memory conversation store. Two different conversation UUIDs shared one owner and registered client. In A/B/A/B order the planner selected the memory rule and omitted Travel with `entity_reference_required`. The plan service then raised `context_no_ai_route` four times from `prepare_sources`. Assertions guarded both Travel reads and canonical memory retrieval, and neither was reached. No preview or in-flight reservation remained. An unknown conversation raised `ResourceNotFoundError` before preparation. |
| PAS private HTTP boundary, reduced harness | The actual middleware and route function bodies ran over in-process ASGI with test replacements for unavailable imports, Google verification, request dependencies and thread dispatch. A locally signed direct human bearer with the registered issuer, subject, audience and authorized party reached all four previews, which returned 422 `context_no_ai_route`. Unknown conversation returned 404, wrong authorized party 403, wrong audience 401, forwarded human identity 401 and additional selector field 422. The error handlers in this harness mirror the relevant production status mapping. The harness did not load the normal application, call Google or establish production ingress. |
| Independent reverse-hop authentication | The existing PAS `delegated_user_assertion` signer interoperated with Travel's actual `authenticate_private_plan_source` and Ed25519 verification. A distinct locally signed service bearer used its own verifier, key, account and audience. Four signed current requests in A/B/A/B order and one signed verify request authenticated. Ten invalid combinations denied, covering assertion replay against another conversation or operation, expired delegation, wrong client, wrong target, trip selector, wrong lane, a non-null workspace, missing human assertion and a human assertion used in the service bearer slot. This was authentication-only and exercised no ACL store. |
| Travel signed route, reduced harness | A separate Travel route diagnostic used the pinned mount, Travel's Ed25519 delegation verifier and v2 projector. Its substitute SQLite lookup returned trip A revision 0 and trip B revision 9 for four A/B reads. It observed no-store, one record under 4,096 bytes, null workspace, the original source identity and decimal permission version, and the source fingerprint. The wrong client, lane, target, selector and expired delegation returned 401. Verify returned the revision only. A changed revision returned 409. Revoked trip access and disabled identity returned 404 without trip titles. This harness substituted the SQLAlchemy identity/binding lookup and worker dispatch. The route did not receive requests from the PAS preview. |
| Source normalization | The [prior version probe](2026-11-22-travel-plan-preview-contract.md) exercised PAS's actual v2 provider normalizer against Travel's original decimal revisions, fingerprints and permission versions. The unchanged plan's separate version guard rejected those normalized snapshots. The current PAS path still runs the same guard after preparation, which this attempt could not reach. |
| Disclosure | The diagnostics ran in-process with socket auditing and observed zero outbound socket attempts. No continuation, runtime release, physical provider send or live credential was used. No authorized preview inventory was published, and canonical memory consent, recipient isolation and outbound/recovery revalidation were not exercised end to end. |

## PAS seam for joint review

1. The private route passes the conversation ID to the plan service, and
   `preview_bound_context` enforces owner and external client namespace before
   calling the planner. A dedicated server-installed application-plan rule can
   admit one bounded domain operation with no caller entity selector. The
   request-bound provider factory receives the authorized conversation on
   `ContextProviderInputs.pending_message`; use it with the verified principal,
   current target registration, client and private lane. Sign exact Travel
   `current` and later `verify` bodies through the existing delegation signer.
   Travel resolves the trip. A timeout or missing binding denies access.
2. The contribution needs a typed application-plan attestation distinct from
   source metadata. Preserve the original v2 source ID, decimal revision,
   fingerprints, observed time, absent expiry, sensitivity, field classifications
   and Travel ACL dependency. Bind the attestation to the registered PAS target,
   authorized human/owner/client/conversation, private lane, source item and
   fields, and independent current-read, runtime and model recipient grants.
   An attestation expiry can bound the private preview without changing the
   Travel source expiry. Require evidence from scoped authority stores and exact
   Travel `verify` before an attestation can revalidate. A new string prefix on
   the Travel revision would establish none of these authorities.
3. The plan service can retain the existing strict two-item inventory and legacy
   shared-source condition, admitting a typed validated authority for the exact
   domain snapshot as an additional path. That authority must remain in the
   prepared snapshot and digest and survive persistence/replay. Audit
   `source_snapshot_authority_complete` and automatic sourced-history exclusion
   alongside the preview check. Both currently recognize private plan authority
   through shared-source/memory version or permission namespaces. Changing only
   the preview guard could lose protection on later reuse. No guard changed
   while this contract is awaiting review.

The coordinated runtime fixture's lock cannot serialize independent Travel SQL
ACL writers or PAS native memory/source writers. Release, pre-send, replay and
recovery remain open. R4-03, 05–08, 13–15 and 34 retain the outstanding gate
requirements in the joint decision.

## Reproduction and blockers

Run the reduced PAS service, PAS HTTP and PAS-to-Travel authentication checks
from the PAS root with the two pinned checkouts and the installed system
runtime. Python 3.12.14, FastAPI 0.141.1, HTTPX 0.28.1, Pydantic 2.13.4,
cryptography 50.0.0 and PyJWT 2.13.0 were available.

```sh
PYTHONPATH=backend/src:reference-apps/src:sdk/python/src:/tmp/r4travel/backend/src \
  python backend/scripts/travel_plan_paired_diagnostics.py
```

| Attempt | Result |
| --- | --- |
| PAS `UV_PROJECT_ENVIRONMENT=/tmp/r4-pas-paired-env UV_CACHE_DIR=/tmp/r4-pas-cache uv sync --offline --locked --extra dev` | Exit 1. The locked `requests==2.34.2` wheel was absent from this cache. |
| Travel `UV_PROJECT_ENVIRONMENT=/tmp/r4-travel-paired-env UV_CACHE_DIR=/tmp/r4-travel-cache uv sync --offline --locked` | Exit 1. The locked `httptools==0.8.0` wheel was absent from this cache. |
| Direct PAS host, private route and canonical memory imports | Exit 1. `google.api_core` or `google.auth` was absent. |
| Direct Travel isolated source import | Exit 1. SQLAlchemy was absent. |
| Native PostgreSQL | No installed PostgreSQL executable or test DSN was available. Docker image inventory could not open the local Docker socket. |
| PAS reduced diagnostics above | Exit 0. In-process boundary and authentication observations only. |
| Travel signed-route diagnostic | Exit 0 with a substitute SQLite identity/binding lookup. The native Travel test entry point is `backend/tests/test_private_plan_postgres.py` with a disposable `TEST_DATABASE_URL`. |

The paired Travel v2 reservation fixture SHA-256 is
`5e5aa6e161c4d8461a3098eeaafb098e8661b78a0a87de2e85f63df2b937076d`
in both repositories. The PAS private v1 schema SHA-256 is
`40e4c1e3515fab057488042c791e298e15f2942008fe1ffba597a9020b700081`.
No frozen manifests were regenerated.

| Repository check | Result |
| --- | --- |
| PAS focused plan tests and Travel focused private source and legacy tests | Exit 1 before collection. Pytest was absent. |
| PAS `make backend-lint` | Exit 2. Ruff was absent. |
| PAS `make naming-policy-check` | Exit 2. The existing R0 handoff had two phase-coded text findings. |
| PAS `make source-contract-check` | Exit 2. The locked environment lacks Pydantic. System Python ran the underlying checker and returned the inherited planning and offline handling source-identity differences. |
| PAS `make consumer-contract-check` and `make sdk-install-check` with `UV_OFFLINE=1` | Exit 2 each. Hatchling was absent. The direct consumer check in the locked environment also stopped on missing Pydantic. |
| PAS `make hermetic-capability-check` | Exit 2. The locked environment lacks urllib3. |
| PAS diagnostic syntax and diff whitespace | `python -m py_compile` and `git diff --check` passed. Both added files also passed the whitespace check against `/dev/null`. |

Independent closure needs the actual isolated PAS application with its canonical
memory service, the actual signed Travel source using a disposable migrated SQL
store, the exact local/model recipient grant stores, and observed A/B inventory
with the original Travel source authority. This diagnostic supplies the first
unchanged runtime failure boundary and the signer interoperability check.
