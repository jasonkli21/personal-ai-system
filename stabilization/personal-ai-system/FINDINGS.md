> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Personal AI reconciled findings

2026-10-13; tested base `c029194156c570ec55f8173af969702f0265e57b` plus the reviewed working-tree patch set.

| Priority | Finding | Reconciliation/evidence | Next action |
| --- | --- | --- | --- |
| P0 | CI benchmark environment mismatch | Root cause confirmed: portable unit tests invoked strict benchmark replay, whose committed lock binds platform, Python micro/ABI and installed distributions. Those tests now use a temporary runtime-bound lock; production `evaluate()` remains strict. V11 binds the reviewed P19/P21 source changes, preserving v10, corpus, and non-promotion. Local portable tests and strict v11 replay pass; post-patch remote CI has not run. | Recheck after remote CI; keep strict replay limited to its recorded runtime/source/revision |
| P1 | No live domain mutation host | README and mutation registration retain unavailable adapters; Shopping worker reconciles destination | Reuse mutation lifecycle; trusted typed ingress and domain-owned receipt |
| P1 | Shared identity/version authority incomplete | Existing Health signed delegation, owner-scoped grants; separate domain mappings | Versioned generic authority, no implicit email/subject conversion |
| P1 | Physical deletion/native recovery unaccepted | Current status and Phase36 retain explicit blockers | Native execution evidence and deletion-fenced restore |
| P2 | Effective context burden | Current status ~63KB; research service >2K nonblank lines; large generated evaluation receipts | Bounded review after green baseline, preserve coverage |

Audit suggestions are not implementation evidence. The held-out corpus and v10 lock are unchanged; v11 is a new strict source/runtime lock. No model-answer quality observation or promoted coverage was added.
