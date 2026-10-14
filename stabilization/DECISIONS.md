# Stabilization decisions

## D001 — Historical coordination (superseded by D005)

All architectural review and gate decisions occur in the primary coordinator session. The user's latest selection is Sol High, superseding the original Astra Medium selection and applying to the scheduled resume. Only Luna Extra High workers may be spawned. The coordinator gives sufficient handoffs, remains inactive while workers execute, and reviews completed results. Initial Astra worker was stopped on user direction; its architecture draft remains unaccepted until primary-session review. Domain data ownership and security gates remain unchanged.

## D002 — Portable evaluator tests versus strict benchmark replay (2026-10-13, accepted for bounded fix)

Problem: Personal AI's ordinary CI unit tests call strict benchmark replay against a committed macOS/Python 3.11 environment identity. Ubuntu/Python 3.12 correctly fails the replay guard, while the same source passes all 1,699 local offline tests. The audit incorrectly characterized this as a known planner semantic fingerprint change.

Ownership: the evaluator owns strict replay acceptance; test setup owns portable conformance inputs. No runtime planner, persistence, transport, policy, or migration change is required.

Fix: evaluator conformance tests use a temporary runtime-bound lock for the executing environment, explicitly test-only. A separate portable assertion retains comparison of the committed planner/configuration/corpus/source identities. Negative tests preserve default evaluator rejection of incompatible runtime/source/version identities and unrelated revision. Do not change the committed v10 lock or production `evaluate()` behavior; test-generated receipts are not promoted evaluation evidence.

Validation: run focused tests, verify simulated runtime mismatch still fails strict evaluation, then ordinary offline CI-equivalent checks. Preserve all corpus cases and non-promotion assertions. Any actual future source change must still be reviewed against the frozen source identity.

## D003 — Typed-task reference direction (2026-10-13, provisional)

Inspected mutation contracts and service already own confirmed intent, one physical execution reservation and observation-only reconciliation. Prefer extending that lifecycle over adding a parallel engine. A deterministic source ingress needs truthful provenance; it must not impersonate model output. Shopping must atomically persist effect and deduplication receipt through normal domain commands. Exact envelope/version authority, trusted ingress, revocation races and retention need further code review before implementation.

## D004 — Historical worker allocation (superseded by D005)

Keep available Luna XHigh worker slots occupied whenever independent work is ready, with one writer per repository. The Sol High coordinator supplies sufficient context and remains inactive during execution. At completion use brief checkpoint/evidence/dependency checks to dispatch the next work promptly. Perform the full coordinator review only after all nine gates (0–8), rather than after every gate or repository. Foundational decisions and genuine blockers can still receive bounded coordinator judgment. The same allocation and cadence are saved in the scheduled resume.

## D005 — Direct end-to-end execution (2026-10-13, latest user instruction)

Supersedes D001 and D004 execution allocation. Stop all agents and do not spawn or resume any. The configured Sol High session performs implementation and verification directly across repositories, collectively without phase stops. Continue until required work is complete; unresolved resources remain explicit blockers, never accepted evidence. A separate user session will review the result. Scheduled continuation uses this latest instruction.

Model amendment: the user subsequently configured **GPT-6.1 Sol Max**. Preserve that exact model and Max reasoning, including scheduled continuation; do not change it. This supersedes older Sol High model references without changing the direct-execution rule.

## D006 — Reference contracts and domain effect ownership (2026-10-14, implemented locally)

D003's existing-lifecycle direction is implemented: Personal AI owns orchestration,
closed shared identity/task/control contracts and generated consumer copies;
domains own source canonical records and Shopping owns operation validation,
constraints, transactional effect/receipt and privacy. Narrow signed source reads
do not enable broad Health access or general Shopping generation. Trust remains
deployment-managed and single-owner; cloud identity and final review remain open.

## D007 — Strict reviewed freeze and recovery retention (2026-10-14)

Preserve planner v10/v11. V12 binds the reviewed task/federation/accounting source
without changing the30-case corpus, deterministic planner/configuration or
non-promotion decision. Strict runtime/source/revision guards remain executable.
Current erasure intent must be retained independently of old backups and replayed
before promotion. Pending external deletion is never completed by inference.
Populated task-recovery tables and erasure markers refuse destructive downgrade.

## D008 — Git publication (2026-10-14, explicit user authorization)

Commit the completed stabilization changes in each repository and push its branch
to remote main. Exclude unrelated pre-existing user files; preserve remote work,
never force-push. This supersedes the earlier no-push boundary only for Git
publication, not cloud deployment or live-provider/personal-data operations.
