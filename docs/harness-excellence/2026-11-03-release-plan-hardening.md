# Operational release plan hardening — 2026-11-03

Author review in the implementation session; no independent acceptance.
HXE-5 entry is `60bcacb6cac1a252ecb2001b9324eab9dfd198c3`, tree
`b11c6538bd9dc4d6b565393ba2e5e8981694d822`, branch `main`. No tracked
baseline delta; five user-owned untracked phase plans are excluded from the commit.

## Source and contract inventory

Read the router, current state, gate registry, naming policy/exceptions, roadmap
HXE-5, SDK v0.1.0/consumer v1.2.0, installed_core_smoke, sdk_install_smoke,
release_evidence_check and adjacent tests. Inspected entry remediation: recent
owner authentication, profile CAS/deletion fence, portable parser and browser
cancellation; planning v35 and source generation 9 remain authoritative.
Makefile owns build, offline, signed HTTP, SDK and native-fence commands.

## Adversarial decision

Rejected a new acceptance/attempt ledger: it would duplicate canonical authority.
Rejected an all-in-one installer that trusts local RECORD or downloads missing
build inputs: reproducibility does not establish input authenticity. Chosen:
small stdlib-only release tooling next to existing scripts, one versioned profile
inventory and pure closed validator; artifact inspection/repeat-build tooling;
source-free SDK protocol probe; and opt-in bounded existing-test measurement.
No runtime or public contract changes are needed. Frozen benchmark source inputs
are unchanged, so no new benchmark generation/lock is justified.

A review document digest cannot authenticate its reviewer. This implementation
therefore never grants release GO, even if a manifest names a different reviewer.
An external independently pinned digest can bind a review reference but acceptance
still belongs to the independent reviewer/operator. No signing trust root is
invented here. Mandatory gates cannot be removed or marked not applicable.

## Narrow deliverables and gates

A01–A03/A10/A13: fixed capability/profile requirements, closed bounded input,
exact source/receipt binding, monotonic NO_GO/BLOCKED verdicts, historical bytes.
A04: repeat first-party SDK builds from committed source in disposable directories;
report byte differences and build-tool dependency/license metadata, with origin
explicitly unverified. A05–A06: inspect wheel metadata/hooks before install;
source-free unrelated public SDK synthetic transport probe; native clean install
remains BLOCKED without external pins and effective native fence. A07–A08 reuse
canonical retrieval/admission/attempt tests rather than create fake authority.
A09: bounded opt-in offline test resource measurements only; no real-task claim.
A11: operator guide, current state/router/registry and dated receipt. A12 stays off.

## Commands, prerequisites and non-goals

Run new release tooling unit tests, naming-policy-check, backend-lint, sdk-check,
sdk-build, sdk-install-check, consumer-contract-check, operations-check,
offline-benchmark-check, planning-eval, memory-control-eval, backend-test-offline;
optional adapter check only with its prepared environment. Record failures/skips.
Historical release-evidence-check requires an external reviewed SHA and a clean
checkout: user untracked plans and pending independent review block that command.
No false clean-checkout workaround. Native sandbox availability must be tested,
not assumed. No network bootstrap, model/provider/source send, credentials,
publication, cloud, destructive cleanup, optional peer, runtime/default changes,
new dependency, production signoff or applied memory import. Missing external
pins/licenses, model/hash/fence/store, issuer, billing, restore/erasure and
independent review remain owner prerequisites. Deliver one commit as requested.

## Implementation discovery

The broad offline run exposed one pre-existing auth fixture incompatibility with
the entry profile correction contract. Updated only its dependency override,
upstream-auth timestamp, revision request data and fake CAS signatures/assertions;
no runtime behavior, frozen fixture or threshold changed. This is an additive
compatibility-test correction, not a gate waiver. Loopback/native failures remain
blocked and the original unsuccessful suite result is retained.
