# Reasoning engine

- [Architecture and owners](architecture.md)
- [Proposed request and result contract](api-contract-v1-proposed.md)
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
