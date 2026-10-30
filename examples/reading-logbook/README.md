# Reading Logbook independent consumer

PI-2 candidate. Books/notes and the operation journal live in local SQLite. The
client has **zero runtime dependencies**, uses only HTTP, and imports neither
platform nor reference code. The separate host distribution runs trusted server
code and imports only `personal_ai.extensions.v1`.

## Offline build and acceptance

With the root README's existing build dependencies installed:

```sh
UV_OFFLINE=true UV_CACHE_DIR=/tmp/pi2-uv-cache make pi2-check
```

This builds core/reference/client/host wheels **from their sdists**, inspects
metadata/members, exercises PI-1 profiles, then installs the fifth host/client
outside checkout with references physically absent and `PYTHONPATH` unset. A
separate client-only interpreter runs the CLI over real loopback HTTP. Synthetic
Google-style JWTs exercise real Google signature/issuer/audience/time verification
with a fake certificate transport. Storage/counter/model ports are fake, including
a closed startup inventory. Python audit fences reject non-loopback network and
DNS, including in CLI subprocesses. Native C/OS-wide egress isolation is not
claimed. The fixture never loads credentials or `.env`, downloads dependencies,
or calls real providers. Run where loopback sockets are permitted.

For a client-only install, use your environment's installer offline:

```sh
uv pip install --python /absolute/client-venv/bin/python --no-index --no-deps \
  examples/reading-logbook/client/dist/reading_logbook_client-0.1.0-py3-none-any.whl
```

## Operator registration and user token flow

1. Install the core and separately built `reading-logbook-host` wheel into the
   server environment. Installation alone does not select it. Set
   `APPLICATION_CONTRIBUTIONS='["reading_logbook"]'`. This selects both existing
   catalogs; no app-specific core patch is required. Unknown/duplicate entries or
   missing membership configuration fail startup. The host declares no routes,
   providers, tools, grants or memory intake.
2. Configure the platform's existing `google_oidc`/required auth, exact builtin
   audience, verified email allowlist and principal directory/private ingress.
   Register a **distinct** Google OAuth public client for Reading Logbook using an
   operator-approved login helper: authorization-code flow with PKCE and approved
   redirect URI, state/nonce validation, token verification and protected token
   storage. This sample does not implement a login helper, mint tokens, carry a
   secret or exchange raw credentials. Obtain a Google **user ID token** whose
   actual aud/effective azp match the policy below. Real Google registration and
   native/browser login are unverified deployment prerequisites.
3. Set `AUTH_APPLICATION_CLIENTS_FILE=/absolute/operator/clients.json`. Example
   shape (IDs/placeholders must be replaced; choose a bounded expiry):

```json
{"schema_version":"application-client-policy-v1","bindings":[{"audience":"LOGBOOK_GOOGLE_OAUTH_CLIENT_ID","authorized_party":"LOGBOOK_GOOGLE_OAUTH_CLIENT_ID","application_id":"reading_logbook","expires_at":1800000000,"enabled":true}]}
```

4. Set `READING_LOGBOOK_MEMBERSHIP_FILE=/absolute/operator/members.json` with exact
   verified Google subject and workspace membership, independently of client binding:

```json
{"schema_version":"reading-logbook-membership-v1","memberships":[{"issuer":"https://accounts.google.com","subject":"VERIFIED_GOOGLE_SUBJECT","workspace_id":"my-shelf","expires_at":1800000000}]}
```

5. Both files must be operator-owned and inaccessible for client writes. They are
   bounded to 32 KiB, read afresh and fail closed on missing/invalid content. Use
   atomic file replacement, never partially overwrite live policy. Revocation
   disables/removes a binding or membership; signature-cache hits still recheck
   it. Expiry/token/directory/workspace are also rechecked before inference/send
   and commit. Stop/drain ingress for operational rollout/revocation; checks
   cannot cancel disclosure already made. No token or subject belongs in source
   control. The sample's static membership file is a small explicit authority,
   not a production membership-directory claim.
6. Store the short-lived user token in a private file outside this checkout
   (`chmod 600`). Never put it in command-line arguments, notes, logs or Git.
   A private deployed service also needs separately verified IAM invocation via a
   trusted gateway; the CLI does not synthesize service credentials. Configure
   `PERSONAL_AI_URL`, `PERSONAL_AI_TOKEN_FILE`, `PERSONAL_AI_WORKSPACE` for the
   endpoint reachable through that authorized deployment. HTTPS is mandatory;
   `--allow-loopback` is only for the synthetic 127.0.0.1 fixture. No environment
   proxies or redirects are followed by the client.

## Tiny CLI workflow

Use a separate local database per account. Local records and journal are private
files; they may contain sensitive text and need the user's ordinary backup policy.

```sh
reading-logbook --db /private/path/books.sqlite3 add 'A book' --note 'My private note'
reading-logbook --db /private/path/books.sqlite3 books
reading-logbook --db /private/path/books.sqlite3 start 'Book discussion'
reading-logbook --db /private/path/books.sqlite3 list
reading-logbook --db /private/path/books.sqlite3 get CONVERSATION_UUID
reading-logbook --db /private/path/books.sqlite3 preview CONVERSATION_UUID 'Explicitly chosen note text'
reading-logbook --db /private/path/books.sqlite3 ask CONVERSATION_UUID 'Explicitly chosen note text'
reading-logbook --db /private/path/books.sqlite3 recover ORIGINAL_PRINTED_OPERATION_UUID
```

`start`/`ask` journal and print their UUID before HTTP. Use `--key` to deliberately
retry the original identical operation. `preview` does not reserve/send a model
turn. Only explicit command text is uploaded; books/notes are never automatically
attached. Stderr streaming text is provisional. Exit 0 on ask means validated
terminal and matching canonical status; exit 2 means unconfirmed/denied/error and
requires the printed original key. `recover` reads status, replays only completed
turns, and leaves unknown/in-progress outcomes unconfirmed. Token refresh is
manual; retain the original journal/key when replacing the token. Never create a
new key automatically because of a timeout, 409, 429, 5xx or missing terminal.

See the [public HTTP contract](../../docs/platform-independence/consumer-v1.md)
for exact schemas, limits, errors and unavailable APIs.

## Upgrade, disable and rollback

Public host contract: `personal-ai-host-v1`; only the facade's `__all__` names are
supported. Both sample packages are version 0.1.0; the host pins core 0.1.0.
Upgrade/test artifacts in isolation before atomically changing policy/selection.
Revoke client and membership, stop/drain its ingress, unselect the host, then
uninstall host/client. Core remains healthy with no references or fifth host.
Retain platform messages/scopes, local journal, task receipts/fingerprints and
source tombstones; no schema migration or data rekeying is needed. Missing
historical task reconcilers still refuse startup. Local synthetic results do not
establish native DB/process crash durability, real identity/IAM, providers or
independent acceptance. No automatic PI-3+ or memory promotion follows.
