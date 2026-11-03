# PI-7 pre-implementation review

2026-11-02 (America/Los_Angeles). Base `57fc5ea53af6540c86f6f0df7ef2ff23b67a1d62`
on main. The index and tracked tree had no changes. Two files were untracked.

| Input | SHA-256 |
| --- | --- |
| pi-6-conditional-offline-development-codex-handoff.md | 6855d4cb55a5ea2b9d0eecda01c2714b8c45ac5c5e3208d0337474b0d2fc33f1 |
| pi-7-detailed-implementation-plan.md | 40f26ae872db031f2e167aed3bb3a66b124683ec189dca47669493d17c204029 |
| Downloads/pi-7-implementation-prompt.md | 74783dbe721afe87601b74def7de3c0aadec829609e7cf14655c83a714935348 |

Preserve the two untracked inputs byte-for-byte. Commit a hardened derivative
of the PI-7 plan and record implementation decisions here. Both originals stay
outside the commit.
The sorted Git index listing for the historical evaluation fixtures
(`git ls-files -s 'backend/src/personal_ai/evaluation/fixtures/**'`) hashes
to `377b11269faad6a521b4cb6d4cea16f8b6b5472921257137eab74e4f53b577cb`.

## Baseline and gates

| Gate | Entry status |
| --- | --- |
| pi5_completion | blocked_unverified |
| pi6_offline_evaluation | locally_complete, frozen synthetic evidence |
| pi6_production_promotion | no_go |
| pi7_offline_operability | pending |
| pi7_cloud_preflight | pending static checks |
| pi7_hosted_operations | blocked_unverified |
| pi7_native_recovery_deletion | blocked_unverified |
| pi7_release_promotion | no_go |

The PI-5 route remediation does not supply native source leases, source/export
rights, cross-worker attempt receipts or restore authority. The PI-6 review
closure is user-directed and applies to its scoped synthetic remediation.
PI-6 freezes the entire core Python/JSON tree, and planning v27 binds the
core source plus a current-or-direct-child Git revision. Keep the phase's
operational controls outside the runtime package. A core change would require
a separately versioned evaluation binding and new evidence. Check both
historical guards on the actual revision and record any revision mismatch.

## Findings and implementation decisions

- **W1.** PI-1 calls its TestClient an HTTP check. That exercises ASGI and
  lifespan but cannot establish an actual network listener. PI-2 binds a
  loopback listener with a signed test issuer. Reuse its runner and auth tests.
  Build in a unique temporary directory with the locked uv environment and
  use an actual listener for the core as well. Rebuild from the sdist and
  install its wheel outside the source tree. The normal lifespan requires a
  mutation inventory even with offline inference. Supply explicit synthetic
  stores and preserve production startup validation. Do not introduce a public
  auth bypass or second app factory. Strip environment, home, .pth/editables
  and source paths from the child boundary. Build/install offline from existing
  dependencies and local archives. Missing dependencies must fail before a
  probe can be called a pass. Reuse the PI-6 macOS native policy with numeric
  IPv4/IPv6 probes and the PI-2 Python audit hook. Report other OSes blocked
  until an equivalent native launcher exists. Use bounded child groups, a
  socket assigned by the kernel, and owned temporary storage. Time startup
  separately from build/install and label the small sample.
- **W2.** A loopback port proves location, not ownership. The standard
  persistence project has durable volumes and the Makefile includes a
  destructive clean target. Reuse only the existing integration services
  with tmpfs/in-memory state under a dedicated project. Verify the Docker
  socket is local, pin the Compose file and container IDs, check ownership and
  published bindings before connecting or stopping, and refuse unexpected
  resources. Never reuse normal data volumes. Restart for this topology
  means fresh ephemeral stores. A preserved-volume restart requires a separate
  native drill. Build the unrelated client and host separately and reuse the
  signed consumer contract, process and original-key stream-recovery checks.
- **W3.** The legacy shell entrypoint changes the active gcloud project,
  enables services, then checks secret metadata. It hardcodes Gemini as the
  provider label while omitting the explicit inference profile; the app
  defaults to offline_fake and ancillary/provider paths have separate gates.
  It binds IAM without checking drift, deploys the worker before its audience
  is known, and IAM-private does not prove network-private ingress. A token
  such as APPLY=true cannot make that command safe. Replace its executable
  mutation path with a static-only front door. Reserve explicit apply and
  refuse it pending a separately reviewed deployer that binds the exact
  manifest and authorized, verified live state. The predecessor is recoverable
  from Git for audit. Use a closed shape with exact identity edges, pinned
  digests and secret versions, service caps, closed source/model egress and
  gated features. Compare a supplied static baseline and require review of
  any difference. JSON references are proposals, not remote evidence. Never
  echo user values, parser excerpts, cloud output or secret fingerprints.
- **W4.** Route reservations key on owner and estimate fan-out. They miss
  ancillary paths and can diverge from the actual inference profile. Existing
  P19 uses request and bucket transaction locks, endpoint scope, conservative
  unknown reservations and usage provenance. Test those boundaries with the
  inspected offline suites. Use the offline/no-remote profile as the only
  approved PI-7 operational profile. Static preflight refuses strict-free and
  paid dispatch pending scoped evidence. A second in-process quota would give
  misleading safety on restart or multiple workers. Keep existing accounting,
  retention and kill-switch semantics. Test local chat, provider, research and
  retrieval stops where the owning path supports them. Report gaps such as a
  switch racing an already reserved attempt. Use fixed diagnostics and explicit
  synthetic/estimate/observed billing categories.
- **W5.** Restoring all stores from the same stale snapshot can restore both
  source rights and receipt state. Demonstrate denial with existing source
  checks and journal capacity/replay using a synthetic authority outside the
  reverted snapshot. Include the loss-of-authority case in the drill plan.
  Prohibit opening restored traffic until rights and original-key fences are
  reconciled. Inventory summaries, history, traces, exports, embeddings,
  local journals, source apps, backups and downstream retention. Keep the
  Postgres/Dynamo split pending measured operational and recovery evidence.
- **W6.** Use Makefile targets and a single scenario ledger. A branch
  commit cannot contain its own SHA. Pin the base and content of the tested
  executable changes and resolve the final revision via Git. Use the
  separate reviewer prompt in a fresh session after implementation.

## Acceptance and rollback

| Evidence | Scenarios | Stop or rollback |
| --- | --- | --- |
| Installed app and native loopback fence | P7-01–08 | Missing build tools, locked dependencies or native fence block. Remove the temporary profile. |
| Owned Compose integration and installed signed consumer | P7-09–16 | Missing Docker or ownership blocks native cases. Stop only verified owned test services. |
| Static plan and fake CLI tripwire | P7-17–20 | Refuse incomplete policy, drift and apply. Keep deployment stopped pending separately approved reconciliation. |
| Existing admission/accounting plus PI-7 closed profile and diagnostics | P7-21–28 | Stop dispatch when authority, cap or billing facts are unavailable. Report simulated counts separately. |
| Synthetic stale recovery with retained authority | P7-29–32 | Keep restores quarantined without independent current rights and receipt proof. |
| Predecessor checks, preserved locks and disabled features | P7-33–36 | Revert offline tooling/docs without deleting state, dropping compatibility guards or restoring default mutation. |

A01 and A21 map to installed core. A03–A07 map to the installed consumer and
exact-scope replay. A10 maps to closed admission and P19 regression evidence.
A15/A18 map to source and tool checks. A20 remains a synthetic exercise with
native recovery blocked. A19 and A22 remain separate model-utility and audit
gates. Plan validation cannot close deployed IAM, live spend, provider/source
rights, physical deletion or distributed anti-rollback.
