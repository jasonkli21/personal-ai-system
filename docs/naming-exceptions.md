# Naming compatibility exceptions

This register covers active or frozen names that still encode implementation
milestones. Their values or paths are part of persisted identifiers, public
contracts, or immutable verification evidence. Human-facing labels and new
entry points use capability names.

| Name or path | Owner | Observable/persisted effect | Reason and migration status |
| --- | --- | --- | --- |
| `personal_ai.evaluation.pi6*`, `backend/scripts/pi6_*.py`, `backend/tests/test_pi6.py`, and `evaluation/fixtures/pi6/` | Offline benchmark | Frozen source and corpus hashes; measurement and verification records cite these paths | The v1/v2 contracts and source generations bind bytes and paths. Renaming requires a new protocol/source identity and fresh evidence. Kept as the quarantined evaluator exception; no production API is exposed. |
| `evaluation/fixtures/memory/mem0-*`, `mem1-*`, `mem2-*` | Memory evaluators | Immutable suite/case identifiers and benchmark evidence | Preserve frozen corpus identity and historical denominators. |
| `phase8-run:` and `phase8-research-session` | Iterative research service | UUIDv5 deterministic run/session IDs | Changing seed bytes would orphan stable IDs. Retained until a compatibility migration exists. |
| `phase21-root-v1`, `phase21-reselection-v1` | Routing service | UUIDv5 routing decision IDs | Persisted deterministic identifiers; retained byte-for-byte. |
| `phase9-owner-v1`, `phase9-chat-owner-v2` | Owner migration and auth directory | Migration and owner binding identifiers | Used to recognize already-migrated local identities; retained byte-for-byte. |
| `pi3-execution-v1`, `pi3-local-json-bytes-v1` | Inference execution | Execution/counter schema identifiers | Existing records and accounting depend on exact values. |
| `mem2:` | Memory control repository | Idempotency-key namespace | Retry identity depends on the prefix. |
| `phase5-{provider}-snippet-v1`, `phase5-research` | Reference source adapters | Source adapter IDs in attribution and provider configuration | These are data/registration identifiers, not display labels. Rendered attribution now names the provider directly. |
| `phase36-external-evidence-v1`, `phase36-matrix-v1` | Verification contracts | Serialized evidence schema versions | Existing verification records use these exact schema IDs. |
| `phase13-envelope-byte-estimate-v1` and phase-labelled synthetic UUID/source seeds | Context planner and frozen planning fixtures | Counter identity and deterministic synthetic input IDs | Planning manifests bind these values. A new identity requires a separately versioned baseline. |
| `phase` plus `PI-1` in import-waiver records | Dependency inventory | Policy/evidence record fields | Historical waiver identity is part of the inventory evidence. |

The naming-policy check scans active filenames and user-visible surfaces. It
allows only the benchmark paths above and exempts fixture directories whose
names are part of frozen suites. Historical reports and plans remain unchanged.
