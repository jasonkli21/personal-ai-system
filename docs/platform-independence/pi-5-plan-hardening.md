# PI-5 pre-code critical review and hardened plan

Recorded 2026-10-30 America/Los_Angeles (2026-10-31T05:32Z), before runtime edits.
Entry `e5412a85e58fdf0a9d7b58d1361a23b37e477190`, branch `main`; no tracked
changes. Eighteen untracked user documents, including the original PI-5 plan and
prompt, are input and will not be edited or staged. Python 3.11.15, uv 0.11.13,
macOS arm64; existing offline environment. No subagents or separate sessions.
The user's direct request authorizes implementation and one local commit; the
attached prompt/plan supply requirements, not higher-priority operating authority.

## Findings and authority graph

- `auth/middleware.py` verifies Google claims, resolves owner/actor, checks the
  installed application/workspace authority, binds a current-client callback,
  limits external POST bodies, admits request rate and adds no-store/correlation.
  `auth/application_clients.py` permits only exact conversation routes today.
- `api/research.py` and `api/iterative_research.py` compose research repositories,
  inference and `search/runtime.py`. Research sessions persist observations,
  attempts, citations and synthesis; detail, inspection, export and SSE are egress.
  They are intentionally unavailable to external clients. Do not expose them.
- `evidence/contracts.py` accepted observations require canonical public URLs,
  public sensitivity and external/synthetic origin. `pipeline.py` normalizes
  extractive passages; its fingerprints and research-v1 storage must not change.
- Search composition already accepts an operator-supplied registration mapping.
  Brave fetches snippets only from its fixed endpoint; URLs are never fetched.
  `SearchOperation` preserves literal query/domain restrictions. Brave calls P19
  before its physical HTTP request; current configured Brave profile has
  `strict_free_enabled=False`. PI-5 must not turn that into approval. Credential
  possession, prepaid claims and an estimated zero price do not prove eligibility.
- Context authorization, assembler counting, LLM disclosure guards/reservations,
  summary snapshots and persisted message attribution form a separate graph.
  PI-4 external detail/replay quarantine is essential. There is no general local
  corpus source issuer/lease or retained retrieval-context provenance today.
- Capability manifests describe tools; they do not bind executable code.
  Reading Logbook is separately packaged with real signed-HTTP test middleware
  and client-only installed-artifact checks. Core must have no logbook branches.

## Eight design answers and plan corrections

1. Add separate closed `retrieval-v1` models. Do not change research observations,
   fingerprints, records, evaluator fixtures or historical locks.
2. Clients may choose only `local`, `external` or both. No corpus IDs, paths,
   providers, credentials, rights flags or arbitrary URLs. Operator file grants
   exact owner/actor/app/workspace/purpose access; no same-owner shortcut.
3. An atomically replaced, bounded operator installation JSON is authoritative
   for local snapshot bodies/revisions/rights/expiry and exact scope admission.
   Re-read and compare its digest at preflight and final serialization. It is
   shared-file, single-host authority, not a distributed source service. Missing,
   changed, deleted, symlinked or corrupt authority denies. Multi-host publication,
   backup anti-rollback and automatic physical erasure remain production gates.
4. Use two exact POST routes: `/v1/retrieval/query` and
   `/v1/tools/retrieval.query.v1/invoke`. No generic URL/path/callable dispatch or
   tool list enumerating hidden metadata. The tool additionally requires selected
   operator installation and matching installed app read-only capability metadata.
   Its only executable binding is the same retrieval use case.
5. Add content-free SQLite original-intent receipts for external attempts on a
   single host. Commit reservation before dispatch; concurrent/restarted retries
   never resend or return cached bodies. Same key with changed input conflicts;
   lost completion remains unknown. Lifetime capacity refuses new attempts rather
   than pruning fences. No claim of exactly-once charging or distributed ledger.
   Missing ledger makes external execution unavailable. No remote automatic retry.
6. General model-context integration is intentionally unavailable: no retrieval
   provider registration, model calls, summary/history writes, SSE or response
   cache. Test that tool invocation cannot enable these paths. Thus mandatory
   context/count/send/derived-history coverage remains incomplete, not vacuously
   passed. API citations are observations, never durable memory/instructions.
7. Add only exact route/method pairs to the external allowlist and OpenAPI subset;
   regenerate/check it and extend the independent client and installed proof.
8. No canonical-store migration is needed. SQLite receipts are explicit local
   operational state, with local/test-only execution. Real Brave remains subject
   to existing closed P19 admission; current profile is not promoted. Live source
   deletion verification, distributed authority/ledger, production store recovery,
   real identity/billing and context integration require separate acceptance.

## Threat model and stronger criteria

Foreign and same-owner app/workspace probes receive identical empty/ unavailable
responses without titles or IDs. Exact actor is required. No implicit profile
share, filesystem ingestion, dynamic imports, page fetch, paid fallback, model
host or memory side effect. Source text, including instructions/tool names, stays
an exact literal quote. Public external attribution is canonicalized and domain
intersection cannot widen. Quotes bind source, revision, rights epoch, hash and
expiry; any final authority change removes all bodies. External errors are a
closed vocabulary; exceptions/paths/secrets cannot be serialized. Published time
unknown is explicit; current-only searches cannot invent publication freshness.

Budget the whole request: bounded source selection, query, documents, file bytes,
result count, UTF-8 quote bytes, conservative byte token upper bound, response
bytes, deadline and process concurrency. Existing middleware adds owner rate
limits; external cost admission remains P19. Receipt reserve conflicts and quota
failure must precede network. Final response guard rechecks current client and
installation immediately before serializing. No callback can recall already sent
bytes; atomic external disclosure/revocation is not claimed.

## Ordered implementation and verification

1. `retrieval/contracts.py`, `installation.py`: additive DTOs, exact grants,
   bounded inline local corpus and deterministic lexical inverted index.
2. `retrieval/journal.py`, `external.py`, `service.py`: durable attempt fence,
   existing selected search registrations/Brave, domain policy, final revalidation,
   safe outcomes and aggregate bounds. Keep all old research paths unchanged.
3. `retrieval/tools.py`, `api/retrieval.py`, settings/main/auth allowlist: default
   off, explicit executable registration, authenticated thin endpoints.
4. Consumer OpenAPI/client/optional host manifest and isolated artifacts: signed
   loopback HTTP, no private imports, physical toy absence. No live secrets.
5. Adversarial tests: cross-scope, corrupt source, revision/rights races, expiry,
   restart/replay/concurrency, malformed tools, inert injection, URL/domain safety,
   P19 denial, deadline/partial/429 and no forbidden network.
6. Run PI-1/2/3/4 and research/retrieval/offline/lint checks as practical; compare
   known matrix failures and source-binding guard failures honestly. Do not refresh
   frozen planning locks to conceal source changes. Inspect every diff and callers;
   write P5-01–28 evidence, status and rollout limits; one explicit local commit.

A17/A18 and PI-5 full completion remain unmet unless their mandatory scenarios
are proven. This candidate can deliver useful standalone local retrieval and an
executable tool without claiming model-context, live Brave or production safety.
Independent PI-0–5 acceptance remains pending. MEM-3+ stays frozen.

## Post-code source-binding note (not part of the pre-code review)

The first installed check correctly rejected changed runtime bytes under v23
(`planning_baseline_changed_requires_new_version`). PI-5 appends a separate v24
source-only lock against the entry revision. All v10–v23 bytes, held-out corpus,
fixture dependencies, planner configuration and non-promotion remain unchanged.
The v23 preservation assertion now reads the historical v23 file and pins its
original digest; a new v24 assertion checks current source. This is an explicit
new source binding, not a waived guard, refreshed historical lock, changed count
or new experiment. The original pre-code findings above are retained unchanged.
