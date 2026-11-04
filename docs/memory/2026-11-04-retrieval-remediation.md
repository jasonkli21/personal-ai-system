# Memory navigation review remediation — 2026-11-04

This report addresses the independent review of `f33aec3`. The implementation
remains a default-off fixture experiment. No production source, route, model,
transport, migration, runtime registration, or durable-memory writer was added.
The original v1 corpus, manifest, measurements, and historical evidence remain
unchanged.

## Remediation

- **R01:** `FixtureAuthority` now rejects semantic, hybrid, and reranked arms as
  unsupported unless the supplied rank frame is explicitly fake-vector contract
  evidence and the test-only opt-in is enabled. A caller-created
  `origin="canonical"` frame cannot certify itself. The fake adapter contract
  remains test-only.
- **R02:** eligibility requires observation by both current time and query
  `as_of`. Corrections suppress a prior assertion only at or after the
  correction's observation time; the correction barrier remains after its later
  withdrawal.
- **R03:** reranking preserves relevance as its leading order and gives
  correction precedence only within an eligible supersession pair. Unrelated
  corrections do not receive a global rank boost.
- **R04:** hierarchical selection accepts terminal one-level topics as targets
  alongside children of mixed-depth roots.
- **R05:** dependency currentness checks the exact currently issued scope/project
  grant. Synthetic revoke and regrant operations advance issuer revision, so an
  old dependency and index remain stale after regrant. A fresh dependency can be
  issued only under the exact new grant.
- **R06:** the no-memory arm performs the same source/grant preflight but builds
  no index, packs no context, and reports zero retrieval work. Unsupported and
  failed attempts retain index work when it occurred. Result v2 separately
  records preflight, index build, retrieval, packing, consumption/final-fence,
  and total elapsed time. The v1 receipt is preserved.
- **R07:** query and content tokenization apply NFKC, normalize common Unicode
  dash characters, and match letter-number identifiers across hyphen/space
  forms without reducing the identifier to broad component terms.
- **R08:** the additive v2 replay retains the original author-visible task set
  and denominator; it does not claim a new utility comparison. Focused tests add
  an independently granted positive application/actor scope and negative
  actor isolation. The v2 study still has no completed fixed, semantic, hybrid,
  or reranked comparison, and no independently authored challenge cohort or
  blind utility result. Those comparisons remain unsupported/deferred.
- **R09:** grant revoke/reissue, stale-index rejection, and a stubbed synthetic
  pre-send fence are covered. The fence has no network or model transport and
  is not physical-send evidence. Cold authority rollback and deployed erasure
  remain external gates.
- **R10:** the study is described as author-visible and author-locked, not
  independently preregistered. The v2 source identity list includes the
  canonical builder, token counter, context contracts, memory contract, and
  client dependencies. The v1 measurement receipt remains historical.

## Additive v2 evidence

- Manifest: `memory-navigation-study-v2`, SHA-256
  `871fd335e6233981b27251d00b98d3236fdcb3667fae6a5fb944e84addbc0ba5`.
- Synthetic corpus: unchanged v1 bytes, SHA-256
  `d7cf41366fa77e01fb9480eed0d617048d9abcfd468dca014417d91492b95d7a`.
- Receipt: [v2 measurements](2026-11-04-retrieval-remediation-v2-measurements.json),
  400 attempted rows across ten arms. Replay digest:
  `36165d76638e61ffd34267b353de89cadbac264e2f4d62ba023a84f714604838`.
- No-memory reports zero index bytes/build time and zero retrieval/packing/
  consumption work. It completes 33/40 cases because three late memory
  mutation checks do not apply when the arm reads no memory. Other supported
  arms complete 30/40 (30 ordinary tasks, plus ten expected boundary outcomes).
  Fixed has 0/40 complete; semantic/hybrid/reranked each have 0/40 complete.
  The latter arms retain numeric index-attempt cost before returning
  `real_embeddings_unavailable`.
- The receipt reports only fixture-estimated token units, local synthetic
  timings and zero provider calls/charge. It establishes no model utility,
  superiority, provider cost, native persistence, live permission, physical
  disclosure, or restore/erasure claim.

## Verification and remaining gates

`make memory-navigation-check memory-navigation-eval backend-lint
naming-policy-check` passed with the pinned backend virtualenv: 57 focused tests
passed, 400 rows replayed twice, zero reported violations, and stable semantic
replay. Ruff and naming checks passed. The focused test process emitted two
upstream Python 3.11 support deprecation warnings. The broader memory/context/
offline-consolidation regression command passed 806 tests with one skip and
three upstream deprecation warnings.

`make planning-eval` still fails with the inherited
`planning_baseline_changed_requires_new_version` source-identity gate.
`make memory-navigation-postgres-check` is blocked because no disposable
`PERSISTENCE_TEST_POSTGRES_DSN` is configured; no database was contacted.

E1 synthetic remediation is recorded for the feasible source, ranking, topic,
grant, lexical, accounting, and fence contracts. The additive v2 remains an
author-visible scripted study, not independent acceptance. E2 native checks
remain blocked without an approved disposable PostgreSQL/pgvector DSN. E3 live
rights and physical disclosure, E4 cold restore/physical erasure, and E5
independent real-model longitudinal utility were not run. Production remains
**NO_GO**.
