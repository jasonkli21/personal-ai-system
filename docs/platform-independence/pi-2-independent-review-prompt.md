# PI-2 separate independent review

Review the **single implementation commit containing this prompt** against base
`2746ea711248603b484f5985ab561978c4ec34bc`. Resolve exact target with
`git log -1 --format=%H -- docs/platform-independence/pi-2-implementation-report.md`
and review `git diff BASE TARGET`. User requested a separate Sol High independent
review after implementation. This file records no review verdict and does not
execute another session. The implementation session used no subagents.

Read AGENTS.md, docs/router/current state, PI-0/PI-1 open gate evidence, PI-2
hardening, consumer contract/spec, sample quickstart and implementation report.
Code/security fences outrank plans and reported test counts. PI-0/1 independent
acceptance remains pending; the user explicitly permitted a non-promotable PI-2
candidate. Preserve the MEM-2 freeze and all historical acceptance limitations.

Inspect the whole diff and challenge its scope. Prioritize:

- Actual Google signature/time/issuer/scalar audience and azp handling, cache
  behavior, primary UI compatibility, operator-file races/outage/expiry/revoke,
  forged app/owner/actor/workspace, user vs service/delegated identity and private
  invocation. An app header/manifest/Origin is never authority.
- Same-owner cross-app UUIDs, external route restrictions, global/account/memory
  surfaces, opaque federation handles, source/derived-history revocation and final
  model-send disclosure checks. Investigate any gap beyond the supplied fixtures.
- Trusted host contracts and explicit entry-point selection: rogue/unselected
  code, absent/incompatible/duplicate/colliding extensions, membership changes,
  startup health and retained task reconcilers. Trusted Python is not sandboxed.
- Stable create/continue keys and digests under races/preparation failure, partial
  stream, disconnect, timeout, response loss, process restart and native-store
  uncertain commits. Status must only observe canonical messages, including
  inactive branches. Failed/in-progress originals must never auto-resend.
- Client SSE fragmentation, invalid/duplicate/delayed terminal, bounds, incomplete
  HTTP, redirects/proxies, local journal timing and false completion. Trace the
  separate client-only CLI process; search built archives/dependencies/imports for
  platform internals or checkout hooks. Local notes must stay local unless chosen.
- v1 generated schemas versus real middleware/routes/SSE; legacy caller behavior;
  no model/provider portability, shared memory or new tool pipeline slipped in.
- Frozen migrations 028–031, MEM fixtures/flags/actor/source/grant/forget/receipt
  fences and v10–v19 lock bytes. v20 may bind source only; strict source/runtime
  rejection, deterministic configuration and non-promotion must survive.

Reproduce using preinstalled dependencies only, no `.env`, cloud credentials or
provider calls. `UV_OFFLINE=true UV_CACHE_DIR=/tmp/pi2-review-cache make pi2-check`
builds wheel-from-sdist artifacts, runs PI-1 physical-absence/legacy/uninstall
probes, then installed PI-2 HTTP tests. It needs permission for numeric loopback
listeners. See the report for exact focused regression commands; use the Python
network-fenced runner. Inspect the fence itself and the closed fake ports. A
passing pytest result with any forbidden attempted DNS/network is not hermetic
acceptance. Native C/OS-wide egress is not covered by the Python audit hook.

Add adversarial cases beyond P2-01–19. Re-run lint/diff and relevant fake suites,
report exact revisions/hashes/commands/results, and distinguish blocked/skipped
Linux/Python 3.12, actual Google/public-client/service IAM, native DB races/crash
recovery, physical provider-send and production security evidence. Do not infer
independent acceptance, production readiness, model economics or cloud identity
from this sample. No push/deployment/provider call is authorized by this prompt.
