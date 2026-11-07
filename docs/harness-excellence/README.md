# SDK, verification, and release tooling

This directory documents the installable SDK, offline verification commands, release profiles, and operator procedures. Start with the [release operator guide](release-operator-guide.md) for commands and prerequisites, then read the owner package README and executable contract.

## Boundaries

- The Python SDK and optional reference consumers use capability-oriented packages and public contracts.
- `make naming-policy-check` rejects phase-coded names and labels on active paths, source, tests, commands, and current documentation, with only documented compatibility exceptions.
- `make source-contract-check` checks current planning and offline benchmark source identities without writing files. Explicit proposal commands create additive, versioned identities.
- Native install checks, PostgreSQL checks, cloud checks, live provider calls, and independent release acceptance are distinct evidence classes.

A passing hermetic suite establishes only the contracts it executes. It does not establish deployed identity, cloud IAM, billing, provider behavior, restore safety, physical deletion, or production readiness. See the [current implementation state](../current-state.md) and [current source integrity note](../verification/current-source-integrity.md).
