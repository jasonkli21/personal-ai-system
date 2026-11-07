# Evaluation

This package owns deterministic evaluators, offline fixture builders, and their static data. JSON fixtures live under `fixtures/<area>/`; output schemas live under `schemas/`. Synthetic evaluations exercise service contracts but do not establish provider, cloud, deployment, or production behavior.

## Offline information handling

`offline_information_handling.py` runs the opt-in `make offline-benchmark-check` suite through the synthetic host and source-rights adapters. The evaluator, scoring, contracts, task driver, loopback host, audit, package sources, and frozen case bytes are bound by a versioned source manifest. Run `make source-contract-check` for a read-only current-source check. To refresh a source identity, use the explicit proposal commands documented in [current source integrity](../../../../docs/verification/current-source-integrity.md); proposals are additive and historical measurements remain bound to their original source identities.

The original v1/v2 corpora and source manifests are immutable historical evidence. Their filenames were made capability-oriented without changing fixture bytes. The current manifest records the legacy corpus identity separately from current source paths. A source rename does not make old benchmark results evidence for the new source identity.

## Memory evaluations

`make memory-task-eval` runs the deterministic task benchmark over the renamed, byte-preserved case corpus. Unsupported and truncated rows remain in paired comparisons; scripted task success is not measured model quality or native-store evidence.

`make memory-knowledge-eval` runs the author-visible paired project-knowledge evaluation. The frozen suite identity `mem1-paired-v1` remains in corpus and result records for compatibility. The trusted fake exercises Task A, a resolver-bound receipt, canonical persistence, and a separately constructed Task B service. Historical receipts cannot count as new task success. Native resource and model-mediated metrics remain unverified; independent fixture review is still required.

`make memory-control-eval` covers synthetic control probes through a hermetic host. `make memory-navigation-eval` runs the separately locked author-visible navigation study. These evaluators retain unsupported rows and safety denials in their denominators. They do not establish production authority, provider quality, native resource behavior, or physical deletion.

## Planning and answer quality

The planning evaluator binds the current recursive source closure and fixed inputs in an additive baseline lock. Portable source conformance and strict historical runtime replay are separate checks. Current-source identity does not replace historical replay, and neither establishes independent acceptance or production readiness.

## Release verification

The `verification/` program indexes executable contracts and acceptance obligations in a strict versioned matrix. `make integrated-verification` writes sanitized receipts, results, blockers, and a report under ignored `artifacts/verification/`. A successful local run does not mean release-ready; missing external evidence keeps affected capabilities unavailable. Serialized evidence identifiers remain stable for existing records.

Use `make backend-test-offline` for the hermetic suite. Native stores, cloud, live providers, domain acceptance, browser behavior, and independent review remain separate gates. See the [verification model](../../../../docs/reasoning-engine/architecture.md) and [current state](../../../../docs/current-state.md).
