# Memory retrieval research plan hardening — 2026-11-04

Baseline: `fe1915ec50d075eb9eba7b4d51c8d56527adc3fc`; no later commits.
The supplied MEM-5 plan is an untracked user document and remains untouched.
This note is the implementation decision for its E0/E1 slice, pending review.

- One ephemeral index owner in `memory/research/`; only a digest-pinned public
  synthetic authority can instantiate the experiment. No API, tool, setting,
  production factory, SQL table, episode reader or pending-proposal admission.
  Immutable cache metadata contains IDs/terms, never replacement source bodies.
- Adapt the existing server-built `MemoryQuery`. Bind exact owner/app/workspace/
  actor/project, current source fingerprints/epochs, public sensitivity, active
  lifecycle and retention. Missing authority denies; empty eligible results are
  distinct from denied, unsupported, incomplete, cancelled and timed out.
- Revalidate the whole bounded eligible universe before scoring, independently
  at topic/leaf reads, after builder packing and under the synthetic authority
  lock at scripted consumption. Any generation change denies, including regrant.
  This proves a simulator boundary only. A new source identity is required for
  regrant; full-authority cold rollback has no external surviving issuer here.
- Use deterministic lexical postings, bounded two-level navigation, rank fusion
  and conservative atomic conflict packing. No model rewrites, ANN, hosted
  embeddings, second RAG store or new permission system. Canonical semantic
  results need complete matching eligible-universe and embedding identities;
  missing real embeddings are unsupported, not a synthetic semantic win.
- Preserve legacy `fixed` unchanged. Schema-3-shaped project facts cannot be
  represented by that legacy comparator. Keep its denominator and unsupported
  reason. Fake-vector fusion is a separate contract test, never benchmark data.
- Packing policies only narrow the canonical builder policy. Fit required current
  sources first and never increase any ceiling. All arms use the same serializer,
  offline counter, task input, clock and total budget. Eligible full context must
  fit completely or is unsupported, rather than silently truncated.
- Pre-register an additive 40-case author-visible corpus, scorer and arm manifest
  before running it. Report scripted exact-answer/attribution outcomes, abstention,
  false support, leaks, retrieval metrics, counted tokens and latency separately.
  There is no blind holdout, model utility, paid usage or promotion claim.
- Caps: 128 records, 256 KiB serialized corpus/index, 4 KiB/record, 128 terms/
  record, 64 characters/term, 32 topics, two path levels, 8 leaves/page, one extra
  page, top-K <=16, query <=2 KiB, <=2 seconds/request, <=5 seconds/lease,
  memory <=1,024 tokens and global <=4,096 tokens. Overflow fails explicitly.
- Native tests exercise existing canonical pgvector/lifecycle behavior feeding a
  disposable derived index; no persistence of this cache is justified at this
  size. Native execution requires a disposable DSN. Do not reinterpret existing
  PostgreSQL or fake evidence as a fresh native run.

Inherited v35 source-lock failure, missing production issuers/local model,
restore/physical erasure, independent acceptance and all release NO_GO statuses
remain open. New source drift will be recorded with an additive proposal rather
than rebinding a frozen lock. No production integration or model send is authorized.
