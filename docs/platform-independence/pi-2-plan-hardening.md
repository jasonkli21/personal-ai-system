# PI-2 same-session plan hardening

2026-10-30, America/Los_Angeles. Inspected HEAD/main:
`2746ea711248603b484f5985ab561978c4ec34bc`. This review precedes implementation;
no subagents or independent reviewer participated. The user explicitly authorized
PI-2 implementation and one commit. PI-0 and PI-1 independent acceptance are
pending; that instruction permits only a bounded, non-promotable candidate.
Existing untracked planning/review documents will not be staged. `gh run list
--limit 3 --json headSha,status,conclusion,url` failed connecting to GitHub;
hosted CI status is unknown, and the configured remote is personal-ai-agent,
not the name in the planning prompt. No push is authorized.

## Code-grounded boundary

Inspected root instructions/router/current state/README/Makefile/quality workflow;
PI index, roadmap, PI-0 ADR/exit/remediation and PI-1 plan/hardening/report/remediation;
the supplied PI-2 plan; application/context catalogs, main/lifespan, middleware,
Google verification/key transport, service/delegated identity, request scope,
API routes/schemas/dependencies/external-turns/profile, execution contracts,
conversation/chat services, context assembler/authorization/runtime, scope-aware
repositories, Phase36 and PI-1 probes, package metadata, frontend proxy headers
and deployment identity settings. Code and security fences outrank plans.

| Surface | At entry | Bounded change |
| --- | --- | --- |
| HTTP | Existing v1 create/list/get, metadata preview, automatic continuation | Publish generated subset; add key-only status read over canonical messages |
| Client identity | Google signature/issuer/audience, email allowlist and principal directory; client claims discarded | Retain verified audience, authorized party and expiry; exact operator client/app binding |
| App/workspace | Header selects app; registered authority checks workspace | Header remains selector only; external client can select one bound app and narrow HTTP operations |
| Registration | Explicit selected installed application/context entry points; collisions rejected | Separate host package using documented public v1 re-exports, same catalogs |
| Context | Shared budgeted assembler; source/disclosure/final-send fences | Preserve source checks; external request authority checked before inference and send/commit |
| Retry | Stable create UUID; deterministic continuation assistant UUID and digest; incomplete assistant refuses resend | Reuse; expose only key status/reference, never reset failed/uncertain messages |
| SSE | Created/delta/completed/error, no durable offsets | Strict client parser; provisional deltas; durable status and terminal must agree |

## Threat model and decisions

1. Valid app A token + forged app B header: exact verified issuer/audience/azp
   binding denies before repositories. Missing azp means the verified audience,
   never a caller header. A service token cannot become a user: existing verified
   user email/subject admission remains required. Existing signed task delegation
   retains its dedicated route/body/service validation and cannot use this lane.
2. Owner/actor headers and JSON cannot confer identity. Reject identity headers
   for the external lane; schemas forbid owner/actor body fields. Workspace IDs
   still require separately installed exact-subject membership authority.
3. Same owner/app-private UUID guesses must remain repository-scoped. Restrict
   external clients to the documented conversation operations: no account export,
   profile administration, memory controls, task writes or legacy non-idempotent
   messages endpoint. Equal owner does not grant global records.
4. Rogue installed code is operator-trusted Python, not sandboxed. Existing
   explicit catalog selection prevents unselected entry-point loading; no HTTP
   loader or manifest-derived authority. Sample host supplies history-only policy
   and exact issuer/subject/workspace membership, no source provider or grant.
5. Source revocation between planning/counting/send retains existing source
   snapshots/revalidation. Recheck external binding/token expiry/workspace and
   principal-directory authority before inference/send and completion. A policy
   file is read afresh, fails closed on missing/malformed configuration, and can
   revoke without deleting data. No guarantee of cancelling already-sent data.
6. Lost SSE terminal/disconnect/cancellation/provider error is unknown observation.
   Never infer commit from delta text; preserve original key and request locally.
   Status reads never execute models. Failed/streaming existing assistant keys
   refuse resend; server restart/native DB durability remain separate gates.

Registration alternatives: (a) new declarative core descriptor/workspace framework,
(b) existing selected application/context entry points. Choose (b), with a tiny
separate trusted host. (a) duplicates manifest validation and workspace authority
without reducing trusted-operator responsibilities. Publish only a small stable
host facade; do not bless arbitrary private modules.

Client binding alternatives: (a) signed user token audience/azp bound by operator,
(b) service IAM plus request-bound signed user delegation. Choose (a) for this
narrow user-driven read/chat client. Current Google verifier accepts an allowlist
of scalar audiences (confirmed against installed google-auth source); verify
signature/time/issuer/audience before interpreting client claims. Preserve the
builtin audience for genuine UI/reference callers; require its effective azp to
match that audience. Separate OAuth clients get distinct audiences, so obtaining
a token for app A does not authorize app B. Reject multi-audience claims and
unconfigured azp. (b) already exists for bounded task control, but generalizing
its replay/body delegation to chat expands scope and compatibility risk. A static
public secret, Origin, CORS or header alone is rejected. Real Google OAuth client
registration/flow remains an external deployment prerequisite; no fake login or
new token issuer is shipped. The sample accepts an independently obtained ID token
from a protected file; no embedded secret or automatic refresh.

## Revised sequence and acceptance

1. Record this review before code. Implement strict operator policy and verified
   claims; preserve builtin development/tests and signed task routes. Add exact
   external HTTP allowlist and request-authority checks, not a parallel principal map.
2. Add a metadata-only continuation status endpoint using existing key derivation
   and messages. GET active branch alone cannot reliably find a superseded key;
   therefore this small lookup is justified. No reservation/status table or migration.
3. Publish v1 OpenAPI subset, SSE schemas/examples, errors/limits/version/recovery
   and host facade. Add separate host and stdlib-only client distributions and CLI
   with local SQLite records and operation journal. No silent note ingestion.
4. Built artifacts outside checkout: verify wheel/sdist contents/metadata/origins,
   no reference modules or source path, separately installed client and host,
   real loopback HTTP, signed test Google-style JWT with fake key transport,
   real middleware and fake storage/model/workspace ports. Python audit fence
   permits only fixture loopback sockets; any attempted other egress fails the run.
5. Test P2-01–17 locally where feasible, including negative client/workspace/source
   scopes, racing stable keys, lost terminal, failure and durable status. Run
   existing PI-1 artifact/import checks and focused frozen-memory/task/branch/auth
   regressions under an inspected network fence; backend lint and diff checks.
6. Skeptical same-session self-review, repairs/retests, exact dated evidence and
   separate reviewer prompt. Update living state/index as candidate only; one commit.

Rollback: revoke client binding, stop/drain ingress as needed, unselect/uninstall
host/client; preserve all scopes, messages, operation keys, fingerprints, receipts,
source fences/tombstones and historical reconcilers. No down migration. Frozen
migrations 028–031, fixture/lock bytes, MEM flags and memory behavior are unchanged.
No MEM-3+, PI-3/4/5, paid/free provider calls, dependency downloads, cloud credentials
or deployment. Linux/Python 3.12 CI, real Google/client/service IAM, native DB races
and restart, physical provider sends, production security and independent PI-0/1/2
acceptance remain open. Offline artifact installation reuses preinstalled dependencies;
it establishes package independence, not a fresh dependency-resolution acceptance.

Residual dissent: the plan's broad failure matrix is larger than one tiny sample;
evidence must name partial/unexercised cases instead of implying full external
acceptance. Application code remains fully trusted when selected. No material P0
blocks this bounded design; stop if app impersonation, cross-app context or unsafe
same-key resend is demonstrated and cannot be repaired.

## Verification-driven lock addendum

The first `make pi2-check` stopped at the existing strict planner source guard:
`planning_baseline_changed_requires_new_version`. Existing v19 binds all backend
source and cannot attest changed auth/API code. Preserve v10–v19 bytes and strict
runtime/current-or-direct-child rejection; add only a new v20 source binding with
the same deterministic configuration, corpus, fixture dependencies and explicit
non-promotion. This follows the existing PI-1 v19 source-only rebind, rather than
weakening the evaluator or treating old evidence as current. The active source
pointer/version and historical assertions must distinguish v19 from current v20.
No memory behavior, experiment gate or historical fixture is changed. Foreign
runtime/Linux replay remains an open evidence gate, not inferred from this rebind.
