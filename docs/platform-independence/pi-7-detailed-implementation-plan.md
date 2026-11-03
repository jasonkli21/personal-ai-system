# PI-7 Detailed Implementation Plan — Local-First, Free-First Operations

**Repository:** [personal-ai-system](https://github.com/jasonkli21/personal-ai-system)  
**Planning baseline:** 57fc5ea53af6540c86f6f0df7ef2ff23b67a1d62, 2026-11-02 (America/Los\_Angeles). Re-pin HEAD and git status before execution.  
**Target repository path:** docs/platform-independence/pi-7-detailed-implementation-plan.md.  
**Status:** Proposed plan, not implementation evidence, production acceptance, or authorization to contact a provider/cloud.  
**Recommended execution:** GPT-6.1 Sol High for one implementation session, then separate GPT-6.1 Sol High independent review. No subagents.

## 1\. Objective

Turn the existing application-independent AI substrate into a reproducible, operator-friendly harness with a genuine credential-free local path, optional local persistence and unrelated client, safe cloud planning, explicit free-first budgets and failure controls, and evidence-rich data lifecycle and recovery procedures. PI-7 delivers \*operability and operational evidence\*, not broad production readiness. PI-8 remains the independent cross-platform readiness audit.  
The Travel, Shopping, Health and Finance apps are optional examples. The core must build, install, start and be useful when they are physically absent. The independently packaged Reading Logbook demonstrates the public consumer boundary; it is not part of core.

## 2\. Baseline and gate ledger

Source-of-truth priority from [AGENTS.md](https://github.com/jasonkli21/personal-ai-system/blob/main/AGENTS.md): code/contracts/migrations/tests, then dated verification/review evidence, accepted ADRs, architecture intent, and finally plans. Reconcile discrepancies with [current-state](https://github.com/jasonkli21/personal-ai-system/blob/main/docs/current-state.md).

* **PI-1/2:** installed core wheel and source archive, optional reference distribution, external Reading Logbook client/host and versioned HTTP consumer contract already exist. Repeat real installed-artifact verification.  
* **PI-3:** offline\_fake inference is the unconditional credential-free profile. Account-specific strict-free provider dispatch needs source/privacy/credential/quota/counter evidence. Never silently fall back to paid or Gemini.  
* **PI-4/5:** governed profile/retrieval features remain default-off. Source and grant authority must be rechecked at final context/use/send; retained original-key/receipt/tombstone semantics must survive.  
* **PI-5:** [completion gate](https://github.com/jasonkli21/personal-ai-system/blob/main/docs/platform-independence/pi-5-completion-gate.md) remains blocked\_unverified: source/send lease and export rights, live account/provider/deployment IAM, cross-worker durable receipts/recovery, inherited canonical checks and original input ownership.  
* **PI-6:** [completion gate](https://github.com/jasonkli21/personal-ai-system/blob/main/docs/platform-independence/pi-6-completion-gate.md) says synthetic offline evaluation locally complete; review remediation closed at user direction, but production promotion no\_go. No real-model task lift or live cost is established.  
* **Operations today:** [compose](https://github.com/jasonkli21/personal-ai-system/blob/main/docker-compose.persistence.yml) provides loopback PG+pgvector and DynamoDB Local; [GCP deployment script](https://github.com/jasonkli21/personal-ai-system/blob/main/infrastructure/gcp/deploy.sh) changes IAM/services and deploys, with Gemini-oriented settings. [GCP guide](https://github.com/jasonkli21/personal-ai-system/blob/main/docs/gcp-deployment.md) expects Neon, DynamoDB, Cloud Run and Google identity.

**Sequencing decision:** PI-7 offline development, documentation, dry-run and synthetic/native isolated tests can proceed while production PI-5/PI-6 gates remain unresolved. This is not a waiver of those gates. No live provider call, credential use, paid request, cloud mutation, real backup/restore or deletion is authorized by this plan.

## 3\. Boundaries and threat model

* Keep core composition app-neutral, provider-neutral at public service boundaries, and stable for existing v1 consumers. No mandatory example module/identity/service.  
* Preserve verified owner, actor, app, workspace, purpose, recipient, source and grant revisions; deny unknown authorization and revalidate before inclusion, disclosure, provider send and derived-history reads.  
* Treat history, summaries, caches, exports, snapshots and backups as \*derived disclosures\*. Revoked or deleted sources cannot become accessible after restore or replay.  
* Preserve durable original effect keys, P19 physical attempt accounting, no-second-send on uncertain outcome, monotonic tombstones/fences and permanent replay protection. Local SQLite receipt journals do not establish cross-worker distributed authority.  
* MEM-0/1/2 existing semantics stay default-off; MEM-3+ feature development is frozen. No automatic new memory capture, background research/agents, hosted tools or dynamic reasoning engine in PI-7.  
* Do not replace PG/Dynamo or expand the plugin framework just to reduce setup steps. Assess the store split first; no migration without separately authorized design and recovery proof.  
* No secrets/private chats/source excerpts/identifying tokens in manifests, reports, command logs, tests or export. Use synthetic fixtures. Cloud network/IAM configuration may be \*proposed\* without claiming it has been deployed or tested.

## 4\. Operational profiles

### 4.1 offline-core (default)

One discoverable command such as make pi7-local-smoke: build/inspect core wheel and sdist using pinned dependencies; isolate an install with reference packages physically absent; boot actual FastAPI app/lifespan under existing injected fake ports; issue local HTTP chat/context and denial requests. No .env, API key, provider/network, Docker or persistent user data. A fake/no-store smoke is \*not\* durable local production behavior. Prove the actual app composition path, not a parallel test-only facade.  
Native remote network exclusion should be verified by an OS fence on supported platforms. Python audit hooks alone are not proof of a native fence. If not available, the command must explicitly mark the native-egress claim blocked or use a reviewed equivalent.

### 4.2 local-persistent (explicit opt-in)

Reuse Postgres/pgvector and DynamoDB Local from the existing compose file, loopback bindings, owner-validated disposable data and migrations/bootstrap. Expose safe doctor, up, bootstrap, smoke and down. down does not delete volumes. Volume removal/reset needs a separately scoped approval/ownership check; never touch an existing personal or production database.

### 4.3 local-consumer (explicit opt-in)

Install Reading Logbook client and host artifacts separately and verify through documented versioned HTTP. No private Python imports or core code patches. Include registered/unregistered client, workspace/actor/owner forging, stream retry, idempotency, endpoint errors and package removal without core breakage.

### 4.4 cloud-plan (read-only by default)

Render and validate a redacted deployment manifest and diff, without executing gcloud, provider SDK calls, remote reads, auth probes or mutable commands. Model exact region/project, image digest, API/web/worker identity, ingress, IAM, end-user verification, OIDC audience, secrets by reference and version, runtime profile, egress, caps and rollback. Refuse missing/ambiguous policy, privilege expansion, unknown account/source rights and default-enabled risky features. Do not merely invoke the existing live deployment script with a "dry-run" flag unless every side effect is provably removed.

### 4.5 cloud-staging/hosted-smoke (separately authorized)

Not part of default execution. Requires specific operator approval naming project/account, provider/model, allowed external source domains and data classes, action, physical request/rate/spend limits, source usage rights, IAM/network and cleanup. Zero-cost claims cannot be inferred from free-tier eligibility; cloud infrastructure and storage may still bill. Real account/provider cost needs actual scoped accounting evidence. If approval absent, report blocked\_unverified.

## 5\. Same-session plan hardening

Before touching implementation code, the implementing Codex session must challenge this plan against current source and create docs/platform-independence/pi-7-plan-hardening.md recording the pinned base, working tree, chosen design, rejected alternatives, real threat paths, source ownership, test matrix and stops.  
Review whether: the local smoke is actually bootable without persistence; pinned offline builds work without unadvertised cache/download; current Cloud Run script mixes Gemini defaults and PI-3 profiles; cloud planner can prove zero mutation; secret redaction survives failures; cost caps are enforcement rather than advisory; an unsafe reset can erase user volumes; stale backups can resurrect prior source/attempt authority; and a simple storage topology has materially better safety/cost than PG+Dynamo. Change this plan if the source demands it, with an explicit rationale. Do not silently downgrade protection or manufacture external evidence.

## 6\. Workstreams and deliverables

### W0 — Baseline and authority mapping

Read AGENTS/router/current-state, PI charter, PI-0 exit contract, PI-5 gate, PI-6 report/closure, Makefile, backend env example and lockfile, Dockerfile, compose, infrastructure, strict-zero policies, CI and existing PI scripts. Record git status/diffs and preserve all untracked user inputs. Produce an exact list of mutable entrypoints, authority/identity boundaries, existing failures and blocked gates. Separate operational facts from proposed improvements.

### W1 — Fast offline core installation

* Implement pi7-local-smoke and pi7-check using existing build/entrypoint/HTTP checks; build artifacts in disposable owned paths, verify wheel/sdist contents, version/lock hashes and no example imports.  
* Exercise real HTTP authless \*synthetic\* test composition with denied remote network and fake model; do not weaken deployed auth.  
* Fail with actionable diagnostics on missing uv/Python/cache, corrupt config or unsupported OS fence; no implicit network fetch while claiming offline.  
* Time first/steady startup, record the environment and whether dependencies were cached; avoid claims about uncached machine reproducibility without proof.  
* Preserve clean termination and idempotent reruns, including interruption and port conflicts.

### W2 — Native local persistence and independent consumer

* Reuse existing local\_stack/compose rather than introducing a shadow datastore. Validate loopback ports, readiness, schema/table bootstrap, version/restart behavior, clean shutdown and isolation.  
* Add opt-in consumer smoke with installed external Reading Logbook client/host and reference apps absent. Verify versioned API auth, denied forged claims, same-key retries, stream recovery and compatibility.  
* Never delete shared volumes during smoke. If no safe local native environment is available, report these tests blocked; fake ports are not native-store proof.

### W3 — Cloud profile preflight and least privilege

* Create a stable operator profile schema and static/no-side-effect validation path. Distinguish fake, strict-free remote and explicitly paid modes. Unknown policy denies; paid/billing cannot be enabled through an innocuous env alias.  
* Audit and, where appropriate, refactor infrastructure/gcp/deploy.sh so it cannot build/deploy/change IAM before validating every prerequisite and receiving explicit apply authority. Preserve the existing production topology unless justified.  
* Check API/worker private ingress, web proxy, service account grants, token issuer/audience, allowed users/origins, workload identity, secret version pins, network egress, worker push authentication, concurrency, max instances and static billing controls. No secret content in plan.  
* Generate a readable plan with a machine-parseable redacted diff, refusal reasons and rollback. No deployment by default and no live gcloud execution in unit tests.

### W4 — Free-first quota, cost and observability

* Reuse existing endpoint admission, P19 provider usage and physical attempt tracking. Enforce pre-dispatch limits by actor/app/provider/model/operation: request rate, concurrent sends, tokens, search calls, retries, daily quotas and approved maximum spend where possible.  
* Ensure concurrent admission, cancellation, 429, outage, provider timeout, unknown outcome, restart and SDK retry cannot silently exceed proven caps or duplicate an effect. If hard atomic/account billing limits cannot be guaranteed, deny that mode and mark the gap.  
* Emit only allowlisted diagnostics: profile/build/adapter IDs, redacted config digest, counts, bounded latencies, quota pressure, denial categories, health and kill-switch state. Distinguish actual measured provider charges from estimates and fake counters. No raw prompts, evidence excerpts, principal IDs or secrets.  
* Test disable/kill switches, clean fallback to unavailable, budget reset cadence and alert/runbook instructions.

### W5 — Lifecycle, restore and erasure

* Document data ownership across Postgres/pgvector, DynamoDB, local journal, source/consent revisions, retained receipts and tombstones, derived history/summaries/cache/export, artifacts and backups.  
* Design and run non-destructive synthetic revoke/delete → stale backup → restore → denied read/send/replay scenarios, retaining independent high-watermark authority. Identify where local fake proof ends.  
* Write a specific safe \*native\* drill procedure for a disposable, operator-owned store and explicit approval. Do not execute real restore/deletion or source erasure on user/production data.  
* Treat long-lived receipt capacity, source issuer/lease, distributed monotonic protection, physical deletion and external provider retention as blockers until actually evidenced. Never "fix" replay by trimming original keys or tombstones.

### W6 — Storage and operating-cost decision

Produce a short, evidence-backed decision comparing current Neon PG/pgvector \+ DynamoDB \+ Cloud Run/worker with local-only and single-store alternatives. Cover correctness and atomicity, ownership, recovery, portability, latency, billing, maintenance and migration risk. Document measured vs estimated costs and open unknowns. Default to retaining the current topology without a separate migration approval.

### W7 — Documentation, compatibility and evidence

Produce these in repository docs/platform-independence/:

* pi-7-plan-hardening.md with pre-code decisions.  
* pi-7-operations-runbook.md with local and cloud-plan commands, prerequisites, incident controls and rollbacks.  
* pi-7-data-lifecycle-runbook.md with source/derived/backup/deletion/recovery matrix.  
* pi-7-storage-operations-decision.md with cost and topology evaluation.  
* pi-7-implementation-report.md and pi-7-verification.json with source SHA, artifact identities, tests, failures and skipped gates.

Update docs/current-state.md, PI index, documentation router and relevant root/infrastructure READMEs. No user/credential data in evidence. Preserve historical evaluation fixtures/locks, API contracts, receipt keys, migrations and data IDs. Perform a skeptical same-session diff review and then stop for an independent PI-7 review.

## 7\. Acceptance scenarios P7-01–P7-36

Each scenario requires PASS / FAIL / BLOCKED / NOT\_RUN, exact command, artifact/source identity, evidence class and reason. A synthetic pass never closes a live gate.

* **P7-01–04 Core:** isolated wheel/sdist, reference packages physically absent, real app lifespan/HTTP fake turn and denied import, no credentials or source PYTHONPATH.  
* **P7-05–08 Setup:** missing dependencies/offline cache, malformed env, repeated run, interruption/timeout, cleanup limited to owned resources.  
* **P7-09–12 Local stores:** loopback PostgreSQL and DynamoDB boot, restart, schema isolation, preserved volumes and independent consumer installation.  
* **P7-13–16 Auth/replay:** wrong owner, actor, app or workspace, unauthorized registration, idempotent stream/retry, no duplicate physical effect or data disclosure.  
* **P7-17–20 Cloud plan:** no gcloud/cloud call, invalid project/region/secret references, IAM/drift escalation refusal, default apply not executable.  
* **P7-21–24 Provider/budgets:** fake vs strict-free/paid selectors, 429, exhausted quota, concurrent caps and uncertain-outcome retry; no surprise send or fallback.  
* **P7-25–28 Privacy/metrics:** secret/prompt/source canary redaction in configs/logs, verified provenance, actual vs estimated cost, bounded diagnostics.  
* **P7-29–32 Lifecycle:** revoke before send, derived history denial, stale restore and original-key/capacity pressure fail closed without resurrected source or second effect.  
* **P7-33–36 Compatibility:** rollback and feature-disabled path, PI-5/PI-6 historical locks intact, MEM-2 disabled, kill switch and coherent cost ledger.

Cross-map charter acceptance A01, A03–A07, A10, A15, A18, A20 and A21. A19 model utility remains PI-6 gated; A22 is the PI-8 independent audit. Add cases for any discovered bugs.

## 8\. Verification matrix and evidence

Review each command for safety and prerequisites before running. Expected candidates include:

* git status \--short; git diff \--check; bash \-n infrastructure/gcp/deploy.sh; make backend-lint.  
* make pi7-check; make pi7-local-smoke; make pi7-cloud-plan (new targets to add and test).  
* make platform-independence-check; make pi2-check; make pi3-check; make pi4-check; make pi5-check; make pi6-check.  
* make backend-test-offline; make planning-eval; make retrieval-eval; make research-eval; make memory-control-eval; make memory-knowledge-causal-eval.  
* backend/.venv/bin/python \-m pytest backend/tests/test\_deployment\_script.py \-q plus focused new operational tests.

Capture OS/CPU/Python/uv/lock/container environment and native network-fence class; immutable source and artifact hashes; sample counts/p50/p95 for cold path; actual physical calls (should be 0 in offline), cost estimate vs billed observed, denied operations, retained synthetic receipts and restore limitations. Never rewrite historical fixture/lock bytes or claim a runtime test passed when the only evidence is a fake script.

## 9\. Gate outcomes

* **G0 offline operability:** core-only installed source and consumer tests, native or explicitly limited egress evidence, safe setup and negative tests. May be locally\_complete.  
* **G1 cloud preflight:** static plan and zero-side-effect validation, reviewed permission/secret/identity config. May be plan\_validated, **not deployed**.  
* **G2 hosted operations:** exact operator/account/source/provider approval plus scoped real IAM/private network/quota/billing evidence. Otherwise blocked\_unverified.  
* **G3 native recovery/deletion:** real authorized isolated store restore, anti-rollback and physical deletion; provider retention where applicable. Otherwise blocked\_unverified.  
* **G4 release promotion:** G0–G3, inherited PI-5/PI-6/MEM/Phase35–36 gates and fresh independent review. Default no\_go until all requirements are actually met.

The user may authorize conditional offline work while external gates remain incomplete; status must not collapse all gates into one "complete" boolean. Record review acceptance separately from local implementation, production promotion and cloud operations.

## 10\. Rollback and handoff

Disable new optional local/cloud profiles and leave existing v1 APIs and deployments intact. Stop only PI-7-owned disposable services; never erase user volumes, persisted receipts/tombstones, source revocation history, original keys, backups or anti-rollback authority. Cloud rollback requires separate approval. Re-run prior installed-artifact and platform checks.  
PI-8 receives the exact evidence ledger, unresolved risks, reproducible commands, source-ownership map and adversarial scenarios. Do not implement PI-8 itself, MEM-3+, or the later dynamic reasoning/harness excellence program inside PI-7.  
**Planning-only document:** It records the repository state inspected at baseline, not a claim that these tasks/tests were executed.  
