# Standalone retrieval and read-only tool contract v1

2026-10-31 local candidate; independent acceptance pending. The external consumer
OpenAPI is v1.1.0; the additive payload version is `retrieval-v1`. Existing
research-v1, conversations, PI-3 inference, PI-4 consent and memory defaults retain
their contracts. This interface does not attach evidence to chat or run a model.

Two exact authenticated operations are available when `RETRIEVAL_ENABLED=true`:

| Method/path | Result |
| --- | --- |
| `POST /v1/retrieval/query` | `RetrievalOutcome` |
| `POST /v1/tools/retrieval.query.v1/invoke` | `ToolOutcome` containing `retrieval` |

Both use the existing Google user-token/client/app/workspace middleware,
owner-rate admission, no-store and bounded correlation. No generic tool dispatch,
discovery, research inspection, account access or memory controls are exposed.
Unknown tools cannot execute. The tool additionally needs an installed application
capability with ID `retrieval.query.v1`, kind `tool`, `available=true`,
`read_only_context=true`, exact `result_fields=["retrieval"]` and
`max_result_bytes=32768`. Metadata alone cannot register executable code.

Example request:

```json
{"schema_version":"retrieval-v1","idempotency_key":"5e74567c-b01e-4dc4-b37c-b127bd2494ce","query":"Atlas","sources":["local"],"purpose":"interactive_retrieval","max_items":5,"max_quote_bytes":4096,"max_tokens":8192,"max_age_seconds":86400}
```

Unknown fields are invalid. Clients cannot submit source IDs, owners, actors,
providers, paths, arbitrary URLs, credentials, policy overrides or callables.
`query` is 1–400 characters without control characters. `sources` contains one
or both of `local` and `external`, with no duplicates. Publication lower bound
requires timezone-aware `published_after`. Optional lower-case public-domain
allow/exclude lists contain at most eight entries each. Typed/literal allowlists
intersect; excludes always narrow. Local sources have no public URL and therefore
do not satisfy public-domain filters.

Each item contains opaque source/passage/citation IDs, provider and origin,
optional legitimate external URL, title, quote and character offsets (Unicode code points), source
revision and its basis, SHA-256 of the exact quoted UTF-8 bytes, source-rights
identity/reference/epoch, license, sensitivity, observation/publication/expiry
times and freshness basis. Local quotes are exact document substrings with
`quote_basis=literal_document`; external quotes use the existing HTML-to-text
snippet extractor and explicitly say `normalized_provider_snippet`. When the
provider supplies no revision, `revision_basis=observation_hash` identifies the
snippet observation, not a live upstream revision or proof the page still exists.
Publication time is null when unknown; an observation timestamp does not prove
publication freshness. Result URLs are attribution only and are never fetched.

Outcomes are `complete`, `partial` or `unavailable`. No eligible match is complete
with empty items and `no_matches`. Foreign documents reveal no title, ID or
existence. Reasons distinguish source unavailable/changed, external unconfigured/
not admitted, original attempt unknown/already attempted, quota, timeout, invalid
source, freshness unverified, budget and busy. Source failure cannot leak raw
exceptions, operator paths, token claims or credentials. Input/auth errors retain
the common safe error envelope; changed external intent returns content-free
409 `retrieval_intent_conflict`.

All bodies are bounded by 131,072 bytes and a 10-second body read deadline.
Retrieval has a configured whole-operation timeout (default 3 seconds, maximum
10), two process slots, at most eight returned items, 8,192 aggregate quote bytes
and 16,384 conservative serialized-evidence byte tokens. Default budgets are
smaller. Items exceeding aggregate budgets are omitted without rewriting quotes
or citations and produce `partial`/`budget`. This byte ceiling is not a tokenizer
claim or model-execution admission. No model context integration exists.

## Operator installation

Use a dedicated trusted single-host directory and atomically publish a regular
(non-symlink) JSON file selected by absolute `RETRIEVAL_INSTALLATION_FILE`.
The file is at most 2 MiB, with at most 128 inline documents, 16,000 characters per
document, and 32 exact grants per access list. Do not use network filesystems,
user-writable directories or independently replicated snapshots as authority.
The whole snapshot digest is checked again immediately before disclosure; even
an unrelated edit conservatively invalidates an in-flight response. No response
body cache, persistent passages or stale snapshot reuse exists across requests.
File deletion/corruption denies. Atomic replacement is required for availability.

The executable schema is `retrieval/installation.py`. Installation-level `access`
admits an exact owner/actor/application/workspace/purpose. Every document has its
own independently exact `access` list plus `quote_allowed`, `enabled`, source ID,
revision, rights epoch/reference, license, title/text, SHA-256 of full text,
sensitivity, observed/published/expiry times. There are no wildcards or same-owner
exceptions. A profile consent grant does not grant corpus access. Only an operator
with authority over the actual source may publish this file; it is not an upload
API or a general third-party rights issuer. Increment source revision/rights epoch
on change/revocation and remove/restrict the authoritative document. All positive
lookups are request-bound. Old snapshots/backups must not be republished.

Create a new synthetic corpus, supplying the exact server-mapped owner and actor:

```sh
backend/.venv/bin/python backend/scripts/pi5_install_demo.py /private/tmp/pi5-demo/corpus.json \
  --owner synthetic-owner --actor synthetic-actor --application personal_ai
```

Create the trusted directory first. The script refuses overwrite and creates only
synthetic public text with an exact scope and a 24-hour expiry. It never ingests
conversations, memory, Reading Logbook records or user files. Its standalone scope
example is not a verified production user. Set `RETRIEVAL_ENABLED=true` and
`RETRIEVAL_INSTALLATION_FILE` to that absolute path in a local operator environment.
Regenerate/update the observation/expiry deliberately when the demo becomes stale.
For the Reading Logbook host, separately opt in with
`READING_LOGBOOK_RETRIEVAL_ENABLED=true`; real client binding and workspace
membership remain required. Client CLI: `retrieve Atlas --key <uuid> --tool`.

## External source, receipts and cost

External search is separately default-off (`RETRIEVAL_EXTERNAL_ENABLED=false`).
It also requires installation `external_query_access` for the exact scope, which
explicitly permits disclosing the submitted query to the selected operator search
adapter. Source selection reuses `RESEARCH_SEARCH_ADAPTER` and the existing search
registration factory. There is no client-selected import or provider. Source
rights and credential/policy identity are checked before dispatch and at final
output; Brave also checks the owning disclosure guard after rate wait/P19 reserve,
immediately before its fixed-endpoint request. Returned URLs are not followed.

A non-synthetic adapter requires canonical P19 accounting and canonical invocation/
physical-attempt IDs. Brave retains existing rights/prepaid/account/quota/privacy
requirements. Its current strict-free profile is **closed**. This change does not
approve it, turn on billing, replace P19 policy or supply secrets. Missing credentials
or eligibility returns unavailable without a network call; no paid fallback exists.
The configured fake adapter is explicitly `origin=synthetic`. Hermetic Brave tests
use mock HTTP and fake P19 storage and do not prove live eligibility or billing.
New operator-installed factories can be supplied to the existing registration
mapping; core does not load Python named in client requests or corpus JSON.

External execution is limited to local/test environments with an explicit absolute
`RETRIEVAL_ATTEMPT_JOURNAL_FILE` in a trusted local directory. SQLite uses private
0600 files, immediate transactions, 50 ms lock waits, and 4,096 lifetime receipts.
The receipt contains only hashed scope/request identities, key and state; no query,
source body or credentials. Reservation commits before external dispatch. No
receipt pruning, key reuse or automatic retries exist. Exhaustion refuses new
attempts; it is a known operational capacity limit. Native P19 storage, multi-host
coordination and production deployment are separate gates.

Retain the original UUID and full body. Local-only calls recompute under current
rights and are stateless. For external requests, the same key/body never issues a
second attempt, including after cancellation/restart/provider switch. Changed
body conflicts. A completed external attempt returns `external_already_attempted`
on retry, with no cached external bodies; local results may be freshly recomputed.
Lost acknowledgement or failed attempt remains `external_outcome_unknown` and must
not be rekeyed automatically. This narrow protocol does not promise successful
body replay or exactly-once provider charging. A new key requires explicit new
user intent. Canonical P19 accounting remains the cost authority.

## Rollout, rollback and limitations

Keep gates off pending independent review. Exercise only synthetic data first.
Disable `RETRIEVAL_ENABLED` and the host opt-in, drain requests, and retain receipt
files, source epochs and all existing deletion/consent/replay fences. Removing the
journal, changing its path, restoring an older snapshot or rolling back to an older
source file can resurrect authority/attempts; do not re-enable until reconciled.
Do not treat successful same-owner identity or a tool's existence as permission.
No migration or changes to research-v1 persisted data are needed.

Normal chat/context counting, model sends, SSE, summaries, history and replay do
not consume these retrieval objects. No automatic memory capture occurs. Users
can explicitly send text in a conversation, but this is fresh user-supplied input,
not governed server-side evidence integration. Source provenance cannot be
retrofitted to that text. Mandatory general context/count/send and derived-history
acceptance is **incomplete**, not a pass by absence. Remote source deletion,
anti-rollback/restore, automatic physical erasure, real identity/IAM/P19/Brave and
cloud/security acceptance remain unproven. Past transmissions cannot be recalled;
checks do not make revocation atomic with a network send. See the
[implementation report](pi-5-implementation-report.md) and
[scenario evidence](pi-5-verification.json).
