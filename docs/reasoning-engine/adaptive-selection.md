# Adaptive reasoning selection

The [decision](../decisions/0029-adaptive-fixture-selection.md) extends
the existing local fixture workflows. Existing finite and grounded V1
requests, receipts and defaults still apply. No public route or SDK
setting activates the host.

| Local state | Finite source-free fixtures | Grounded public-source fixtures |
| --- | --- | --- |
| `disabled` (default) | Existing V1 template | Existing V1 template |
| `shadow` | Observe finite features and abstain, retaining the existing V1 template | Observe coverage and recommend bounded focus only for one recoverable gap. Existing focus behavior executes. |
| `local_fixture_canary` | Publication and execution are blocked. A restored pointer falls back to V1. | Existing V1 template |

## Policy and workflow

The finite host derives family, bounded slot count and ambiguity from
the closed typed task and checks it against an operator-installed
task-and-fixture allowlist. It uses the installed verifier, source-free
profile, effective effort and intersection of all existing ceilings.
The 2026-11-05 review found no trusted pre-generation feature that
distinguishes the decomposition-favorable independent subgroup. Finite
runtime selection therefore abstains and keeps the V1 baseline for every
family until such a cohort is supported by independent development evidence.
A trusted direct pin, lower effort, and incomplete reserve also keep the
baseline. No requested label, prompt text, model confidence, source text,
holdout label, oracle or retrospective outcome grants permission.
The grounded shadow reads coverage already derived from a validated
local retrieval result. The existing citation predicate and follow-up
resource and rights checks still decide execution and disclosure.

V2 reserves two generations, two charged verifier operations, input,
output, result and count bytes and the full eight-second nominal step
envelope, plus enough wall clock to retain that reserve at admission.
The first objective check permits early success with one generation.
On a failed or inconclusive first check the alternative gets the task
through a fresh canonical continuation with no prior answer. The final
comparison rechecks both typed vectors within one operation. Verified
complementary slots can combine. Unparseable or wrong values do not
become support by agreement. The projected result is exact, verified
partial, or unavailable. There is no model synthesis step in this
template.

Shadow receipts at INFO contain only an installed policy and strategy
identity, feature digest, coarse reason, recommended and baseline action,
and generation. Shadow causes zero extra model, count, retrieval or tool
calls. The finite shadow logs at original admission. The grounded shadow
logs after validated initial coverage and does not affect the admitted
V1 plan. Terminal V2 replay carries the pinned selection and plan digests,
attempt bindings and resource/verifier receipts. Results are transient.
The submitted spec, approval and typed active checkpoints are removed
when the row settles.

## Local operator control

1. Construct `AdaptiveHost` explicitly in the trusted fixture host and
   pass it to the existing `WorkflowService`. Supply the current verified
   workflow scope digest and exact installed build and experiment protocol
   digests. For finite tasks, precompute `finite_fixture_binding(task,
   fixture_digest)` from known public-synthetic inputs and set the
   immutable `finite_fixtures` allowlist. Its default is empty.
2. Create a dedicated operator-owned directory with mode `0700`. Use its
   absolute, symlink-free path with `LocalPolicyControl`. The control
   uses one fixed private file. It does not discover configuration from
   request input or environment. The rollback command takes the directory
   explicitly through its Make variable.
3. Read the current generation with `control.admission()` and release the
   read context. Build a `PolicyPointer` with the next generation, exact
   build and installed policy digests, issued time and expiry. Publish it
   with `control.update(previous_generation, pointer)`. Use the finite
   or grounded installed policy digest for that profile's shadow.
4. Finite canary publication is currently blocked. `LocalPolicyControl.update`
   rejects every canary pointer because this checkout has no mechanical
   artifact verifier or independently held blind corpus. A valid Ed25519
   signature authenticates its signer but does not verify the reported
   measurements. The existing fabricated-signature tests cover cryptographic
   mechanics only and are not promotion evidence. Do not use them to enable a
   pointer.

   Installed workflow hosts also deny execution of restored V2 plans,
   including validly signed plans. Offline V2 comparison stays in its
   isolated evaluation host. A future independent verifier needs custody
   of the exact paired corpus and oracle, complete matched-budget rows,
   preregistered thresholds, recomputed confidence bounds and subgroup and
   safety vetoes, plus a trusted reviewer and exact source, endpoint,
   build and scope bindings. A signed summary alone is insufficient.

To stop new adaptive admissions, run the following against the same
private directory.

```sh
REASONING_ADAPTIVE_CONTROL_DIR=/absolute/private/control make reasoning-adaptive-rollback
```

Rollback atomically publishes the next disabled generation. Repeating it
reports a safe no-op. Missing configuration also reports a safe no-op.
Invalid configuration fails closed and the command reports an error
without replacing an unreadable pointer. A stale writer cannot restore
the old generation through the supported API. The shared lock lasts
through new admission and rollback takes its exclusive lock before
publication. Existing original keys, in-flight plans and receipts
survive rollback. Live or distributed rollback and recovery from a
filesystem snapshot are unverified.

See the [experiment protocol](adaptive-experiment.md), the
[threat model](threat-model.md), and the
[current verification status](../current-state.md).
