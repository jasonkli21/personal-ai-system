# Platform and consumer contracts

This directory documents the stable HTTP consumer boundary, profile sharing, retrieval, and source portability. Implementation reports, review receipts, plans, and frozen evidence remain in their original historical locations and retain their original names and bytes.

## Current contracts

- [Consumer HTTP contract](consumer-v1.md) defines the separately installable client surface and generated OpenAPI subset.
- [Profile sharing](profile-sharing-v1.md) defines owner-bound, default-off profile disclosure and revocation checks.
- [Retrieval](retrieval-v1.md) defines bounded source search and citation behavior.
- [Current implementation state](../current-state.md) is the living status and release boundary.
- [Naming compatibility register](../naming-exceptions.md) lists only exact immutable or externally persisted identifiers that still carry legacy names.

The local consumer and source tools remain bounded development capabilities. Verified deployed identity, provider rights, native persistence and recovery, cloud controls, independent acceptance, and physical deletion remain separate gates. Synthetic checks and local fakes do not close those gates.
