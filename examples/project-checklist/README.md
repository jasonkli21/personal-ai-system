# Project Checklist

An independent SQLite checklist and HTTP-only SDK consumer. The optional
operator-trusted host supplies conversation history policy and a single
workspace membership, and leaves checklist records on the client.

## Credential-free quickstart

From the repository root, with the prepared build environment:

```sh
UV_OFFLINE=1 make hxe0-installed-check
make hxe0-check
```

The installed test runs the CLI's local `add`, `finish` and `preflight`
commands. The signed ASGI canary uses ephemeral test keys, the production
verifier and fake persistence/model ports. It exercises the SDK without a
network listener. Example preflight receipt:

```json
{"contract_supported":"1.2.0","token_configured":false,"workspace_configured":false,"remote_authority":"unverified","retrieval":"unavailable","memory":"unavailable","evidence":"E0"}
```

After installing the SDK and Checklist client wheels into your own virtual
environment, run `project-checklist --db /path/to/local.sqlite add "Check the drawings"`
and `project-checklist --db /path/to/local.sqlite items`. The database contains
local records and any explicitly prepared turn bodies. Keep it private.

## Operator test configuration

1. Install the host wheel into the server environment and explicitly select
   `project_checklist` in the existing application contribution settings.
2. Set `PROJECT_CHECKLIST_MEMBERSHIP_FILE` to an absolute path. Its JSON object
   has `issuer`, `subject`, `workspace_id` and integer Unix `expires_at`.
   For the synthetic fixture the issuer is `https://accounts.google.com`,
   the subject `synthetic-owner` and workspace `site`. Supply a future expiry
   in the isolated test. The host rereads this file on each check.
3. In the existing [operator client policy](../../docs/platform-independence/consumer-v1.md),
   bind the approved audience and effective authorized party to
   `project_checklist` with a current expiry. Set `CHECKLIST_USER_ID_TOKEN`
   in the client environment to the caller's ID token. Synthetic fixtures are
   for local verification.

Use identical base URL, workspace and database options for each CLI command.
`create KEY TITLE` takes a UUID and title you have already journaled.
`conversations` lists and `detail CONVERSATION` reads within current scope.
`prepare CONVERSATION` reads explicit turn text from stdin and prints the
journaled key. `send KEY` claims one initial dispatch. After an ambiguous
observation, `recover KEY` reads status and only replays a canonical completion
using the stored body and key. A crash after the claim but before dispatch can
leave the original key unobserved. The journal preserves it for reconciliation.

The CLI never uploads checklist records automatically. Host installation alone
confers no client or source authority. Consult the [evidence matrix](../../docs/harness-excellence/README.md)
for the installed-preview and production gates.
