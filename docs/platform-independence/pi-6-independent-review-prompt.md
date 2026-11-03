# Fresh independent PI-6 review prompt

Run in a genuinely separate GPT-6.1 Sol / High session. Do not delegate or call
live services. If that exact model is unavailable, record the substitution; do
not claim an independently verified model identity from this prompt. This prompt
is review scope, not approval of the implementation or new operational authority.

Review the actual candidate on base `093e3b6816581e0b975e74e498dab99a2ac9a4b6`
plus the exact working-tree hashes in `pi-6-verification.json`. No implementation
commit is claimed. Before review, record HEAD/status and verify every source,
fixture, scoring and artifact hash. If a later commit exists, pin its SHA and
verify the manifest matches it. Preserve the untracked user handoff. Read root
AGENTS.md, docs router/current-state, PI-6 entry/hardening/plan/contract/gate,
implementation and benchmark reports, and the preserved handoff Appendix A.

Judge **conditional offline development**, not nonexistent full PI-5 acceptance.
P6-02/29 are unmet under an explicit user scheduling exception. That does not
prevent reviewing the local harness; it does prevent calling PI-5 accepted or
production promoted. Carry forward F01/F02/F03 and P5-04/11/14/19/22/26/27,
P5-24 canonical compatibility and P5-28 original input ownership. Distributed
source/attempt leases, live provider/account/privacy/cost, cloud identity/IAM,
anti-rollback/restore and physical deletion remain blocked. Do not request
accounts merely to reproduce this offline candidate.

Inspect code independently before relying on reports. Challenge requirements
outside the implementer's interpretation. In particular:

- Trace real `create_app`, JWT/client/workspace authorization, context planner,
  packer/counting, chat, retained dependencies, SSE/detail/replay, local source
  index and static tool registry. Fake only I/O, never parallel auth/orchestration.
  Confirm disabled external model context cannot be invoked through fixtures,
  fallback, retries, model tools, CLI or malicious source text. Fake generation
  is a narrow input-only consumer; it cannot prove prompt-injection resilience of
  a live model. Inspect the P19/P21 evidence boundary: fake normal profiles bypass
  physical-provider accounting and must not receive fabricated reservations.
- Reproduce foreign owner/actor/app/workspace, missing/expired identity, forged
  scope, profile grant/revision/expiry/revocation, source mutation/expiry and
  missing-validator cases. Check opaque denials and that external context
  inspection is itself denied by client policy (403), separately from R05's
  source-aware route regression. Check pre-send/count/SSE/history/summary/replay
  guards using inherited PI-5 and profile tests, not just benchmark output.
- Try malicious quote instructions, false citation and schema-valid factual
  lies, static registry replacement/unregistered tools, executable rubrics,
  manifest import/URL/path/traversal/SSRF, kill switch and resource exhaustion.
  Examine original-key changed payload, cancellation/timeout/429, unknown counter,
  lost acknowledgement, concurrent fake workers, full journal and restart-unknown
  tests. Do not perform real effects, destructive DB, restore or cloud tests.
- Scrutinize 32 cases/eight families, task semantics, normalization of empty
  required-source refusal, expected vs observed dispatches, no-source ablation,
  profile purpose/revision consent, standalone retrieval controls, citation oracle
  and source dependency retention. Verify scoring never receives gold via driver
  inputs and a schema-valid false answer cannot pass. A driver failure must not
  be hidden by a high average or by dropping its arm from the denominator.
- Audit lineage/source grouping rather than trusting unique IDs. Templates are
  shared across some splits/families: test whether the reported matched sample
  overstates independent coverage. No real-world statistical or model-quality
  claim is justified. The two source-availability wins are scripted, not measured
  model lift. Held-out memory controls and long-history/branch probes do not
  establish memory correction or summary utility. Challenge these limits.
- Verify strict content-free observations, confidence labels, unknown versus zero,
  synthetic monetary zero versus real USD, latency class/percentiles, raw text
  disposal, exception/stdout/log paths and optional emit copies. Test callback
  mutation and secret-bearing failures. Never persist prompts, outputs, profile
  values, source text/labels, credentials, auth headers or real identities.
- Recompute case/contract/scorer/runtime hashes, reject tampering/duplicate IDs,
  split leakage and unknown executable fields. Confirm no historical fixture,
  threshold, schema/migration or default changed. Inspect the additive planning
  v26 transition and unchanged v10–v25 bytes. Independently check source identity;
  do not regenerate a lock to make an unexplained failure pass.
- Run `make pi6-check`, lint, PI-2/3/4/5, platform-independence, planning/retrieval/
  memory-task evaluations and focused provider-matrix/Phase35/36/research/MEM
  tests. Run the full offline suite separately from marked loopback tests under
  native no-network. Use pinned macOS arm64 / Python 3.11.15 where available;
  report exact runtime/skips and label alternates. Verify built core wheel/sdist
  with toy/reference files physically absent and separately installed Reading
  Logbook public HTTP; a source-tree run alone is insufficient.

Use exact results from this review, including failures/reruns. The implementer's
initial moving-source runs, pre-v26 failures and corrected empty-source driver
failure remain history, not independent passes. Do not wash them out or attribute
old results to the final source. Native fences and Python-only loopback fences
are different evidence classes.

Deliver findings with severity, exact source location, executable reproduction,
impact and bounded remediation. Explicitly disposition every P6-01–33 row.
Possible verdicts: conditional offline candidate accepted, changes required, or
blocked with concrete enabled-path cause. Keep `pi5_completion=blocked_unverified`
and `pi6_production_promotion=no_go` regardless of a favorable offline verdict.
Same-session implementer self-review supplies no independent acceptance.
Stop at PI-6 review; do not begin PI-7, MEM-3+, real-model experiments, deployment
or external enablement. If fixes are needed, write a bounded remediation handoff;
separate verification/signoff remains necessary where scope changes.
