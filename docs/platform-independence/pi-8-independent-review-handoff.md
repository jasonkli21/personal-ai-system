# Independent PI-8 review prompt

Open a **new GPT-6.1 Sol / High Codex session** and apply this file as its review
prompt. Review the exact commit that introduced this file. Resolve the full SHA
with `git log --diff-filter=A -1 --format=%H -- docs/platform-independence/pi-8-independent-review-handoff.md`
and compare it with the SHA in the authoring session's delivery. The introducing
commit's parent must be `9b4b0f4db358ac97c156a615831dbb81a0a636a9`. The Git
lookup avoids embedding a commit's own SHA in its contents.

Independently inspect the commit and parent, the
[pre-code hardening](pi-8-plan-hardening.md), [report](pi-8-implementation-report.md),
[ledger](pi-8-verification.json) and [readiness verdict](pi-8-readiness-assessment.md).
Read repository instructions and the owning contracts. Treat the author's
findings and command claims as hypotheses. Run `make pi8-check` and reproduce
the safe report commands. Try falsifying ledger provenance, evidence classes,
case coverage, and the no-go conclusions. In particular, examine authority loss
after final recheck, export with missing provenance, stale journal generations,
strict-free physical dispatch, and native child isolation. Verify that no
historical evidence, fixtures, defaults, or user-owned untracked files entered
the commit. Where original untracked inputs are unavailable, report that limit.

If the native fence is denied, preserve BLOCKED and do not run degraded smoke.
This handoff grants no live provider, Docker, cloud, backup restore, erasure,
billing or personal-data authority. Keep external checks blocked unless the
operator independently supplies exact authorization and safe prerequisites.
Classify findings P0–P3 with source lines, reproduction, owner and gate impact.
Return evidence by profile and independent acceptance or changes required.
Do not promote PI-5, PI-6, PI-7 or MEM-2 based on this local audit.
