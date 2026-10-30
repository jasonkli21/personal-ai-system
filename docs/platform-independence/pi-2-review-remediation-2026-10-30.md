# PI-2 review remediation evidence

**Date:** 2026-10-30 (America/Los_Angeles)
**Entry revision:** `96227267e4c1361a2366278b051a5d7b2fd5d7d7`
**Result:** The two blocking local findings are remediated in the containing
commit. PI-2 remains an implementation candidate; this record is not independent
acceptance or production approval.

## Scope and hardening decisions

The attached independent review handoff was treated as evidence and implementation
guidance. The working tree contained pre-existing untracked planning and review
documents; they were preserved and excluded. The remediation changes only the
external create contract, the shared chat disclosure boundary, focused tests,
planner evidence binding and this evidence/current-state documentation. No
migrations, memory implementation, provider adapter, or domain record changed.

The challenge pass kept the external key requirement out of the shared request
model so builtin callers retain optional-key behavior. It uses the existing
deterministic conversation key path and creates no ledger. For streaming, the
existing ChatTurnService and canonical persistence path remain authoritative. Each
external output event gets a current identity/workspace check and a source snapshot
check immediately before disclosure. The check runs through the existing I/O
thread helper and is skipped for builtin requests. Each external delta therefore
adds one policy, directory, membership and source-rights reread; this is a
deliberate per-delta cost. No benchmark established a latency bound. A revocation
that races between a successful check and transport send is still possible; this
does not claim a distributed or physical-send fence.

## P1-A — external create retry identity

External `POST /v1/conversations` now returns safe `422 validation_error` for an
omitted or null `idempotency_key`, before calling the conversation service or
writing a row. A required, non-null `ExternalCreateConversationRequest` is used in
the published consumer OpenAPI subset. The shared first-party request model stays
optional, and the builtin keyless-create HTTP regression still passes. Same-key
replay returns one canonical conversation; changed title with the same key returns
409. The existing concurrent keyed-create test confirms both callers receive the
same record and only one row exists. No model request is involved in creation.

The test uses the real FastAPI middleware and loopback HTTP fixture with a freshly
signed synthetic Google-style user token and closed in-memory storage/model ports.
It covers missing and null keys, replay, changed-body conflict, concurrency, the
generated required field, and builtin compatibility. This is local protocol
evidence, not OAuth or deployed identity evidence.

## P1-B — revocation before each streamed disclosure

Before each external `response.delta`, the service rereads current client binding,
token expiry, owner-directory activity and workspace membership, and revalidates
the turn's source snapshots. Completed-key replay applies the same fence before
each `message.created`, replay delta and completion event; this matters because a
created assistant message itself contains retained content. A failed fence emits
one safe `response.error`, emits no later delta or completion, and does not replace
or retry the original key. The canonical completed record is not rewritten by a
denied replay.

The held-provider regression waits until the first delta is received over HTTP,
then separately withdraws client binding, workspace membership, directory
activity, token validity or source authority before releasing the second chunk.
For each case, the second chunk and completion are absent, one provider request is
counted, status is `unknown` after restoring the fixture authority, and retrying
the original key returns 409 without a second provider request. A successful
completed replay with revoked source authority returns a safe error before
disclosing the retained answer. Existing pre-send revocation tests still prove
zero model requests when authority is withdrawn during context counting.

The first allowed replay regression exposed an uncaught authority exception after
SSE headers had started. The replay path was updated to turn this into a safe
terminal error event without mutating the completed record; the full HTTP suite
then passed. No raw provider exception, token, policy path or source identifier is
placed in the error body.

## P2-E — expanded adversarial coverage

A source-profile HTTP test registers two external application/host contributions,
with separate audience/authorized-party bindings and workspace membership. It
tries A-token/B-header and B-token/A-header swaps against create, list, get,
continuation status, context preview and continue. The matrix covers records for
the same owner across applications and a different owner/workspace principal; all
swaps are denied before record changes or model calls. Existing tests cover an
unselected app header, builtin-vs-external guesses, malformed/disabled/expired
policy, oversized input, external operation denials and original-key recovery.

The second host is synthetic and is intentionally absent from the separately
installed Reading Logbook profile; the installed profile skips this one source
matrix case. The installed profile still exercises the real separately installed
host and client packages, original-key behavior and all remaining HTTP cases.
Independent fixture scheduling, hosted Linux/Python 3.12 CI and native/network
fencing remain open review work.

## Verification record

The final source HTTP run used Python 3.11.15 on macOS arm64 and
`backend/scripts/pi2_http_checks.py`, whose Python audit hook permits only numeric
loopback and reported zero denied network attempts. It passed **45 HTTP/SSE
tests**, including the source-profile A/B host matrix. The signed fixture uses an
ephemeral RSA test key, synthetic claims, explicit membership, in-memory
repositories and the fake model; it does not verify live Google keys or storage.

`UV_OFFLINE=true UV_CACHE_DIR=/tmp/pi2-uv-cache make pi2-check` passed on the same
runtime after rerunning with permission for its numeric-loopback fixture. It
rebuilt backend, reference, host and client wheel/sdist artifacts; passed the
dependency inventory and 30-case non-promoting planner probe; ran installed PI-1
core/legacy/original-task subsets (**49 / 190 / 56 passed**); and passed the
installed PI-2 profile (**64 passed, 1 skipped**). The skipped case is the
source-only synthetic second host described above. The installed probe verified
package origins, client-only import isolation, and reference/host uninstall
behavior. The Python audit hook reported zero forbidden attempts. The initial
non-escalated `make pi2-check` could not bind the test loopback socket and is not
counted as a pass.

The handoff's additional offline command passed **195 tests** with zero blocked
network attempts:

```sh
backend/.venv/bin/python backend/scripts/pi1_offline_checks.py -q \
  backend/tests/test_auth.py backend/tests/test_chat_stream_lifecycle.py \
  backend/tests/test_application_scope.py backend/tests/test_context_runtime_composition.py \
  backend/tests/test_memory_disclosure_authorization.py \
  backend/tests/test_memory_control_api.py backend/tests/test_memory_knowledge.py \
  backend/tests/test_phase36_integrated.py backend/tests/test_federation.py \
  backend/tests/test_pi2_client.py --tb=short
```

Backend lint, Reading Logbook lint, generated contract check and `git diff --check`
passed. An earlier exploratory run stopped at the strict planner source guard
after the code changed. The v21 source-only binding now preserves v20's planner
configuration, corpus, fixture dependencies and non-promotion without weakening
the current-or-direct-child guard. Historical lock v20 and earlier fixtures stay
unchanged.

The remediation fixture identity is
`f620be93d81e7c73722d34365a250b1d860cf54424cb7f22d4d369f5bb026e6f`; the active
lock is [planning-baseline-v21.json](../../backend/src/personal_ai/evaluation/fixtures/context/planning-baseline-v21.json).
The core package wheel/sdist SHA-256 values were
`25ff14e121825225f26870d2ddb91facdccb718f1737020f98df94a768969207` /
`8b70b722081c4af4a7a22baf47ca649ae48b575e7d2b27d0b7dc1206e2d15ef9`. The client
wheel/sdist hashes were
`19e448a3e9a9fd408359292005752a7f3534d7da381303bab19c675fdebaa4a0` /
`f2d2f1a7379b0145e3cdcdb02e0f2856f42663d6efa1c8a61fa682eca0f81fc1`; the host
wheel/sdist hashes were
`4b11168dd3a22927cf47592d5b5f4f6a41e4ab1b15b5bc3ef819e0a1648b8e3c` /
`a793e5c29fd86782ef412daf1001fa683f764c5d56304d90dadc39ffd50ed6f7`. The
reference wheel/sdist hashes were
`dc34894104bdda3a82fef1b4f1b69fca6f84649cdacaa6983eeefc0a107071fd` /
`ba3464852d505ae68a2484af9dacbc03ca3ca9d03c3b17abbe12d551de4cc58c`.

## Compatibility, privacy and remaining gates

No schema migration, account data, message, key derivation, task receipt, source
tombstone, memory flag, memory fixture or provider dispatch policy changed.
Builtin keyless creation remains supported. External incomplete/failed requests
retain the same deterministic key and cannot trigger an automatic replacement-key
send. App and workspace scope checks remain in the existing authorization path.
No cloud credentials, personal data, live model, cloud, native database or
deployment was used.

Real Google OAuth registration and key verification, private service IAM, deployed
membership/source revocation, native PostgreSQL/DynamoDB recovery and races, backup
and physical deletion, actual provider token/cost behavior, Linux/Python 3.12 and
hosted CI remain unverified. MEM-0/1/2 and Phase36 acceptance, PI-0/PI-1
independent acceptance, and independent PI-2 review remain open. Safe rollback is
to disable the external client policy and ingress, then unselect or uninstall the
host/client while preserving canonical records, original keys and journals. No
rekey or data deletion is required.
