# Provider eligibility by deployment

**Provisional · 2026-11-21 05:16 UTC · No account-specific approval supplied.** Decisions govern admission today. Confidence refers to the decision, not the likelihood of future approval.

|Topology|Target app|Device/host|User UX|Identity vs plan execution|App registration|Token custody|User vs operator control|Provider/model scope|Credit/limit policy|Receipt/recovery support|Evidence (2026-11-21)|Confidence|Decision|Open blocker/owner|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|Installed OSS Electron|Source-free probe|macOS 14+ local Node|Install and connect|Direct plan|App-bound local registration|OS-encrypted main process|User machine|Direct scopes below, discover model|Gate I|Local stream L|[Kit][K]|High for example|conditional|License, registration, allowance / owner|
|Non-Electron desktop|Packaged client|Local process|Install and connect|Proposed plan|Exact client unknown|Needs OS-backed adapter|User machine|Platform unverified|I|L unproven here|[Security][S]|Medium|unverified|Packaging and provider applicability / client lead|
|Partner website|Travel|Browser plus approved host TBD|Visit and connect|Identity trial distinct from plan participation|Separate partner grants needed|Provider must name custodian|Operator runs Travel|No Travel scope supplied|I|Partner contract missing|[Website][W], [Usage][U]|High|blocked_external|App and host approval / product owner|
|Pure browser OSS|Travel|Page JS|Visit site|Proposed plan|Browser registration unknown|No approved persistent store|User browser, operator serves JS|No documented grant in inspected kit|I|Tab lifetime insufficient for durable witness|[Kit][K]|High|unverified|Platform and custody / provider|
|Embedded native|Health|iOS or Android Expo build|Normal install|Proposed direct plan|Each native client unverified|Would require OS secure store|User device|Desktop scopes insufficient evidence|I|Mobile termination unresolved|[Kit][K]|High|unverified|Per-OS eligibility / mobile lead|
|Partner mobile|Health|App plus approved host TBD|Normal install|Partner plan|Written mobile enrollment needed|Unspecified|Depends on agreement|App/workspace grant unknown|I|Partner contract missing|[Usage][U]|High|blocked_external|Named host and mobile grant / owner|
|Sole-user VM|Power user|User-administered remote VM|Provision, pay, patch|Possible plan session transfer|Registered client and transfer rules unresolved|Remote persistence disputed|Must be solely user controlled|Host scope unknown|I|Host attribution uncertain|[VM][V], [Terms][T]|High for UX|conditional; reject default|Written reconciliation / provider|
|Managed per-user container|Travel or Health|Operator cloud|No extra install|Proposed plan|No backend grant|Operator can access runtime|Operator despite tenant isolation|No approved scope|Deny|No authorized path|[Terms][T]|High|rejected|Only reconsider specified written arrangement / owner|
|Separate daemon|Travel|User desktop plus browser|Install, update and troubleshoot bridge|Proposed local plan|Companion/app binding unclear|Local OS store only|User machine|Eligibility unverified|I|Bridge and browser require bound journals|[Kit][K]|High|rejected for browser-only UX|Separate product decision / Travel|
|Developer API|Either|App backend|Opt in|Developer billing|Developer project|Project API secret on operator backend|Operator|Project model permissions|Separate hard budget|Separate API receipt contract required|[API][A]|High|out_of_scope|Finance and security approval / operator|
|No AI|Both|Domain app|Normal use|Domain identity only|Existing domain registration|No model token|Domain owner|None|Zero model calls|No send|[Roadmap][R]|High|selected|None|

**I — included-only admission.** Require provider-enforced, app/account/workspace-bound evidence that this invocation can consume included allowance only, even with purchased credits or automatic credit purchases enabled. Require eligible live model and fresh entitlement at send. Go, Plus, Pro and Business names alone establish neither inclusion nor a particular model. Verify each tier and workspace admin policy. Deny missing entitlement, disabled workspace, exhausted allowance or unknown usage. Respect weekly app caps below 100% even when account allowance remains. On account switch invalidate preview, grant and cost evidence. Credit-enabled accounts require an independently enforceable zero-credit path. Never route exhaustion to developer billing.

**L — receipt interpretation.** Local sample requests `openid profile email offline_access resource.invoke chatgpt.tokens.use.direct` and uses PKCE. Only the approved scopes actually granted to the bound client count. A request ID correlates events. A stream delta witnesses activity. The sample requires `response.completed` and sends `store:false`. None of those signals identifies the payer or guarantees later status lookup. Only a durable pre-send denial with an intact physical fence establishes definitely unsent locally. After send-start, a 429, disconnect or missing terminal leaves usage unresolved absent authoritative request-specific evidence. Preserve original key, account, app, host, attempt and revocation epoch. Reconcile status without redispatch. PAS completion also requires matching terminal, clean EOF and agreeing original-key status. No provider-backed billing or lookup semantics were verified for partner or API modes.

**Persistence and lifecycle.** Local disconnect clears profile tokens; remote revocation is attempted and can remain unconfirmed. Deny background execution by default; a future path needs explicit consent and platform authority. For partner, VM, browser and native proposals, persistence, unattended execution and revocation granularity require host-specific evidence. No shared plan vault. Private or paid distribution has no inferred OSS grant. The DevKit noncommercial license can exclude business testing even for free products.

### Evidence register

Directly inspected on 2026-11-21: pinned OpenAI DevKit README, LICENSE, docs/security.md and packages/local/src/{oauth,responses}.ts. The links to provider policy, VM, identity and usage guides below identify the roadmap's sources. Direct retrieval of those pages and the local guides returned proxy 403; their present text, update dates and tier-specific rules remain unverified. Terms effective date reported by roadmap: 2026-11-04. No approval letter supplied.

[K]: https://github.com/openai/sign-in-with-chatgpt-devkit/tree/0a36fefeb913055c8c7a1a29b63d82b96b2e841a
[S]: https://github.com/openai/sign-in-with-chatgpt-devkit/blob/0a36fefeb913055c8c7a1a29b63d82b96b2e841a/docs/security.md
[W]: https://developers.openai.com/siwc/website
[U]: https://help.openai.com/en/articles/20001542-using-your-chatgpt-plan-in-other-apps-and-sites
[V]: https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms
[T]: https://openai.com/policies/sign-in-with-chatgpt-terms/
[A]: https://developers.openai.com/api/docs
[R]: PAS_User_Controlled_Inference_Runtime_Roadmap_2026-11-21.md
