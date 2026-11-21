# PAS Inference Runtime — R0 / Phase 0 Codex Handoff

**Purpose:** Complete **R0: Provider eligibility and deployment decision log**, the first post-Phase-6 research/architecture milestone. This is a **self-contained research and decision-making handoff**, not a coding or account-action task.  
**Prepared:** 2026-11-21 · **Repository:** https://github.com/jasonkli21/personal-ai-system  
**Pinned inspected PAS HEAD:** `28bb98e4fe1071c8f4dff4896943b6c6b28a4a47`  
**Companion:** `PAS_User_Controlled_Inference_Runtime_Roadmap_2026-11-21.md`  
**Suggested executor:** **Astra Codex / High reasoning**. Use **Extra High** if available for a single-pass, exhaustive external-eligibility and contract audit. Do not use fast/low effort for the final policy determination.  
**Authorization:** Read repositories and public documentation; write requested **Markdown research/ADR output only**. No code or deployment, no sign-in or token exchange, no live inference/provider requests, no partner/contact submissions, no charges, and no changes to user/account permissions.

## A. Executive task (copy into Codex session)

> Implement **R0 documentation only** for the PAS user-controlled inference runtime. First inspect current `jasonkli21/personal-ai-system` at actual HEAD (starting from `28bb98e4`), and the attached runtime roadmap. Phase 6's versioned private HTTP/Python SDK contract and review fixes have been pushed; the repository's own evidence still distinguishes independent E1 acceptance and skipped E2 from completed implementation. Using dated **official OpenAI sources**, determine which exact provider/app/host topologies are documented, partner-approved, blocked, or unverified for (a) browser-only Travel, (b) native Health, and (c) supported installed desktop local inference. Separate ChatGPT **identity sign-in** from **subscription-plan inference** and **developer-billed API**. Verify token custody, entitlement/model access, included allowance versus optional credits, provider receipts and usage recovery. Produce a cited decision matrix, an ADR selecting preferred/fallback deployment modes, a list of exact unanswered questions and approval/action owners, and a small R1/R2/R3 go/no-go checklist. **No implementation, credentials, OAuth, live requests, financial spending, provider outreach or repository code changes.** Where public information cannot prove support, mark `unverified` or `blocked_external`, not `supported`.

## B. Background and desired user outcome

A user opens the **Travel** web app or **Health** React Native/Expo app and uses its normal domain features without AI. If an eligible integration exists, they select **Connect ChatGPT**, authorize the specific app and desired source context, then obtain an AI response **without installing or administering an extra server**. PAS supplies common context selection, permissioned PAS memory, recipient and source authorization, frozen preview, exact confirmation and original-key recovery. The domain apps own their databases, ACLs and final writes. Credential-bearing ChatGPT-plan execution belongs to the authorized runtime/provider arrangement, not to a PAS-held subscription gateway.

Three distinct functions must remain distinct:

1. **App→PAS→provider inference:** user starts a Travel/Health question, PAS assembles source/memory context, and an eligible executor invokes the model.
2. **ChatGPT-as-client→PAS MCP:** ChatGPT searches approved app data through separately granted installed-client identities. This is **not** a prerequisite to R0 or the in-app inference path.
3. **Ordinary developer-billed model API:** separately operated service with developer API credentials/billing, **not** a way of consuming the user's ChatGPT subscription. Disabled unless separately budgeted and approved.

**Success for R0 is a reliable topology decision and explicit documented blockers, not running a model.** R0 may conclude that neither browser-only Travel nor native Health can yet offer the desired subscription experience without a specific provider arrangement; that is a legitimate result.

## C. Current implementation — what not to duplicate

The commit chain is:

| Stage | SHA | What it establishes |
|---|---|---|
| Phase 5 | `f391c0563cfd0336c839fbe4f4e39af710c5cffb` | Shared app/client service and consent-scoped external source projections, synthetic multi-app |
| Phase 5.5 | `21b9d95ae01091b2781753d813676a0f1c21fec4` | App-owned plan mode, PAS memory, preview/confirm, v2 signed dispatch, fake local runtime and durable physical send fence |
| Repair | `f059b8223e441db40a0844017d610e9b32d0d8f0` | R1–R5 recipient/history/preview/native-witness/fairness/scheduling fixes |
| Phase 6 implementation | `0f2c34c06fe09a474547ff4c1b68bafaf37cbd52` | Private versioned HTTP/ASGI adapter + explicit Python SDK 0.2.0 + synthetic socket tests |
| Phase 6 review fixes | `28bb98e4fe1071c8f4dff4896943b6c6b28a4a47` | Preview serialization/size rejection before publication and corrected E1/E2 evidence ledger |

**Scope distinction:** The user reports review fixes done/pushed. The repo's dated evidence at the inspected SHA still says **independent E1 acceptance unverified**, the three Phase 6 PostgreSQL cases were **collected/skipped (`E2=not_run`)**, and E3 hosted provider execution is **NO_GO**. Record these honestly in R0's baseline. R0 should not become a re-review or rerun of Phase 6; any unexpected contradictions go to a separate review owner.

**Existing app-facing protocol:**

- Private `POST /private/application-plan/v1/conversations/{id}/context-preview` and `POST /private/application-plan/v1/conversations/{id}/continue`.
- Canonical conversation create/status/detail remain under `/v1/conversations`.
- Explicit typed `ApplicationPlan` SDK in `personal-ai-sdk==0.2.0`; external consumer v1.2.0 is separate and preserved.
- Synthetic local runtime and injected provider catalog **are not** real SIWC evidence. Do not invent a second plan API or move SIWC refresh tokens into PAS.

**Primary repo reading (at current HEAD, verify paths rather than assume):**

- `docs/current-state.md`
- `docs/platform-independence/private-application-inference-v1.md`
- `docs/context-inference-integration/evidence/2026-11-21-private-application-inference.md`
- `docs/context-inference-integration/user-owned-application-inference.md`
- `backend/src/personal_ai/api/private_application_plan.py`
- `backend/src/personal_ai/services/external_turns/application_plan.py`
- `backend/src/personal_ai/local_bridge/README.md` and its runtime/store modules
- `sdk/python/src/personal_ai_sdk/application_plan.py`, `sdk/python/README.md`
- `backend/tests/test_private_application_plan_http.py`

**Travel app:** https://github.com/jasonkli21/travel-app and `docs/06-ai-integration.md`. Travel is web-first (Next.js/FastAPI/PostgreSQL), already has `travel-context-read-v2` and a read-only sidecar, owns trip ACLs and revisions, and must preserve `workspace_id=null` and the separately scoped legacy research/extraction/proposals. Do not assume a browser-based site can use the OSS local SIWC plan flow.

**Health app:** https://github.com/jasonkli21/health-app and `docs/ai/personal-ai-integration.md`. Health is Expo/React Native/FastAPI/PostgreSQL, uses Firebase owner identity, `health-context-read-v1` and granular `ai_use_allowed`/`cross_domain_use_allowed`. Its narrowly delegated dietary→Travel/ergonomic→Shopping federation export is **not** broad AI inference consent. Mobile SIWC support cannot be inferred from OS Keychain/Keystore alone. No Health records should be accessed or exported in R0.

## D. Explicit questions R0 must answer

### D1. Provider eligibility and program applicability

For **each** topology, answer whether public docs establish *actual* support: locally installed desktop OSS (Electron example), non-Electron desktop, native iOS/Android/Expo, browser-only JavaScript, participating commercial/partner website, participating commercial mobile app, user-owned self-hosted VM, developer-managed per-user cloud container, separate user-installed companion/daemon, and ordinary developer-funded API.

For each include: app category and licensing (OSS/free/paid/private), exact runtime host and custody, client/app registration requirements, authorized OAuth scope, user vs developer control, whether separate provider approval or waitlist is needed, account plan eligibility, allowed persistence, authorized background execution, supported revocation, and whether the user must install/administer infrastructure. **Do not infer a supported platform from a working sample on a different platform.**

The exact **commercial** distinction matters: OpenAI's website identity guide documents a limited selected-partner program; the commercial plan-usage Help Center describes participating apps; the OSS plan-use cookbook covers **locally running** tools. The existence of any one does not qualify PAS/Travel/Health for the others.

### D2. Credential custody and remote-execution policy

Explain the exact difference between:

- user-controlled local runtime with OS-protected tokens;
- a genuine remote runtime controlled solely by the user (including self-hosted VM limitations);
- a developer-owned per-user container or managed Cloud Run backend;
- a third-party/commercial provider-approved execution topology;
- standard developer-owned API credentials for separately billed model execution.

Flag any apparent tension between **SIWC Terms' local token persistence requirement** and the published **self-hosted VM guidance**. Do not resolve ambiguities with engineering conjecture; request authoritative clarification. Identify whether any API/service can hold plan refresh tokens in a backend **with explicit written provider approval**. If not documented, default to **no centralized plan token custody**. Explicitly identify whether host-specific revocation/usage attribution for transferred VM sessions remains limited.

### D3. Entitlements, cost and usage

Find official evidence distinguishing *identity-only login* from *plan execution scopes*, included allowance, Go/Plus/Pro/Business constraints, workplace controls, optional user credits, automatic credit purchases, application weekly caps, and ordinary API billing. Spell out the precise evidentiary requirement for a product **included-only/no-credit** policy. A model name, account label, 429, or cosmetic toggle is not sufficient proof that credits cannot be consumed. Document what happens at missing entitlement, quota exhausted, user credits enabled, app limit under 100%, account switch, workspace admin disabled, and unknown usage state.

**Project preference:** avoid variable model API spend and preserve fully functional no-AI; developer API is a **separate explicitly approved and hard-budgeted option**, never an automatic fallback.

### D4. Receipt and recovery evidence

For each eligible provider path, determine what official responses/events can establish *a request was accepted, started, billed, finished or definitely not sent*. Analyze streaming transport errors (especially 429 or disconnect after send-start), provider request ID, terminal evidence, charge attribution, status/retry policies, account/app/host binding and whether `store:false`/no persistent provider thread changes recovery. Preserve PAS's existing original-key journal and physical send-start fences; no silently reissuing an ambiguous request under a fresh key. Distinguish **documented provider semantics** from a proposed implementation.

### D5. UX, support burden, and deployment costs

Compare the options against the **actual product goal**: users should not separately install, start, update, monitor or fund inference infrastructure. Normal native app installation/sign-in is fine. A desktop companion required for browser Travel **does not** satisfy browser-only zero-extra-install. User-provisioned VM fails the normal consumer-default criterion, even if technically allowed. Estimate qualitative app-operator workload and identify unverified cost/latency assumptions rather than invent quantitative charges.

### D6. Exact next implementation contract

Explain what, if anything, R1 should document after Phase 6 acceptance; how R2 should test a **source-free** supported local client; how R3 differs between local, approved commercial web/mobile and ordinary API modes; and which provider decision would enable a Travel browser-only product slice versus a Health native pilot. No implementation now.

## E. Research method and evidence standards

1. **Pin sources first.** Record run date/time, current PAS SHA, relevant Travel/Health heads, official page URLs, page effective/update dates, and direct quotations **only as short excerpts**. Prefer provider Terms, official technical guides, active registration pages, Help Center and official devkit licenses. A search snippet is a starting point, not definitive terms text.
2. **Classify each claim.** `documented_eligible`, `written_approved`, `conditional`, `unverified`, `blocked_external`, `rejected`, or `out_of_scope`, with a precise reason. `written_approved` requires an actually supplied approval letter or account-specific authoritative evidence, not a general product page.
3. **Do not elevate examples.** Example code, sample Electron implementation, a successful test OAuth or a registration UI by itself does not prove arbitrary Travel/Health production approval. A linked user account does not imply source grants or provider-plan authorization.
4. **Separate verified facts, architecture recommendations and speculation.** Keep each in its own column. Resolve conflicting docs by naming the conflict and an action to confirm it, not guessing.
5. **Do not perform protected actions.** No SIWC login/registration, OAuth code/token capture, model call, credit purchase, partner contact, waitlist submission, real data export, API deployment, user account settings change, or paid request. Draft questions/outreach *for the human to send* instead.
6. **No repo code changes.** If running in a writable Codex checkout, write only the requested documentation files. Do not update frozen source locks, SDK, tests, config, secrets, deployment, or historical review ledgers. If a document would conflict with existing versioned docs, propose the changes rather than overwrite without approval.

### Sources to prioritize (recheck live, don't rely on pasted descriptions)

- SIWC Terms (effective Nov 4, 2026): https://openai.com/policies/sign-in-with-chatgpt-terms/
- SIWC entry and integration choice: https://developers.openai.com/siwc/quickstart
- Open-source/local runtime overview: https://developers.openai.com/siwc/token-sharing-open-source
- Official local implementation example: https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt
- Website identity sign-in: https://developers.openai.com/siwc/website
- SIWC account/refresh/revocation: https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions
- SIWC model and inference: https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference
- SIWC errors/recovery: https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery
- Self-hosted VMs: https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms
- OpenAI devkit and licensing: https://github.com/openai/sign-in-with-chatgpt-devkit
- Commercial plan usage, limits and credits: https://help.openai.com/en/articles/20001542-using-your-chatgpt-plan-in-other-apps-and-sites
- Website/account OAuth is **identity-only** unless a separately eligible plan-use flow is authorized; do not combine them.

## F. Deliverables (docs only; create all of these)

If in the PAS checkout, **propose** the directory `docs/context-inference-integration/runtime-r0/` for new R0-specific documentation, avoiding historical filename collisions. Do not modify other repo paths without explicit approval. Output four Markdown files (or one equivalent folder/archive plus file links if Codex lacks repo write permission):

### F1. `R0-eligibility-matrix.md`

A **dated evidence matrix** with one row per exact topology/app combination. Required columns:

`topology | target_app | device/host | user UX | identity vs plan execution | app registration | token custody | user vs operator control | provider/model scope | credit/limit policy | receipt/recovery support | exact evidence URL/date | confidence | decision | open blocker/owner`.

At minimum include desktop local OSS, browser-only Travel commercial plan, browser-only Travel pure browser, native Health local SIWC, commercial Health mobile, self-hosted VM, developer-managed cloud container, separate desktop companion, ordinary developer API, and no-AI. **Include explicit negative and unknown findings.**

### F2. `R0-provider-topology-ADR.md`

Decision record with status (`provisional` until external approvals): context and constraints; considered A–G alternatives; benefits/drawbacks, custody and governance; **selected mode for Travel web**, **selected mode for Health mobile**, and **technical first source-free proof host**; accepted/conditional/rejected classifications; the no-approval fallback; trigger conditions to revisit each decision. Include Mermaid logical and physical paths for the selected and fallback modes. Avoid a universal provider relay assumption.

### F3. `R0-external-blockers-and-questions.md`

Prioritized outstanding provider questions, a **concise partner eligibility inquiry draft** suitable for the owner to send, any licensing/devkit checks, exact approval/registration facts to request, and concrete account-specific evidence the human must supply. List actions as `owner_action_required`, not `completed`, and **do not contact anyone**.

### F4. `R0-exit-review-and-next-phase-handoff.md`

R0 executive result: go/no-go by topology; **R1 dependency** (accepted Phase 6 app-facing SDK/profile ADR, no new code); **R2 preflight** for an authorized source-free local provider proof; **R3 native/transport preflight** for selected mode; Travel R4 and Health R5 product mode choices; residual E1/E2/E3 limits. Include safety/credit/credentials denial gates, owner actions, useful paths and exact next one-phase recommendation.

Every deliverable must carry a status banner and short dated evidence bibliography. Prefer 80% useful completed decision content over a long list of speculative work.

## G. Acceptance criteria for Codex R0 work

| ID | Requirement | Pass condition |
|---|---|---|
| R0-01 | Baseline accuracy | Correct latest HEAD/ancestry and Phase 6 implementation+review fix; no invented independent acceptance or native E2 |
| R0-02 | Official provider evidence | Every support claim points to currently accessible authoritative documentation or written approval; temporal freshness recorded |
| R0-03 | Explicit identity distinction | Identity-only website SIWC, subscription-plan scopes, and developer API billing separated |
| R0-04 | Comprehensive deployment matrix | Travel browser, Health native, installed local desktop, commercial/partner, VM, cloud, browser JS, companion and no-AI covered |
| R0-05 | Token and user control | No managed PAS SIWC token vault; remote user control explicitly examined; conflicts escalated |
| R0-06 | Credit enforcement | No unsupported zero-credit assertion, no silent developer-paid or user-credit fallback |
| R0-07 | Terminal/recovery | Ambiguous send status and provider receipt semantics assessed; no at-most-once invariant weakened |
| R0-08 | Consumer UX realism | No user-administered server in recommended normal UX; extra-install solutions labeled accurately |
| R0-09 | Travel/Health separation | Travel read-only contract and Health Firebase consent/federation distinctions preserved |
| R0-10 | Phase alignment | R1 adopts Phase 6; R2 local proof conditional; R3 mode-specific; R7 separate MCP |
| R0-11 | Clear decision | Selected default/fallback for each app; unanswered provider questions and owner actions explicit |
| R0-12 | No unauthorized action | Docs only; zero provider calls, registration, token handling, contacts, spending, or source/credential modifications |

**Stop / escalate:** Stop at R0 documentation with `blocked_external` if support/approval is not confirmed. Do not test an unapproved model path “to see whether it works.” Never manufacture an approval, close E2 by treating skipped tests as passes, or call a developer-owned VM user-controlled without evidence.

## H. Recommended Codex execution style

**Best choice: Astra Codex, High reasoning.** R0 is primarily careful external-policy research, product topology selection, security threat-modeling and cross-repo reconciliation, not routine implementation. High reasoning is a good balance of depth and time. Use **Extra High** if your Codex interface provides it and the run will make the final policy/eligibility decision without a second independent review. A faster implementation-focused model can later handle R1 documentation updates once R0 is accepted.

**Suggested workflow:** one research session that gathers sources and produces F1–F4; then a separate independent review (ideally Astra Extra High or another strong reasoning model) checks disputed provider claims and approval assumptions before R2/R3 implementation. Do not burn model budget writing unnecessary runtime code or lengthy test scaffolding during R0.

**Final report format:** list created Markdown paths, pinned SHA, sources checked with date, decisions and confidence by topology, unverified blockers, missing proof, exact human actions, and next single implementation phase. Clearly distinguish `research_complete` from `provider_approved` and `E3_GO`.
