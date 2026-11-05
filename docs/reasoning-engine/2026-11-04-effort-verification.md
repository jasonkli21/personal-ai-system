# Continuation effort verification

Baseline `cac6549c47323ababb2c1d2ba3f1f871d3bc43de`. The checks used the
repository Python 3.11.15 virtual environment, with the LiteLLM model cost
map set to local. No reference applications were installed. The HTTP,
wire and local adapter evidence below is hermetic.

| Check | Observed result |
| --- | --- |
| `make reasoning-check` | 118 passed, including 67 continuation effort cases. Python network fence recorded zero attempts. |
| `make reasoning-eval` | 64/64 sealed rows valid. Semantic SHA-256 `9c1335f421c00b36f863f7c55c2321d92a02d68358f5887c6bcf8cd8c8fb2ae2`. |
| Focused offline regression | 434 passed across the effort, chat lifecycle, inference, local transport, LiteLLM, routing, usage, API, federation and external-turn suites. Zero network attempts. A prior concurrent run hit the existing 50 ms chat lifecycle test deadline once. The full focused rerun passed. |
| `make workflow-check` | 70 passed. |
| `make real-task-eval` | 36 scripted rows. Coverage and safety canaries passed. Natural-language quality was unmeasured. |
| `make backend-lint`, `make naming-policy-check`, `git diff --check` | Passed. Naming unit tests passed 2/2. |
| `make sdk-check` | Generated contract check passed. Pytest reported 354 passed, 25 failed, 12 deselected. The same selection on the pinned baseline reproduced the exact 25 failing test names and counts. Failures are in the existing planning source identity and PI-6 frozen protocol checks. The seals were left intact. |

The local socket mock exercises the canonical reservation and final send
boundary. Quota and ledger failures prevent generation. Revoked authority
after reservation prevents send. Lost acknowledgement, timeout and
post-dispatch cancellation retain one attempted generation and an unknown
ledger outcome. Completed replay performs zero new model attempts and changed
effort or budget conflicts. The fake native adapter checks captured bytes
against the exact installed descriptor and rejects dropped, altered or
upgraded control values. The observation and usage trace are content-free.

- E0 and E1 cover the request, policy and observation contracts, captured
  synthetic wire, and offline admission and replay tests. Independent
  exact-commit review remains open.
- E2 real native/local utility remains unmeasured. The existing local
  plain-completion lane needs its separate private socket, model/build,
  operator and quota configuration. A real native mapping also requires
  exact serializer and total-output accounting evidence.
- E3 hosted remains blocked. No hosted profile has a verified native mapping
  or a proven opt-in bound for hidden and billable output, so hosted effort
  requests fail before counting. The inherited source/issuer, billing and
  installed consumer acceptance gates remain open.
- E4 production is NO_GO. Cloud, deployment and recovery checks were outside
  this local run. Development opt-in is disabled by default and denied in
  deployed environments.

[Runtime contract and rollback](continuation-effort.md)
