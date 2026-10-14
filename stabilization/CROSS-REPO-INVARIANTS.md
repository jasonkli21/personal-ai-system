# Cross-repository invariants

Primary-session review, 2026-10-13. These constrain stabilization; they are not claims of implemented end-to-end acceptance.

1. Domain applications retain canonical domain state, owner mapping, revisions, validation and writes. Personal AI retains orchestration, grants, shared context and execution metadata. No cross-app database access.
2. Verified service identity and verified user identity are separate. Issuer plus subject is the external identity tuple; email equality, a domain UUID or the literal `local` cannot establish a cross-app owner. Receiver resolves its own authorized owner.
3. Application/workspace scope is explicit. A Shopping project or Travel trip is not implicitly a workspace. Null scope remains distinct from arbitrary strings.
4. Delegation binds exact payload, source/destination, audience, capability, purpose, field/scope bounds, current grant/source dependencies, expiry and execution identity. Health recency and linked-owner consent cannot be weakened.
5. Shared contract/version authority must fail closed on incompatibility. Historical contracts remain identifiable for reconciliation; new-write eligibility differs from old-result observation.
6. Existing Personal AI mutation reservation and observation-only reconciliation semantics should be preserved. Any error after potential dispatch is uncertain until authoritative destination evidence resolves it. Never resend a mutation merely because the response was lost.
7. Destination deduplication receipt, domain revision and domain write commit atomically through the existing application service. Same execution key with different intent is a conflict.
8. Confirmation binds exact intent and source/target revisions. Model output and deterministic user commands need truthful distinct provenance.
9. Revocation/deletion is checked at owning authority boundaries. Retained derived context, receipts and restored data cannot silently resurrect removed authorization or records.
10. Tests use synthetic data. Offline fakes, native local services, cloud IAM, live providers and browser/device acceptance are distinct evidence classes. Default-off external/private gates stay enforced until their actual acceptance.

Reviewed anchors: Personal AI `auth/verification.py`, `auth/delegation.py`, `federation/contracts.py`, `mutations/contracts.py`, `mutations/service.py`, `mutations/registration.py`; Health `integrations/personal_ai_federation_auth.py`; Shopping `integrations/personal_ai/auth.py` and `client.py`; Finance `integrations/finance_context.py`; Travel `docs/06-ai-integration.md`. See ARCHITECTURE-BASELINE.md for repository-qualified paths.
