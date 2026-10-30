# External conversation HTTP contract v1.0.0

PI-2 local implementation candidate, 2026-10-30. Independent review and deployed
identity/provider/storage acceptance remain open. The [generated OpenAPI subset](consumer-v1.openapi.json)
is derived from executable routes/models by `backend/scripts/pi2_contract.py`.
The server's full `/openapi.json` includes additional first-party and gated APIs;
those are not part of this external consumer contract.

## Identity, selection and bounds

Use HTTPS and a verified Google **user ID token**, not an access token, service
assertion, client secret or app header as authority. The operator separately
registers an OAuth client, allows its exact verified `aud` and effective `azp`
(`azp`, or scalar `aud` when absent), and binds it to one application. Google
signature, issuer, audience, expiry, verified email allowlist and principal
directory checks remain mandatory. Multi-audience claims are unsupported.
Existing builtin UI tokens keep their reserved audience and must have matching
(or absent) azp; their canonical app/reference selection remains available.
External clients cannot select the builtin or another app by changing headers.
Do not give external clients the builtin UI OAuth registration.

Send `Authorization: Bearer <user-id-token>`, `X-Application-ID` and, when required
by the host, `X-Workspace-ID`. A trusted private gateway may use the existing
`X-User-ID-Token` user-forwarding header **only with independently verified private
service invocation**. The client sample handles user bearer tokens; it does not
mint Cloud Run IAM tokens or create a public gateway. Private deployment ingress
remains required. `X-Owner-ID`/`X-Acting-User-ID` are denied in the external lane;
owner/actor body fields are invalid. Client context and launch metadata are
advisory. They cannot grant membership, source access or model disclosure.

External POST bodies are limited to **131,072 bytes** with a **10-second** body
read deadline; oversized/slow bodies return 413/408. Content is 1–20,000 characters;
titles are 1–200 characters (omission/null uses the default). UUID keys must be
retained. The generated schema defines all other field/selector limits. Model
context/output/time budgets remain operator settings; valid input may exceed the
context budget and be refused. Lists are bounded by the existing repository
(default newest 50); there is no pagination or exhaustive export guarantee.

## Supported operations

| Method/path | Meaning |
| --- | --- |
| `POST /v1/conversations` | Create with `title` and stable UUID `idempotency_key`; 201, including replay |
| `GET /v1/conversations` | Current owner/application/workspace's bounded list |
| `GET /v1/conversations/{id}` | Scoped conversation and active message branch |
| `POST /v1/conversations/{id}/context-preview` | Automatic planner metadata only; no raw context or provider execution |
| `POST /v1/conversations/{id}/continue` | Stable UUID-keyed automatic continuation via shared assembler; SSE |
| `GET /v1/conversations/{id}/continuations/{key}` | Read original key's canonical state and optional message UUID, including inactive branches |

The Reading Logbook host permits only conversation history. It supplies no
memory/profile/domain provider. Planning previews show selections/exclusions,
not context content or authorization promises for a later turn. Source policy,
current permissions and budgets are checked again during preparation and before
model send. No cross-app grants are added. Gated external-turn preparation,
manual/connected dispatch, non-idempotent `/messages`, tasks, account operations,
profile administration, raw context inspection and memory controls are unavailable
to this external lane. Existing builtin callers retain their current APIs/gates.

Example create body (generate and journal UUID once before sending):

```json
{"title":"Book discussion","idempotency_key":"de28aa09-a8ce-4e15-a450-63456a10f690"}
```

Preview and continue use the same request shape:

```json
{"content":"Discuss this note I explicitly chose to send.","idempotency_key":"66e4618a-7acf-44dc-b00e-61565bf6e9af","choice":{"mode":"automatic"}}
```

## SSE and recovery

Frames use UTF-8 `event: <name>\ndata: <JSON>\n\n`. Event schemas are in
`x-sse-events` in the generated spec. Ordered vocabulary:

1. `message.created` with `{message}` for user and assistant.
2. Zero or more `response.delta` with `{message_id, delta}`. Text is provisional.
3. `response.completed` with the canonical completed `{message}`, or
   `response.error` with `{message_id, code, message}`. Normal stream exhaustion
   and successful durable status must agree before the client calls it completed.

There are **no SSE IDs or Last-Event-ID resume semantics**. A stream may fail
before HTTP headers (JSON error), or after 200 (SSE error/incomplete transport).
HTTP 200, deltas, socket EOF, or a local timeout alone do not establish success.
Clients must bound frames/output, handle fragmented UTF-8/CRLF and reject invalid,
duplicate or inconsistent terminal frames. The sample bounds each event to
262,144 bytes and the total stream to 2,000,000 bytes; excessive metadata results
in an unconfirmed observation, not success.

Creation retries use the original key and title. An existing normalized title
mismatch returns 409. Continuation retries use the **original key and complete
original body**. Completed requests replay canonical completion without a new
model send. Changed input conflicts. Existing incomplete/failed/cancelled assistant
keys refuse re-execution with 409. There is no automatic replacement-key retry.

Status returns `{state,message_id}`: `not_found` means neither message was
observed at that instant; `in_progress` means a streaming assistant exists;
`completed` means a canonical completed assistant exists; `unknown` means a
failed/cancelled assistant or user-only preparation. Status never repairs state,
resends a model call, or authorizes a new intent. Stale state/native database
recovery retains its existing limits. After a disconnect, expiry, rate limit,
429/5xx or process restart, reconcile **that same key**. The sample `recover`
reads status and replays only a completed request. Unknown/in-progress remains
unconfirmed. A new key requires an explicit new user intent and may incur another
model call. No domain effect is part of this protocol.

## Safe errors and compatibility

Errors use `{"error":{"code":"...","message":"..."}}`; all protected results
use `Cache-Control: no-store` and a bounded correlation `X-Request-ID`. Do not parse
human messages or retain credentials in logs. Representative rules:

| HTTP | Stable codes / action |
| --- | --- |
| 400 | `application_scope_invalid`, `request_scope_invalid`, workspace required/unsupported |
| 401 | `authentication_required`, `invalid_identity`; obtain a valid token, retain original key |
| 403 | `application_client_denied`, `client_identity_override_denied`, `client_operation_denied`, `workspace_not_authorized`, `access_denied`, `origin_denied` |
| 404 | `not_found`, `application_not_registered`; foreign UUIDs reveal no record |
| 408/413 | `request_body_timeout`, `request_body_too_large` |
| 409 | `conversation_conflict` for changed input; `conversation_busy` for in-progress or non-resumable state; reconcile original key |
| 422 | `validation_error`, context/source/launch/federation denial; correct intent explicitly |
| 429 | Safety/request limits, with `Retry-After`; no automatic new key |
| 503 | `authentication_unavailable`, `application_client_policy_unavailable`, `workspace_authority_unavailable`, `storage_unavailable`, provider/context/safety unavailable |

An unexpected 5xx or malformed response remains unconfirmed. SSE error codes are
safe generation/context codes, not raw provider exceptions. A revocation during
preparation produces `context_client_authority_changed`; it cannot recall data
already sent to a model. Cancellation/lost acknowledgment does not prove no send.

Version `1.0.0` is independently versioned from host Python contracts. Within v1,
additive optional fields/operations and new safe error codes may appear. Clients
ignore unknown object fields and nonterminal future events while enforcing the
completion protocol; they do not infer success from unknown events. Removing or
reinterpreting required fields, authorization or retry semantics needs a new
major contract and an explicit migration guide. Deprecation requires release
notes and an operator-announced support window before removal; no removal date
is scheduled. The pinned JSON and conformance fixtures must change together.
