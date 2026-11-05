# Reasoning engine

- [Architecture and owners](architecture.md)
- [Automatic continuation effort](continuation-effort.md)
- [Continuation effort verification](2026-11-04-effort-verification.md)
- [RE-1 independent-review remediation](2026-11-05-re-1-review-remediation.md)
- [Finite reasoning workflow](re-2-implementation.md)
- [Finite reasoning verification](re-2-verification.md)
- [RE-2 independent-review remediation](re-2-review-remediation.md)
- [Grounded iterative reasoning](re-3-implementation.md)
- [Grounded verification and review handoff](re-3-verification.md)
- [RE-3 independent-review remediation receipt](re-3-review-remediation.md)
- [Grounded release gates](re-3-blockers.md)
- [Historical request and result sketch](api-contract-v1-proposed.md)
- [Threat model](threat-model.md)
- [Frozen offline benchmark](benchmark-contract.md)
- [Implementation decisions at entry](2026-11-04-re-0-plan-hardening.md)
- [Verification and independent review handoff](2026-11-04-re-0-verification.md)
- [Independent-review remediation receipt](2026-11-04-re-0-remediation.md)

Run `make reasoning-check` and `make reasoning-eval` from the repository root
with the backend environment provisioned. The benchmark is a scripted
offline evaluation. `make reasoning-eval` uses the sealed v2 lane; the v1
manifest and source files remain available for historical replay. The
[living implementation status](../current-state.md) tracks gate disposition.

Run `make reasoning-orchestrator-check` and `make reasoning-orchestrator-eval`
for the separate, sealed finite reasoning lane. Use `make workflow-postgres-check`
for native process, fencing and acknowledgement faults against a disposable
local PostgreSQL fixture with pgvector.

Run `make reasoning-grounded-check` and `make reasoning-grounded-eval` for
the separate sealed grounded lane. The grounded host is default-off, local
fixture-only and uses the same foreground workflow and chat continuation.
