# Application context and inference integration

**OFFLINE WITNESS / NOT DEPLOYED.** A private test composition exercises bounded reads from synthetic application sources, an in-process recipient-bound snapshot, and a protected MCP adapter over in-process HTTP. The live integration remains a proposal. The [implementation status](../current-state.md) governs shipped capabilities and production `NO_GO`. The companion integration plan is historical planning context; it does not establish implementation or release readiness.

The [optional MCP adapter](../../adapters/mcp_context/README.md) exercises the ChatGPT-facing read contract with a synthetic client over ASGI. The proposed inference direction allows a connected app to ask its user's eligible runtime to run an inference turn. Each path needs its own recipient grant, account binding and release decision. An explicit, redacted snapshot provides a manual alternative when the ChatGPT surface cannot connect.

| Read | Decision it supports |
| --- | --- |
| [Architecture](architecture.md) | Which component owns each record, credential and dispatch |
| [Application context contract](application-context-contract.md) | How to implement an independent source and select records |
| [Shared application service](shared-application-service.md) | How to bind a synthetic app, grant a projection and recover the original consumer request |
| [ChatGPT integration boundaries](chatgpt-integration-boundaries.md) | Which OAuth grant, host and evidence each direction requires |
| [Inference routing policy](inference-routing-policy.md) | Which endpoints a user can authorize and how spending is bounded |
| [Delivery and acceptance](delivery-and-acceptance.md) | What to build first and how to admit a specific mode |

The [maintainer's implementation authorization and synthetic verification](evidence/2026-11-17-synthetic-application-context.md) cover the hermetic implementation; they do not satisfy the independent Stage 0 entry decision. The [2026-11-18 remediation record](evidence/2026-11-18-synthetic-application-context-review-remediation.md) records the accepted code fixes and the remaining independent-review and shared-budget blockers. MCP, manual export, SIWC, paid APIs, and shared hosting each retain separate gates. The scope excludes data mutation, other subscription systems, unbounded tools, fine-tuning and production rollout.
