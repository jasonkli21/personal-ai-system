# Code quality and context assessment — 2026-10-14

This is an implementation assessment for independent review. The reproducible
[archived inventory](archive/2026-10-14/evidence/source-inventory.json) compares fixed baseline revisions with
current tracked/task files. It excludes ignored private files and the named
unrelated user documents. Run scripts/inventory.py with Python≥3.12. Metrics are
bytes and nonblank physical lines, not statements or a universal quality score.

## Improvements and limits

Shared closed wire/verifier, source transport/settings/status and checked generated
consumers remove repeated security semantics. Health's handwritten signed verifier
was replaced by the canonical verifier. Finance command creation moved to its
domain service; Travel/Health source creation remains in cohesive services.
Routes/UI are thin and gated. Domain effect logic uses Shopping's normal project
commands and one atomic receipt rather than parallel validation/write machinery.
Task tests separate source hosts, TLS listeners, setup and behavioral cases.
Setup finalizers close resources on failure. This improves bounded reasoning
without claiming a whole-repository rewrite.

PAI's default current-state context fell from about 63 KB to about 6 KB; its router
fell from about 28 KB to about 4 KB. Detailed history is preserved with rebased links.
Each app has one concise living status plus dated evidence. Generated API/wire
artifacts are marked, regenerable and kept out of the handwritten-source category.
Historical plans/reviews are optional context, not current delivery evidence.

Not every repo has fewer total lines: the task/recovery capabilities add code.
The relevant simplification is shared semantics and clearer ownership, not line
deletion. Large existing modules/tests and frozen artifacts remain maintenance
debt. No evaluation case or immutable financial/health/travel history was removed.
No hard constraint, owner/revision guard or unknown-value rule was relaxed to pass.

## Largest remaining handwritten areas

| Repo | Examples and nonblank lines | Assessment/next bounded extraction |
| --- | --- | --- |
| PAI | iterative research service 2172; provider matrix runner1602; context sources test2792; native persistence test1584 | Separate attempt/evidence/state orchestration and evaluator observations under existing behavior coverage; preserve frozen source/version acceptance |
| Shopping | product execution1068; Discover796; conversation API test919; web app test767 | Extract cohesive view-model/research-stage responsibilities and reusable test setup; keep user draft/retry flow intact |
| Finance | transaction domain1629; recovery archive1487; Stage5 research test797; core schema test721 | Preserve Decimal/provenance/idempotency and recovery manifests; extract domain/view-model boundaries, not arbitrary UI fragments |
| Travel | trip exports1406; Personal AI client1126; proposal lifecycle test1140; secure source test912 | Keep export/provenance/timezone and private-data boundaries explicit; split format/contract responsibilities with parity evidence |
| Health | persistence models1339; analytics artifacts1226; account data test688; daily domain test685 | Cohesive schema/domain extraction and shared synthetic setup without hiding ownership, temporal identity or lifecycle semantics |

Counts are a baseline comparison aid; generated files and full largest-file tables
are in the archived inventory. Existing source-heavy debt is retained explicitly and does
not count as completed aggressive whole-repo decomposition.

## Re-review fixes — 2026-10-14

This pass made only changes that support F1–F3. The execution-authority callback
now has an explicit documented linearization point, with deterministic tests
that revoke a grant, source consent, or source owner after the successful
callback. Shopping also verifies that its owner lifecycle lock fences a
concurrent purge until the authorized effect and receipt commit. A bounded
read-only project-choice contract removes manual UUID/revision entry from
Finance, Travel and Health while leaving Shopping as the authority.

Travel and Health now keep source-command creation, submission, confirmation,
and possible destination effect in distinct recovery phases. Travel uses
owner-scoped session recovery; Health uses owner-scoped SecureStore records and a
serialized storage helper. Focused UI/render and state-transition tests cover
the specified ambiguous and definitive failures. No unrelated large module or
test suite was split; the hotspot priorities above remain unchanged.

## Large generated/frozen artifacts

PAI's adaptive observations, Phase36 receipts/matrix and held-out context fixtures
remain frozen semantic evidence. Finance/Health/Shopping generated public API
contracts and dependency locks remain outputs of owning generators. The inventory
is generated diagnostic metadata, not runtime input. Do not compact or refresh
frozen artifacts blindly: a representation/source change needs a deterministic
generator, complete case parity and reviewed version/freeze evidence. Existing
raw stabilization JSON now sits under `archive/2026-10-14/evidence/` and is outside
the default documentation route; the current verification record retains the
reproduction commands and digest summary.

## Direct answers for the separate reviewer

- Simpler without lost capability: shared task/verifier semantics and clearer
  source ownership; total suite size increased and legacy monolith debt remains.
- Boundaries clearer: PAI orchestration, domain source facts and Shopping effects
  have explicit contracts, code paths and native evidence.
- Large files reduced/justified: current documentation and new shared logic are
  smaller; legacy large source/test/frozen artifacts are retained with priorities.
- Duplicate setup reduced: common source transport/settings/status and dedicated
  host/TLS fixtures; old domain test duplication is not globally eliminated.
- Generated artifacts separate: source-hash headers, byte equality checks and
  per-app OpenAPI/client regeneration remain executable.
- Comments explain semantic edges: uncertainty/no resend, actual auth time,
  retained receipts, erasure/restore, SQL cycle and immutable freezes.
- Traceability/context: router → current state → owning contract/service/tests;
  separate handoff contains cross-repo paths, commands, limitations and roadmap.
- Documentation consistency: new dated evidence supersedes baseline local-check
  gaps while preserving historical/external gate distinctions. Independent final
  review still needs to validate these claims against the actual diffs.
