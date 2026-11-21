# External evidence and owner actions

**Open · 2026-11-21 · All actions below are owner_action_required. No outreach initiated.**

|Priority / owner|Decision question|Minimum evidence to close|
|---|---|---|
|P0 · Provider liaison|Can Travel's web origin or Health's individual Expo builds register for plan execution? Is enrollment open, waitlisted or partner-only? Which host may send?|Dated provider answer per legal entity, app ID, origins/bundle IDs, registration, redirects, granted scopes, eligible regions and named execution host. Identity-only grant leaves gate closed.|
|P0 · Billing owner|For Go, Plus, Pro and Business, what happens at the weekly app cap, plan exhaustion, workspace denial, purchased credits and auto-purchase?|Provider-documented enforced included-only control and account-specific redacted entitlement, model, workspace policy, reset and cap evidence. Identify observable rejection before any credit debit.|
|P0 · Security owner|Can a named partner backend ever retain or refresh plan credentials? Where may tokens persist on a solely user-controlled VM?|Written custodian, acquisition, refresh, revocation and transfer rules. Ask whether revocation and usage isolate the original and transferred hosts. Treat both as linked until confirmed.|
|P0 · Reliability lead|Which events establish acceptance, start, terminal result, definite rejection and settled charge? What survives store:false?|Documented lookup and retention by request/account/app/host, idempotency window, retry and reconnect behavior, 429 after send-start, and charge reconciliation. Capture only redacted examples.|
|P1 · Licensing owner|Does a source-free proof qualify as noncommercial given the intended products? Which parts may ship?|Review exact pinned LICENSE, brand restrictions, dependency and font notices, app license, distribution and business purpose. Obtain separate rights if necessary.|
|P1 · Mobile and desktop leads|Which native OS versions, client implementations, background tasks, disconnect and account-switch paths are approved?|Per-platform documentation, explicit background consent and revocation behavior, secure-store/redirect requirements and signed package identity.|
|P1 · Review owner|Can the externally cited policies be independently checked?|Supply dated authoritative copies of Terms, website, local, VM, errors/recovery and commercial usage guidance, including effective dates. Record conflicts before changing a decision.|

### Draft for the product owner

We maintain a browser-based Travel app and an Expo iOS/Android Health app. We want each signed-in user to authorize inference in the app against their included ChatGPT allowance. PAS prepares a user-confirmed context preview. Each domain app controls its own data. Could you identify the enrollment process and supported execution host for each app, including eligibility for private or commercial distribution? Please distinguish website identity registration from plan-use authorization.

Please specify which component may acquire, persist and refresh credentials, supported scopes, platforms, models, plans and workspace controls. Can either app enforce included-only execution even when the user enables credits or automatic purchases? What per-request evidence supports terminal status, charge attribution, revocation and recovery after a disconnected stream? We can supply app identifiers through your approved channel.

**Evidence · 2026-11-21.** [Pinned DevKit license](https://github.com/openai/sign-in-with-chatgpt-devkit/blob/0a36fefeb913055c8c7a1a29b63d82b96b2e841a/LICENSE), [matrix and policy access limitations](R0-eligibility-matrix.md).
