# Memory governance readiness and plan hardening — 2026-11-04

Entry: `b694c5f26e0c5fc21880bac06f1fdf2eac5ca650`, tree
`d1f6dbd80202ca8f7ab2136a7a657ea15087f3da`, branch `main`. No intervening
commits. Tracked tree clean; ten pre-existing untracked detailed plans (HXE 1–5,
MEM 3–7, including the double `.md.md` filename) are owner inputs and excluded
from this change. Python environment: existing `backend/.venv`; no installation,
network, provider or cloud access authorized. Native DSN is unset.

## Decision and authority

Accepted for bounded public/synthetic E0/E1 development by the owner's explicit
implementation request. This is no general lifting of the MEM-3+ freeze.
Durable rationale is [ADR 0027](../decisions/0027-memory-governance-overlay.md).
All production release profiles remain NO_GO. Independent review is pending.

| Capability | Code/evidence boundary | Not accepted |
| --- | --- | --- |
| Verified knowledge / controls | Default-off canonical source leases, CAS, lifecycle and forget; E1 | Deployed issuer/send/erasure and permanent fence economics |
| Episodes | Capture and selection hard-disabled | Producer, reader, export, deployed rights |
| Consolidation | Pending-only E1; prior limited E2 Postgres component evidence | Whole-authority restore, promotion, model utility |
| Navigation | Sealed default-off E1 lexical/topic research | Real semantic/hybrid, blind task proof |
| Longitudinal research | E1 author-visible 3,528-row campaign | Independent lift: corrected primary is 0 pp / 25 pairs |
| Owner portability | Explicit profile-only export, inert import preview | Knowledge/episode transfer, imported authority |
| Release | Author tooling; every profile NO_GO | Phase 36, PI, HXE-5 independent acceptance |

Inherited failures: `planning_baseline_changed_requires_new_version` and PI-6
`frozen_protocol_mismatch`; historical evidence is not rewritten. Previous offline
run also needed SDK/Checklist source paths and could not bind sandbox loopback.
Prior remediation is not independent acceptance. Current verification will record
fresh outcomes separately.

## Threat model and corrections

The host binds verified owner/actor, canonical source app/workspace/project,
immutable record/version, owner and lifecycle epochs, registered recipient
principal/app/workspace/project and membership epoch, exact purpose and read-only
ceiling, explicit user proof and expiry. All must intersect. Email, UUID equality,
shared storage, imported JSON and memory text confer no authority. Cross-owner,
wildcard, transitive and sensitive/unverified sources fail closed. Replays bind
the original actor and complete input; revocation and regrant advance generations.

Selection, pack and final internal observation each revalidate under the same
synthetic authority/store lock. Physical send is always denied: a rights check
alone cannot close revoke-to-send races. No callback can dispatch effects through
this seam. No copied durable content, route, tool, flag or runtime issuer is added.
A Python object boundary is a host API discipline, not a hostile Python sandbox.

A stale snapshot cannot reconcile itself: a separately retained monotonic fence
must match before reads resume. E1 demonstrates this with separate fixture state;
it does not prove survival of deployed authority. Logical suppression, physical
erasure and irretractable external copies have separate statuses.

Native SQL is deliberately not added: there is no approved DSN, surviving authority
or deployed owner-erasure integration for a grant table. A repository protocol
and atomic in-memory test adapter provide E1 CAS/replay fault proofs. Adding an
untested production table would misstate durability. E2 adapter/transaction and
cold restore acceptance stay blocked with exact operator reentry tests.

## Finite work and verification

1. Closed versioned contracts and pure policy, host/repository seam; no runtime registration.
2. Synthetic two-owner/two-agent/two-app/two-project lifecycle, revoke, restore,
   quotas, replay and faults; additive six-family campaign with at least 36 rows.
3. Inert owner preview, per-store erasure inventory and pure canary/rollback plans.
4. Two fresh-process runs with code/source hashes, complete rows and semantic
   equality; measured E1 timings/counts separated from unknown native costs.
5. Focused and adjacent Makefile checks, full offline attempt, exact inherited
   failures, G01–G27 matrix and independent review handoff in dated evidence.

Rejected expansions: live model/recipient, general identity service, automatic
memory promotion, applied imports, episode use, production flags, and fictitious
native/physical guarantees. No E1 work is deferred for lack of external services.
