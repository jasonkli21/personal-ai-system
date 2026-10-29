# Documentation router

Read [current state](current-state.md), then the smallest task route below.
[Root README](../README.md) and [Makefile](../Makefile) own local setup and commands.

## Authority and document classes

Code/contracts/migrations/tests → dated verification/review evidence → accepted
ADRs → architecture/product intent → authorized plans → history. Security and
privacy constraints apply throughout. A plan or fake test never proves delivery
or provider/cloud acceptance. Each repository owns one current-state page.

## Route by task

| Task | Minimum context |
| --- | --- |
| Five-repo stabilization or separate review | [Current verification](../stabilization/VERIFICATION.md), [fresh re-review handoff](../stabilization/FRESH-REVIEW-HANDOFF.md), [contracts](../stabilization/CROSS-REPO-CONTRACTS.md) |
| Delegated identity, confirmed tasks, domain receipts | [Suite contracts](../stabilization/CROSS-REPO-CONTRACTS.md), `backend/src/personal_ai/contracts/`, `mutations/`, `auth/task_identity.py`, and [integration matrix](../stabilization/INTEGRATION-MATRIX.md) |
| Federation, grants, context identity and revocation | `backend/src/personal_ai/federation/`, [Phase30 architecture](personal-ai-chapter-2/phase-30-architecture.md), owning context adapter and domain contract |
| Chat, branches, summaries and active model input | [API contract](api-contract.md), `backend/src/personal_ai/chat/`, `context/`, focused tests; [Phase2 guide](phase-2-implementation-guide.md) for historical intent |
| Durable memory and temporal context | [Memory README](../backend/src/personal_ai/memory/README.md), [Phase34 report](personal-ai-chapter-2/phase-34-implementation-report.md), memory lifecycle tests |
| MEM-0 research baseline | [Architecture ADR](personal-ai-chapter-2/memory/mem-0-architecture-adr.md), [benchmark contract](personal-ai-chapter-2/memory/mem-0-benchmark-contract.md), [baseline evidence](personal-ai-chapter-2/memory/mem-0-baseline-report.md) |
| MEM-1 verified project knowledge | [Contract ADR](memory/mem-1-contract-adr.md), [implementation evidence](memory/mem-1-implementation-report.md), [review remediation evidence](memory/mem-1-review-remediation-evidence.md), [tombstone capacity blocker](memory/mem-1-tombstone-capacity-follow-up.md) |
| Provider transport, endpoint admission and routing | [Inference README](../backend/src/personal_ai/llm/README.md), [routing README](../backend/src/personal_ai/routing/README.md), provider/accounting tests |
| Persistence, artifacts, deletion and recovery | [Persistence README](../backend/src/personal_ai/persistence/README.md), owning adapter/schema, [operations](../stabilization/OPERATIONS.md) |
| Strict evaluation, experiments and promotion | Owning `backend/src/personal_ai/evaluation/` module, fixture/lock, focused tests; [Phase36 report](personal-ai-chapter-2/phase-36/implementation-report.md) indexes external obligations |
| Shared sidecar, applications and external turns | [Applications README](../backend/src/personal_ai/applications/README.md), frontend sidecar/API code, owning Phase25–31 evidence |
| Maintainability or future work | [Quality assessment](../stabilization/CODE-QUALITY.md), [roadmap](../stabilization/ROADMAP.md), then the specifically authorized plan |

## Authentication and operations

Read the current authentication/account-data code and [Phase9 threat model](phase-9-threat-model.md).
Only verified deployed identity/private invocation can authorize personal data.
Use [suite operations](../stabilization/OPERATIONS.md) for local isolation and
staging prerequisites. External gates remain open unless dated evidence says
otherwise.

## Research, evidence, and domain guides

Use the owning service and focused tests first. [Research notes](research-agent.md)
and [architecture](architecture.md) explain intent. Domain canonical data and UI
remain in their own repositories; [contracts](../stabilization/CROSS-REPO-CONTRACTS.md)
route to those boundaries. Evidence freshness is distinct from durable memory.

## Release and review evidence

[Current verification](../stabilization/VERIFICATION.md) records this patch set.
Chapter2 phase evidence and `docs/releases/` retain dated predecessor acceptance.
Use the [fresh re-review handoff](../stabilization/FRESH-REVIEW-HANDOFF.md)
for the fixes and remaining acceptance; implementation QA does not constitute
independent sign-off.

## Decisions

See [accepted decisions](decisions/) for durable architecture and
[suite decisions](../stabilization/DECISIONS.md) for this bounded stabilization.
The polyglot persistence and LiteLLM boundaries remain unchanged.

## Historical material

The [previous router](history/stabilization/README-before-2026-10-14.md) preserves
the detailed guide/evidence index. The [detailed plan index](personal-ai-chapter-2/personal-ai-next-scope-detailed-implementation-plans/README.md)
preserves future sequencing. Read history only when the bounded task needs it.
