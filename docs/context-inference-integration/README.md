# Application context and inference integration

**DRAFT / NOT DEPLOYED.** This package proposes how an independent application could supply a bounded projection of its own records to PAS. The [implementation status](../current-state.md) governs shipped capabilities and production `NO_GO`. The companion integration plan is historical planning context; it does not establish implementation or release readiness.

ChatGPT can request an authorized read through a proposed PAS MCP server. In the other direction, a connected app can ask its user's eligible runtime to run an inference turn. Each path needs its own recipient grant, account binding and release decision. An explicit, redacted snapshot provides a manual alternative when the ChatGPT surface cannot connect.

| Read | Decision it supports |
| --- | --- |
| [Architecture](architecture.md) | Which component owns each record, credential and dispatch |
| [Application context contract](application-context-contract.md) | How to implement an independent source and select records |
| [ChatGPT integration boundaries](chatgpt-integration-boundaries.md) | Which OAuth grant, host and evidence each direction requires |
| [Inference routing policy](inference-routing-policy.md) | Which endpoints a user can authorize and how spending is bounded |
| [Delivery and acceptance](delivery-and-acceptance.md) | What to build first and how to admit a specific mode |

Stage 1 synthetic reads may begin only after an independent acceptance of the repaired Stage 0 contract. MCP, manual export, SIWC, paid APIs, and shared hosting each retain separate gates. The scope excludes data mutation, other subscription systems, unbounded tools, fine-tuning and production rollout.
