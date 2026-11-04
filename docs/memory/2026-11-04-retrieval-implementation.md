# Memory navigation research implementation — 2026-11-04

Baseline: `fe1915ec50d075eb9eba7b4d51c8d56527adc3fc` on `main`.
This author implementation receipt describes the single subsequent implementation
commit; its exact identity is supplied in the handoff. No independent acceptance,
production activation, deployment, hosted send or private data use is claimed.
All release profiles remain **NO_GO**. No subagents were used.

## Decision and delivered boundary

The [in-session hardening decision](2026-11-04-retrieval-plan-hardening.md)
preceded code. The supplied untracked MEM-5 plan remains untouched. The planned
study grew from a minimum of 30 to **40** pre-registered public cases, all
visible to the author. There is no independent holdout. No SQL cache is justified:
the measured scoped index is at most **8,209 bytes**, with millisecond-scale
synthetic construction; caches are discarded and rebuilt.

`backend/src/personal_ai/memory/research/` owns one sealed, ephemeral index and
immutable query/index/result contracts. `ResearchQuery` adapts `MemoryQuery`,
without becoming a source of grants. Only the concrete hash-sealed fixture
issuer can instantiate the enabled research path. It is disabled by default,
with no production factory, setting, route, tool, scheduler or model callback.
Legacy `MemoryRetriever`/`KnowledgeService`, repository schemas, migrations,
episode hard-disable and pending-proposal semantics are unchanged.

The implementation includes normalized lexical terms, sanitized two-level topic
navigation, independent leaf reads, exact metadata/time/revision filters,
canonical semantic-result adaptation, reciprocal rank fusion, correction-first
conservative reranking, and atomic contradictory evidence. Canonical semantic
adaptation checks complete eligible-universe identity, scope, content fingerprints,
finite scores and full embedding space. Existing retriever output is exercised in
a fake-vector contract test. This does not supply real embeddings to the study.

Every ranking universe is filtered before ranking. Fetch, packing, and the last
supported scripted consumption independently revalidate source/permission/record
fingerprints, current epochs, lifecycle, retention and scope. Consumption runs
under the simulator's mutation lock and checks packed cards against original
sources. Regrant cannot rehabilitate a terminal source identity. Cache generation
also includes an authority-instance nonce: old-process indexes and dependencies
fail closed, even if public fixture content is unchanged. That is cache invalidity,
not authentication of a cold-restored issuer. Public fixture bodies remain in the
fixture and simulator after purge; no private-data physical erasure is claimed.

Packing uses only `ContextBuilder`, original source refs, permission dependencies,
historical authority/sensitivity and existing hard ceilings. Required current
context fits first. Fixed, request-aware and adaptive allocations only reduce
memory ceilings. Full eligible context must fit completely. Bounds are 128 fixture
records, at most 100 eligible candidates (or the smaller canonical query cap),
256 KiB corpus/index, 4 KiB/record, 128 terms/record, 64 characters/term, 32 topics,
two levels, eight leaves/page and at most one extra page, top-K <=16, 2 KiB query,
two-second original request deadline, <=5-second lease bounded by that deadline,
1,024 memory and 4,096 total fixture token units. Full context may exceed top-K.
Unknown rights/issuer, overflow, unsupported, timeout and cancellation are explicit.

## Study identities and retained measurements

- Corpus: `memory-navigation-corpus-v1`, SHA-256
  `d7cf41366fa77e01fb9480eed0d617048d9abcfd468dca014417d91492b95d7a`.
- Manifest: `memory-navigation-study-v1`, SHA-256
  `56e8f0b96edb64b3b612479b4ce6368c48776f3e8663af789d6691c5a479ab7f`.
- Policy: `bounded-navigation-v1`; scorer: `exact-scripted-answer-v1`;
  serializer: `source-card-json-v1`; counter: `fixture-word-estimate-v1`.
- Semantic replay digest across two complete runs:
  `49ebdf72adf5a8cc4a0c225740079f6681a3128d5fe28f3b83dcc5a1b48f8b6d`.
  Timing and ephemeral generation nonces are excluded; statuses, selected/packed
  identities, answers, attribution, token counts and scores must match.
- [Retained machine-readable receipt](2026-11-04-retrieval-measurements.json)
  includes all **400 attempted rows**, code/policy/scorer hashes, environment,
  failures, cancellations, timeouts, denials, unsupported rows and family deltas.
  Source/fixture/manifest mutation during execution fails the run. Unexpected
  exceptions retain a failed row and fail the CLI.

Environment: CPython 3.11.15, macOS 27.0.1 arm64, existing backend virtualenv.
All arms share grants, source/currentness preflight, serializer, task text, clock,
4096/1024 context/memory ceilings, output ceiling declaration 128 and two-second
request deadline. There is no generated output or model to meter. The scripted
consumer receives only serialized cards and query text, never the rubric/source.
Latency includes common index/preflight overhead even for no-memory/full-context;
it is not a production serving latency comparison. All token counts below are
actual builder counts in **estimated fixture word units**, not provider tokens.
Real usage and model quality are unmeasured; provider calls and charged cost are
zero, classified `offline_no_charge`.

| Arm | Complete / all cases | Script answer/status correct among complete | Critical leaks | Mean packed units | Mean lookup/run ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| no_memory | 30/40 | 7/30 | 0 | 14.17 | 8.30 |
| fixed | 0/40 | unmeasured | n/a | n/a | 1.39 |
| lexical | 30/40 | 29/30 | 0 | 55.90 | 9.40 |
| semantic | 0/40 | unmeasured | n/a | n/a | 1.40 |
| hybrid | 0/40 | unmeasured | n/a | n/a | 1.40 |
| hybrid_reranked | 0/40 | unmeasured | n/a | n/a | 1.40 |
| topic_hierarchical | 30/40 | 29/30 | 0 | 55.90 | 22.31 |
| request_aware | 30/40 | 29/30 | 0 | 55.90 | 9.39 |
| adaptive | 30/40 | 29/30 | 0 | 55.90 | 9.40 |
| eligible_full_context | 30/40 | 29/30 | 0 | 154.43 | 11.72 |

Supported arms also get **10/10** expected boundary outcomes: five scope denials,
three late mutation denials, one cancellation and one expired request. Fixed and
semantic variants each have **33 unsupported + seven preflight boundary rows**;
their three late mutations cannot execute after the unsupported operation. Those
seven outcomes do not establish retrieval quality or comparative safety.
Legacy fixed cannot represent these project facts. Semantic/hybrid/reranked have
no genuine embedding source/runtime. Adaptive/request-aware therefore use lexical
recall, explicitly, rather than claiming a hybrid benchmark. Separate fake-vector
contract tests exercise the integrated fusion/rerank implementation.

Lexical/adaptive mean retrieval recall is 0.9565 and mean precision 0.8030 on
applicable complete rows; exact attribution is 29/30, false support zero. The
unmatched paraphrase abstains rather than inventing support. Full context also
abstains on that paraphrase: this narrow script cannot establish semantic/model
utility. Full context fits this small corpus and is a valid stronger coverage
baseline, with the same answers and larger packed context. Packing policies do
not improve quality/token counts on these small cases; no adaptive advantage is
claimed. Topic navigation adds overhead. There is no promotion/Pareto acceptance.

Per-family paired deltas against no-memory are retained with sample counts and
population SD. For lexical: transfer (n=4), identifier (n=4), correction (n=2),
conflict (n=2), topics (n=3), repeats/negation/poison/full-context (n=1 each) gain
1.0 scripted success; metadata/paraphrase/regrant (n=2 each) gain 0.5, SD 0.5.
Safety/absence families gain zero. No confidence intervals or generalization
claims are justified by these small, correlated, author-visible tasks.

## Verification

Commands use the existing virtualenv: prefix Make commands with
`PATH="$PWD/backend/.venv/bin:$PATH"` from repository root. Full raw local logs
are in `/tmp/navigation-*.log`; the table preserves results independently.

| Command | Result |
| --- | --- |
| `make memory-navigation-check` | PASS, 49 tests; final replay included |
| `make memory-navigation-eval` | PASS, twice-replayed 400 rows, zero critical leaks; unsupported rows retained |
| `cd backend && .venv/bin/python -m pytest -q tests/test_memory*.py tests/test_context*.py tests/test_offline_consolidation.py tests/test_consolidation_adversarial.py --ignore=tests/test_context_manual.py` | PASS, 798 passed, one skipped, 28.78s |
| `make memory-eval memory-optimization-eval memory-knowledge-eval memory-knowledge-causal-eval memory-control-eval memory-consolidation-check memory-consolidation-eval context-eval context-plan-eval naming-policy-check` | PASS; consolidation check 107 tests; naming checker plus two tests |
| `make memory-lifecycle-eval` | PASS |
| `make backend-lint` | PASS |
| `make planning-eval` | FAIL, preserved `planning_baseline_changed_requires_new_version` |
| `make backend-test-offline` | FAIL collection, SDK not on import path |
| same target with SDK source `PYTHONPATH` | FAIL collection, Checklist package not on import path |
| same target with SDK + Checklist client/host source paths | FAIL: 2,633 passed, one skipped, 180 deselected, 36 failed, 92 setup errors; 224.25s |
| `make memory-navigation-postgres-check` | BLOCKED: no disposable `PERSISTENCE_TEST_POSTGRES_DSN`; target now fails explicitly rather than reporting skipped tests as acceptance |
| earlier underlying canonical pgvector / knowledge commands | 2 + 9 native tests skipped, 23 other native cases deselected; no E2 pass claimed |
| `cd backend && .venv/bin/python -m personal_ai.evaluation.consolidation_quality --local-preflight` | BLOCKED, `local_profile_not_configured`; no send |
| Network-fenced offline subset | PASS, 2,605 passed, 279 deselected, 233.15s; zero forbidden network attempts |
| Changed-document local links, historical fixture preservation, `git diff --check` | PASS, 96 local links; all 12 historical memory fixture files byte-preserved; no whitespace errors |

The composed broad command sets
`PYTHONPATH="$PWD/sdk/python/src:$PWD/examples/project-checklist/client/src:$PWD/examples/project-checklist/host/src"`.
Its failures are PI-6 frozen identity mismatches, the v35 planning identity
assertion, and loopback `PermissionError: Operation not permitted`. No new
navigation test failed. The failed original gate is not replaced by the passing
subset. No tests or release gates were loosened.

The network-fenced diagnostic command (from `backend/`) is:

```sh
PYTHONPATH="$PWD/../sdk/python/src:$PWD/../examples/project-checklist/client/src:$PWD/../examples/project-checklist/host/src" .venv/bin/python scripts/offline_test_runner.py -q -m 'not persistence_integration and not cloud_smoke and not loopback_http' --ignore=tests/test_gemini_manual.py --ignore=tests/test_context_manual.py --ignore=tests/test_external_consumer_http.py --ignore=tests/test_pi6.py -k 'not test_current_planning_lock_binds_owner_portability_source_without_promoting'
```

## Remaining gates and rollback

| Status | Dependency / owner / exact next action |
| --- | --- |
| DONE E0/E1 author candidate | Local implementation, adversarial contracts and measured scripted study; independent reviewer must assess it |
| PARTIAL: genuine semantic and fixed comparators | Canonical issuer + compatible real embeddings / source owner; supply representable accepted legacy records and pinned local embeddings, retaining unsupported denominators until then |
| BLOCKED native E2 | Operator supplies disposable local PostgreSQL/pgvector DSN with CREATEDB; run `make memory-navigation-postgres-check` and independently reproduce canonical revocation/erasure results; this does not itself add a native research source adapter |
| BLOCKED runtime source / final model send | Host/source owners supply reviewed issuer, lease and physical-send fencing; keep experiment disconnected until then |
| BLOCKED actual model utility | Operator supplies pinned local model/build, private socket and usage store; no arbitrary download/installation or hosted fallback authorized |
| BLOCKED source identity | [Additive generation proposal](2026-11-04-retrieval-source-proposal.json); reviewer verifies exact bytes before any new accepted planning lock; preserve v35 and PI-6 failures |
| NOT_RUN E3/E4 | Source/deployment owners must authorize and evidence live rights, source erasure, cold issuer rollback protection and backup/replica/physical deletion |
| NOT_RUN E5 / independent acceptance | Independent Sol High review next; future independent task author supplies blinded longitudinal real-model tasks |

MEM-3 issuers/read enablement, MEM-4 automatic admission, real private histories,
cloud/backup restoration and production rollout remain inherited gates. No part
of this candidate grants them authority. Production remains **NO_GO**.
Rollback: disable explicit research construction and discard derivative caches.
No canonical source, immutable identity, migration, correction or old reader needs
reverting.

## Independent review handoff

Review the single implementation commit identified in the final handoff, starting
with `research/{contracts,source,index,semantic,engine}.py`, both new test modules,
the additive corpus/study manifest and this receipt. Run the focused target,
replay evaluator, owning regression command and naming/lint commands above;
preserve planning/full-suite failures and native BLOCKED status. Challenge source
scope/currentness at all boundaries, cache instance/generation and cold restore
claims, fake-vector isolation, conflict atomicity, budget invariants, scripted
scoring assumptions, identical preflight overhead and small-corpus packing claims.
The dated measurements bind exact implementation hashes. The untouched untracked
planning documents belong to the user and are not part of the commit.
Independent Sol High review is pending; Luna High/XHigh remediation and final
verification follow that review, with no further review claimed after Luna.
