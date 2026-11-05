# HXE-2 — Detailed Implementation Plan

# 0\. Status, sources and non-negotiable scope

Repository: https\://github.com/jasonkli21/personal-ai-system  
Pinned planning baseline: 3e9c9581d3ed4de7a0f5897584c28f5adf8d7ea4 (2026-11-03, "refactor: use capability names in active surfaces")  
Roadmap: /Users/jasonkli/projects/personal-ai-system/docs/personal-ai-system-integrated-roadmap-11-03.md  
Entry state: HXE-0 and HXE-1 implemented as scoped development candidates with review fixes; HXE-1 is partial synthetic E1, not live or production acceptance. MEM-0 through MEM-2 have scoped default-off implementations; MEM-3+ is frozen. Production remains NO-GO.  
Authority order: repository AGENTS.md; code/contracts/tests; dated verification and gate registry; ADRs; active roadmap; historical plans. Re-check the actual HEAD and dirty worktree before using this pinned snapshot.

Purpose: implement the smallest useful vertical slice of free-first provider portability, safe observability and real-task evaluation. This is a development authorization, not permission to send private data to external providers, spend money, enable production, or unfreeze memory work.

Relevant code entry points at the pinned baseline:

* backend/src/personal\_ai/llm/execution.py and backend/src/personal\_ai/llm/README.md: closed operator-selected inference pair; offline\_fake, offline\_fake\_alt, legacy\_gemini; provider capability and counter checks.  
* backend/src/personal\_ai/llm/litellm/, llm/client.py, llm/preparation.py, llm/disclosure.py: physical generation/counting, provider transport, model-input preparation and disclosure revalidation.  
* backend/src/personal\_ai/routing/, backend/src/personal\_ai/usage/, persistence/postgres/usage/: endpoint eligibility, strict-free attestations, reservation, dispatch, reconciliation, durable P19 records.  
* backend/src/personal\_ai/retrieval/, adapters/mcp\_source/: default-off retrieval, bounded source/tool context and HXE-1 read-only integration.  
* backend/src/personal\_ai/evaluation/ and docs/platform-independence/pi-6-benchmark-contract.md: existing frozen scripted benchmark. Do not rewrite its manifests, source generations, scoring, threshold or historical receipts.  
* docs/harness-excellence/README.md, docs/harness-excellence/2026-11-03-hxe1-remediation.md, docs/current-state.md, docs/platform-independence/pi-cross-phase-gate-registry.md, docs/naming-exceptions.md and AGENTS.md: evidence tiers, remaining gates, current naming requirements.  
* docs/decisions/0023-external-consumer-and-execution-authority.md: one PAS attempt/intent lifecycle; outside coding harness retains its own execution loop.

The last commit implements a naming policy: implementation-phase identifiers are forbidden in new production filenames, module/package names, tests, fixtures, commands, identifiers, log keys, code comments, active READMEs and user-facing messages. Use enduring capability/behavior names. Do not introduce names such as hxe2\_\*, test\_hxe2\_\*, HXE2\_PROFILE or "phase-two tracing". Phase labels are allowed in this historical implementation plan, dated implementation/review records, and roadmap discussions only. Preserve an existing phase-coded immutable or persisted identity only when docs/naming-exceptions.md establishes compatibility; do not copy the old pattern into new work. Extend the naming checker if the current checker misses material new surfaces.

# 1\. Desired outcome and scope cuts

A) An operator can explicitly configure one optional local inference endpoint, run a bounded useful task through normal PAS chat/context and attempt accounting, and get a source-aware result. The core still imports and starts with the endpoint absent. Prefer a maintained Ollama or llama.cpp-compatible local transport that can realistically execute on available hardware; justify the exact choice in an ADR or concise decision record after inspecting current configuration and libraries.

B) A compact, correlated, privacy-safe trace shows one task/request, context preparation, source/retrieval checks, model count and generation attempts, quota/admission decisions, timing, measured/estimated usage, and terminal/uncertain outcomes. One bounded CLI export works without an external tracing service.

C) A reproducible multi-family experiment harness distinguishes E1 plumbing from E2 real local inference and, if separately authorized, E3 hosted inference. It records both positive task utility and safety negatives without claiming scripted proxy scores measure real model quality.

D) The system remains strict-zero by default. Free provider eligibility is a revocable, expiring, operator-held assertion; a zero-price router label or nominal free-tier advertisement cannot authorize a physical call. Unknown account eligibility, missing counter, uncertain privacy policy, ambiguous billing, expired attestation, exhausted allowance, or mismatched credential fails closed. No default paid fallback or automatic subscription exploitation.

Explicitly outside this phase: general agent orchestration or mutating tools; autonomous provider discovery; large multi-provider marketplace; new memory consolidation or embedding migrations; RE effort/planning engine; production cloud, native store disaster recovery or physical deletion; full OpenCode integration; broad UI/dashboard; hosted source disclosure beyond current grants; adaptive model/strategy promotion; stable public paid mode.

# 2\. Workstream A — Baseline and design hardening (first, in same implementation session)

* Capture git status, exact HEAD, tree and test environment. Identify relevant existing contracts and current gate state; treat uncommitted user work as owned by the user.  
* Write a concise in-repo plan-hardening decision under docs/harness-excellence/ or docs/decisions/ only if it preserves useful durable architecture: what already exists, overlap avoided, chosen local transport and counter, exact trust boundary, tracing owner, evaluation corpus owner, acceptance/test commands, and deferrals.  
* Design one provider capability matrix: model/serializer/tokenizer identity; bounded\_generation, streaming, structured\_generation, token\_counting, embeddings if actually supported; max input/output; context limit; timeout and concurrency; data sensitivity; cost mode; exact accounting evidence; unknowns.  
* Make local-vs-remote distinction explicit. Loopback URL alone is not sufficient trust: require operator-selected endpoint and bounded scheme/host/port, prohibit user-controlled arbitrary URLs and redirects, prevent SSRF and unintended remote egress, and pin the effective identity before physical send. Document residual host/network threats and what native fencing would be needed.  
* Choose a minimal trace contract and lifetime: stable correlation IDs, structured event kinds, version, timestamps/duration, scope identity as pseudonymous references where safe, endpoint/attempt IDs, reason codes, counts, event state, citation/provenance IDs and policy decision. Never persist raw messages, private source snippets, API keys, auth headers, tokens or hidden chain-of-thought.  
* Ensure a new adapter is optional and isolated. Do not fork the context assembler, endpoint registry, SendAccounting/P19 ledger, source authorization, SDK or retry logic.

# 3\. Workstream B — Optional local inference

* Implement an operator-selected local profile/factory behind the existing closed composition interface, with an explicitly pinned implementation and model identity. Preserve current fake and legacy behavior.  
* Define a local endpoint transport with deterministic request serialization; reject invalid schemas, oversized request/response bodies, redirects, unexpected host changes, unsupported operations and unbounded streaming. Enforce request and output limits, cancellation, timeouts and at most the authorized attempt semantics.  
* Supply a matching tokenizer or counting implementation when possible. If exact model-token counter cannot be established, do not label estimates authoritative; choose a conservative bounded capability profile and withhold operations that need exact admission. No silent fallback to another model, counting API or embedding service.  
* Call the shared preparation, sensitivity/disclosure, admission and reservation path for every physical model operation. Reserve before dispatch; reconcile observed output usage, unknown effects and timeouts into the canonical ledger. Missing usage fields remain unknown/estimated, not invented actual usage.  
* Test the absence profile (no install, missing binary, stopped server), insufficient model capabilities, malformed server responses, wrong model identity, local-to-remote DNS/redirect attempt, cancellation, duplicate retry, disclosure revocation, quota/accounting error, and old fake/Gemini compatibility.  
* Deliver a credential-free sample/local quickstart that names a model and hardware requirements only as a verified profile, not as a universal guarantee. Avoid downloading models in unit tests or on core installation.

# 4\. Workstream C — Strict-zero hosted provider readiness

* Keep all live hosted profiles default-off. Support explicit registration/evidence/preflight for one distinct candidate only if there is legitimate operator authorization, current terms and privacy verification, actual account/free-credit and quota checks, exact tokenizer/counting compatibility, and effective model/operation eligibility. Prefer using existing Groq or Cloudflare adapter skeletons rather than duplicating integrations.  
* Store versioned, expiring, credential-bound eligibility evidence without secrets. Check provider identity, free-only account status, regional terms, per-operation pricing (generation, count, embeddings, search and retries), request/tokens ceilings and cap freshness before each physical call.  
* If allowance is unknown, the endpoint can bill, limits change, the account lacks hard no-spend controls, or cost cannot be bounded: deny strict-zero and record a content-free reason. Provide an opt-in diagnostic for operators, not an automatic live test.  
* Do not implement paid mode unless monetary reservation and hard caps are independently enforced and separately authorized; leaving it unavailable is correct. Never assume account-side cap protections can claw back an already submitted request.  
* Prevent any counting, tokenization, preflight, retries, fallback or embeddings from making hidden billable calls. Ensure a prior model-selection decision cannot outlive an attestation or credential change.

# 5\. Workstream D — Minimal observability

* Reuse existing request/run/invocation/attempt IDs. Add one small structured event contract and bounded in-memory recorder; optionally add safe local file export behind explicit operator action. Do not create a second authoritative attempt journal.  
* Instrument at semantic boundaries (authorization/admission, prepared context, count, reserve, dispatch, streamed response, reconciliation, retrieval/source use, tool or memory decision) through one shared correlation context. Keep event emission failure from changing the safety decision; fail safely if an audit record is required for a specific regulated operation.  
* Attach request/attempt/status/reason code, outcome and timestamp; never copy application payloads into traces. Preserve distinctions between reserved, estimated and provider-reported tokens; elapsed and time-to-first-token; zero-cost local, quoted provider estimate, and actual charged USD if independently known. Unknown cost is not \$0.  
* Use bounded buffers, stable schema/version, deterministic ordering where feasible, redaction and retention defaults; guarded export paths with no accidental overwrite or symlink traversal. Export sanitized JSONL plus a human-readable summary, with a manifest binding commit, configuration identity and benchmark run.  
* Test cross-service correlation, lost/duplicated callbacks, timeout/cancellation, concurrent isolation, failing exporters, source revocation, sensitive field leakage, and that disabling telemetry changes no authorization or business outcome.

# 6\. Workstream E — Real-task evaluation and incremental value

* Create a concise versioned experiment manifest in existing evaluation ownership: immutable case IDs, task family, input identity/digest, split (development/held-out), model and tokenizer revisions, inference parameters, hardware/software, policy snapshot, allowed tools/sources, budget, seed if supported, scoring rubric, baseline variant and comparison arms.  
* Freeze a modest corpus (target 12–20 cases across at least four independent families: grounded QA/retrieval, coding/context continuity, multi-step research, and safe denial/permission drift). Include held-out cases and multiple prompt-injection/scope negatives. Prefer synthetic or explicitly approved low-sensitivity content; do not harvest private chats or copyrighted benchmarks without rights.  
* Run E1 with fakes only to prove driver and safety invariants. Separately run at least one E2 real local-model useful task on hardware, if available. Record exact availability and failure/blocked status when hardware or native fencing is absent. E3 hosted tasks require separate operator approval and verified account/privacy/cost gates. Never silently downgrade E2/E3 into E1 claims.  
* Evaluate direct baseline vs fixed selected context vs full eligible context where meaningful; match model, prompt, tools, allowed context, budget ceilings, sample size and measurement protocol. Preserve failures, nonresponses, exclusions, statistical caveats and raw redacted aggregate data.  
* Measure task success, groundedness/citation correctness, wrong-source/stale-context rate, injection and unauthorized disclosure, intervention/recovery counts, tokens/calls, estimated and observed resource usage, latency and time-to-first-token, setup/cold start/idle CPU/RAM, disk/model footprint, and cost/charge unknowns.  
* Optional coding lane: compare unmodified OpenCode V2 with identical OpenCode \+ separately authorized PAS context via an ordinary read-only integration. Hold OpenCode version, model/provider, hardware, task, repository snapshot, tests, time/token budget, tool set and intervention rules fixed. Report marginal accepted patches/test pass, stale-context reduction, human interventions, retries, tool failures and context utilization; never credit PAS for OpenCode's own editor/Git/tool loop. If PAS memory/reasoning is unavailable under existing gates, mark those experimental arms unavailable rather than unfreezing MEM-3+ or adding RE features. The optional lane is not an exit blocker.  
* Experiment manifests and trace export must be reusable by MEM-6 and RE-4; those programs retain their own promotion authority. Do not build an adaptive promotion engine or alter frozen PI-6 source-generation identity. Add new evidence additively.

# 7\. Suggested stable files and interfaces (adapt to actual code)

Potential names, subject to code inspection: backend/src/personal\_ai/llm/local\_endpoint.py; backend/src/personal\_ai/observability/{contracts.py,events.py,export.py}; backend/src/personal\_ai/evaluation/{experiment\_manifest.py,real\_tasks.py,metrics.py}; backend/tests/test\_local\_inference.py, test\_zero\_cost\_admission.py, test\_trace\_redaction.py, test\_real\_task\_evaluation.py; backend/scripts/run\_real\_task\_evaluation.py; docs/inference-local.md or owning module README; experiments/README.md. Use an enduring Make target such as local-inference-check or real-task-eval, never a phase number.  
Avoid new directories or layers when current modules can own the behavior. Reject speculative files/modules and massive fixture expansions; a few high-signal negative tests are better than redundant test piles.

# 8\. Acceptance, evidence and go/no-go

Required for a complete scoped development candidate:

* E0: code/ADR/contract/format/name audit, no secrets, diff check, ownership map, no phase-coded new active surfaces, no accidental frozen benchmark mutation.  
* E1: clean hermetic tests for fake and new local adapter, negative endpoint/SSRF, zero-cost admission, source revocation/revalidation, P19 attempt accounting, cancellation/unknown effects, trace redaction/isolation, manifest determinism and no unauthorized outbound network. Existing inference, consumer, retrieval, MCP and benchmark regressions remain green or are explicitly characterized with a reproduced unrelated failure.  
* E2: a separately installed real local endpoint on actual supported hardware with authenticated or operator-approved binding, a nontrivial bounded task, observed results and measured resource/latency figures. If unavailable, deliver a complete E1 candidate but mark E2 and the real-utility exit unfulfilled.  
* E3: optional only when explicitly approved. If no safely verifiable free provider account exists, hosted profile stays disabled with BLOCKED\_UNVERIFIED. Do not spend to satisfy this plan.  
* E4/E5: not claimed. Cloud restore/erasure, physical-send atomicity, independently audited account billing and longitudinal utility remain separate gates.

Safety vetoes regardless of task score: a paid or external model send without required authorization; unauthorized source disclosure; wrong actor/client/workspace; fallback that changes cost/privacy; unbounded retry; leaked secrets/raw private trace; falsely successful E2/E3 claim; benchmark contamination or altered historical evidence.

Quality exit: demonstrate at least one useful real local task under bounded resources, compare to a meaningful baseline with transparent limitations, and provide an auditable source/attempt/usage trace. No arbitrary fixed percentage improvement required; measure before deciding later optimizations. Failure to obtain E2 is an explicit partial exit, not permission to invent it.

# 9\. Verification, rollback and final evidence

Suggested checks (adjust to actual Makefile/venv and record exact output): make naming-policy-check; make backend-lint; make backend-test-offline; make provider-isolation-check where the OS permits; make offline-benchmark-check; focused tests for local transport, accounting, telemetry and real-task harness; make backend-build; git diff \--check. Existing native/network/fenced tests may be BLOCKED; do not misreport substitutes as equivalent.

Record: base/final commit, toolchain/OS/model/hardware, file changes, public behavior, test commands with exit/pass/fail/deselection counts, measured E1/E2/E3 results, budget decisions, zero-charge evidence, safety canaries, exact blockers and gate owner, rollback instructions. Avoid source dumps, secrets or hidden reasoning in evidence.

Rollback: disable optional local or hosted profile at the operator registry, stop/drain new sends, quiesce trace export and new evaluations, reconcile original P19 reservations and retained uncertain attempts, then revert only scoped code if necessary. Preserve memory, canonical messages, source grants, original-intent keys, durable usage receipts, vector identities and old benchmark generations. Never rewrite history to make a metric pass.

# 10\. Execution and review workflow

Sol Medium: in the same Codex session, first independently review and harden this plan against current code, then implement, verify, self-review and commit. No subagents. If a hard privacy/monetary/issuer prerequisite is unavailable, implement bounded offline facets and document the blocker instead of crossing it.

Sol High: separate independent commit-pinned review of correctness, safety, evidence and scope; produce one complete self-contained Luna High/XHigh remediation handoff rather than editing the source.

Luna High/XHigh: fix reviewed findings, rerun focused and relevant full tests, perform final verification and commit. No further independent review cycle after Luna. Record remaining capability-specific gates rather than promoting them.  
