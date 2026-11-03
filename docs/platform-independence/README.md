# Platform Independence — Documentation Index

**Intended repository path:** `docs/platform-independence/`  
**Initial review base:** [`8571a8af33969f249614c2652a7d29c0c686f2d8`](https://github.com/jasonkli21/personal-ai-system/commit/8571a8af33969f249614c2652a7d29c0c686f2d8), October 30, 2026.  
**Status:** bounded PI-0 architecture/documentation/static diagnostics implemented locally; independent post-implementation acceptance is **pending**. Review remediation is recorded separately in the [2026-10-30 remediation evidence](pi-0-independent-review-remediation-2026-10-30.md). PI-1 is an implementation candidate pending independent review; PI-2 is a user-directed local implementation candidate pending independent review; PI-3 is a user-directed local candidate pending independent review; PI-4 is a user-directed local profile-consent candidate pending independent review; PI-5 is an incomplete standalone retrieval/tool candidate pending independent review; PI-6 has a locally complete scripted offline evaluation and a closed 2026-11-02 remediation review with no further review required at the user's direction; production promotion remains no-go. PI-7 is a synthetic local operations candidate pending independent review. PI-8 remains undelivered. See the [implementation report](pi-0-implementation-report.md) for original-baseline checks and worktree caveats.

`personal-ai-system` is to become an application-independent, mostly-free AI harness. Travel, Shopping, Health, and Finance are **optional toy/reference clients**, not core platform requirements. Feature development for the separate memory program is **frozen at MEM-2**: preserve default-off MEM-0/1/2 and their outstanding acceptance gates; MEM-3+ requires a separate explicit unfreeze.

## Read in this order

1. [Platform Independence Charter & Phased Roadmap](platform-independence-roadmap.md) — first-principles product direction, current assessment, invariants, ownership, freeze and PI-0 through PI-8 implementation plan.
2. [PI-0 Independent Architecture Review](pi-0-review.md) — evidence-backed findings, code paths, risk classification and review limitations; **not** a completed post-implementation review.
3. [PI-0 Sol Medium/High Codex Handoff](pi-0-sol-codex-handoff.md) — standalone implementation instructions and acceptance checks for PI-0, suitable for direct use in one Codex session.

## Source-of-truth boundaries

The owning repo's `AGENTS.md`, code/tests/migrations, [`docs/current-state.md`](../current-state.md), historical memory records under [`docs/memory/`](../memory/), and stabilization evidence are authoritative for implemented behavior and gate status. The PI roadmap is a **future implementation plan**, not a declaration that PI-1–8 or production memory capabilities are delivered.

## PI-0 baseline outputs

- [Architecture decisions and ownership](pi-0-architecture-decisions.md) — committed constraints and provisional extraction/provider/sharing choices.
- [Dependency inventory and guard](pi-0-dependency-inventory.md), [machine records](pi-0-dependency-inventory.json), [exact import waivers](pi-0-import-waivers.json) — static and dynamic/default composition, flags and historical obligations.
- [Later-phase exit contract](pi-0-exit-contract.md) — PI-1 physical absence and PI-2 separately installed consumer proof, plus provider/privacy/replay gates.
- [Implementation evidence](pi-0-implementation-report.md) — source identity, preservation, executed checks and remaining review.
- [Independent review remediation](pi-0-independent-review-remediation-2026-10-30.md) — R01–R03 dispositions, updated guard evidence and residual limits.

## PI-1 candidate

- [Detailed plan](pi-1-detailed-implementation-plan.md) and [pre-implementation hardening](pi-1-plan-hardening.md).
- [Implementation report](pi-1-implementation-report.md), [current import inventory](pi-1-dependency-inventory.json), and [verification commands](pi-1-verification-commands.md).
- [2026-10-30 review-remediation evidence](pi-1-review-remediation-2026-10-30.md) — reproduced findings, code and CI corrections, local offline checks, artifact identities and remaining acceptance.
- [Independent-review instructions](pi-1-independent-review-prompt.md); no verdict supplied by the implementer.
- [Optional package operations](../../reference-apps/README.md).

PI-0 independent acceptance remains pending. The roadmap and exit contract retain all gates. This index does not supersede memory security or production acceptance.

Do not move or duplicate the historical MEM/Chapter2 evidence into this folder. Link to those records and preserve their version and provenance.

## PI-2 external consumer candidate

- [Same-session plan hardening](pi-2-plan-hardening.md), including the PI-0/1 gate exception and threat model.
- [Implementation/verification report](pi-2-implementation-report.md), observed limitations and artifact identities.
- [2026-10-30 independent-review remediation evidence](pi-2-review-remediation-2026-10-30.md), fixes, fresh offline checks and remaining acceptance gates.
- [External v1 HTTP contract](consumer-v1.md) and [generated OpenAPI subset](consumer-v1.openapi.json).
- [Independent Reading Logbook quickstart](../../examples/reading-logbook/README.md), operator identity/membership policy and rollback.
- [Separate independent-review prompt](pi-2-independent-review-prompt.md); self-review supplies no independent verdict.

The new client does not grant access to global profile, app-private memory, tasks,
account administration or gated external turns. Existing MEM-0/1/2 flags, schemas,
source/actor fences, receipts and fixture/lock history remain preserved. PI-2 v20
and remediation v21 are source-only planner rebinds with no promotion. Real identity/IAM, providers,
native storage recovery, Linux/Python 3.12 CI and independent acceptance stay open.


## PI-3 provider-neutral execution candidate

- [Pre-code plan hardening](pi-3-plan-hardening.md), source audit, counter/cost decisions and inherited gate exception.
- [Implementation, self-review and P3-01–P3-20 evidence](pi-3-implementation-report.md).
- [2026-10-30 independent-review remediation evidence](pi-3-review-remediation-2026-10-30.md).
- [Machine verification record](pi-3-verification.json).
- [Operator and adapter instructions](../../backend/src/personal_ai/llm/README.md#pi-3-explicit-execution-profiles).

Normal API composition supports two credential-free fake identities and an
explicitly approved strict-free legacy Gemini profile through the same neutral
ports. Unsupported remote counters, new embedding work and paid modes deny.
Existing vector identities, MEM-0/1/2 semantics/flags, PI-2 v1, original keys,
external SSE fences, tasks and Phase36 gates remain intact. v22 is a source-only
non-promoting planning rebind; no historical lock or held-out corpus is rewritten.
Independent review and all inherited/live-provider/billing/native/cloud gates stay
open. This candidate does not establish a live non-Gemini counter or production
memory-vector portability.

## PI-4 governed profile candidate

- [Pre-code plan hardening](pi-4-plan-hardening.md), same-session security decisions.
- [Implementation/self-review report](pi-4-implementation-report.md) and [P4-01–P4-24 machine evidence](pi-4-verification.json).
- [2026-10-30 independent-review remediation](pi-4-independent-review-remediation-2026-10-30.md) — external detail/replay quarantine, signed HTTP evidence, and remaining gates.
- [Owner API, operator instructions and rollback](profile-sharing-v1.md).

Default-off exact-value/revision grants feed the existing planner/packer/provider
path and carry original source authority through counts, summaries, assistant
history, physical reservation, external SSE/replay and detail checks. Legacy allowlists
require re-consent. Local native PG and installed synthetic checks are distinguished
from real OAuth/provider/cloud/erasure acceptance. The exact-record memory view is
explicitly unavailable; browser management UX is incomplete. Historical v10–v22
locks and corpus bytes are preserved; v23 is a source-only non-promoting rebind.
No independent acceptance or production readiness is claimed. MEM-3+ remains frozen.


## PI-5 standalone retrieval/tool candidate (incomplete)

- [Pre-code review and hardening](pi-5-plan-hardening.md).
- [Implementation/self-review report](pi-5-implementation-report.md) and
  [P5-01–P5-28 machine evidence](pi-5-verification.json).
- [Retrieval-v1 API/operator contract](retrieval-v1.md), additive
  [external consumer v1.1.0](consumer-v1.md) and generated OpenAPI.

Real bounded lexical corpus, exact source grants, source-neutral citation metadata,
a single registered read-only tool and signed unrelated-consumer HTTP are implemented
locally. The 2026-10-31 review remediation binds local citation authority to an
operator issuer and authenticated scope, declines title-only body citations, preserves
P19 attempt IDs on Brave failures, preflights deterministic no-dispatch filters, and
limits receipts per scope. Aggregate receipt storage across scopes remains unbounded.
Retrieval has no general model/context, summary/history or memory integration. A generic
operator-extensible tool registry remains a roadmap goal; v1 has one fixed executable.
The Brave bridge retains existing closed strict-free admission; mock transport/P19 ports
are not live acceptance. Receipts are single-host, durable and never pruned. Distributed
authority, restore, real identity/provider/billing and production acceptance remain open.
The detailed PI-5 plan remains an untracked preserved input, identified by hash in the
[review remediation evidence](pi-5-independent-review-remediation-2026-10-31.md). v24 is
a source-only non-promoting planner rebind; all historical locks remain intact. PI-5
mandatory acceptance is incomplete; independent PI-0–5 review remains pending. MEM-3+
stays frozen.


## PI-5 completion candidate — acceptance blocked

- [Pre-code design and source-identity migration](pi-5-completion-plan-hardening.md).
- [Implementation and self-review](pi-5-completion-implementation-report.md),
  [scenario/command evidence](pi-5-completion-verification.json) and
  [mandatory entry gate for PI-6](pi-5-completion-gate.md).
- [Self-contained completion review handoff](pi-5-completion-review-handoff.md).

Explicit local source-to-normal-model context is now implemented with separate
model disclosure grants and retained authority. External source-to-model, export
consent, distributed source/attempt storage, real eligibility/IAM/restore/delete
acceptance remain incomplete. Older standalone-only records
above retain their historical scope; the living boundary is current-state.

## PI-6 conditional offline candidate

- [Conditional-entry decision](pi-6-conditional-entry-decision.md), [revised local plan](pi-6-detailed-implementation-plan.md), [pre-code hardening](pi-6-plan-hardening.md) and [benchmark contract](pi-6-benchmark-contract.md).
- [Implementation report](pi-6-implementation-report.md), [command/scenario/hash ledger](pi-6-verification.json), [benchmark report](pi-6-benchmark-report.md) and [canonical observations](pi-6-benchmark-report.json).
- [Separate gates](pi-6-completion-gate.md) and [review closure](pi-6-review-closure.md); no further review handoff is requested.

Run `make pi6-check` with the backend virtualenv. This is synthetic local evidence,
not real-model lift, live cost or production acceptance. PI-5 remains
`blocked_unverified`; original P6-02/29 are unmet, production promotion is `no_go`,
MEM-3+ remains frozen. No public API, production default or migration is added.


## PI-7 local operations candidate

- [Hardened plan](pi-7-implementation-plan.md) and [pre-code hardening](pi-7-plan-hardening.md).
- [Operations and rollback](pi-7-operations-runbook.md), [data lifecycle and recovery](pi-7-data-lifecycle-runbook.md) and [storage decision](pi-7-storage-operations-decision.md).
- [Implementation report](pi-7-implementation-report.md) and [P7-01–36 verification ledger](pi-7-verification.json).
- [Fresh independent-review prompt](pi-7-independent-review-prompt.md).

Installed synthetic core and Reading Logbook HTTP checks, static cloud policy
validation and simulated recovery have separate evidence classes. Hosted apply,
account/provider caps and cost, deployed source/receipt authority, and native
recovery and physical erasure remain blocked. PI-5/PI-6 gates and the MEM-2
freeze continue to apply.
