# Phase 30/31 fourth independent review handoff

**Prepared:** 2026-10-12
**Purpose:** independently verify the third-review remediation commits and identify any remaining implementation defects. Treat this as review context, not as authorization to expand Phase 30, enable integrations, deploy, or change remote state.

## Review targets

| Repository | Branch | Remediation commit | Parent |
| --- | --- | --- | --- |
| `personal-ai-system` | `main` | `05208aca144c872bfc1398be2de6e543c8abe812` | `7e707df38621f114c10774aa9b4535e2d11a7ca9` |
| `health-app` | `main` | `a60ad7a9caf76b52d443c318057625c14ac7e065` | `31fd0ff5f9607b181fb505d97a9c7cc7911145ec` |
| `travel-app` | `main` | `bb275d6f9b1e3ad041ec22367c4ca039fcb3945d` | `0af49a9e72d65065808a5f2ea4bc21736339f214` |
| `shopping-assistant` | unchanged | `2268b944ffa8fe5c2e6f2787c88dea616160e398` | unchanged |
| `personal-finance-and-investments` | unchanged | `495c21186b68215bf110ab6ab3115cd67190cc67` | unchanged |

The first three rows are the code/test commits to review. Documentation/evidence follow-up is recorded in the Personal AI, Health, and Travel repositories on their `main` branches. The corresponding status/evidence entry points are each repo's `docs/current-state.md`; detailed records are linked from those files.

## Expected remediation boundaries

- **P30-H1A:** Personal AI preserves token issue time separately from actual authentication time. A signed Health `auth_time` must originate from a verified upstream authentication-time claim. Missing, stale, malformed, or future authentication times fail closed. Token `iat` remains a distinct token-freshness check.
- **P30-H1B:** Health's narrow federation-export gate is independent of its broad context-read gate. Shared service-identity configuration is required for either capability, and federation-specific key validation remains tied to federation activation.
- **P30-H2A:** Travel's central authenticated sidecar classifier includes `/v1/trips/{trip_id}/assistant/federation-choices`; no route-local credential forwarding is introduced.
- **P30-M4:** Browser APIs carry only an opaque destination-scoped HMAC handle and a display-safe label. Public continuation schemas reject caller-authored canonical federation selections. Server resolution binds the handle to the exact current grant issuance, owner/actor, and destination.
- **P30-M5:** Choice discovery and handle resolution make bounded local grant-store/cryptographic checks and do not call source authority or retrieve source values. Actual continuation still performs full broker/source revalidation before disclosure and at the established use boundaries.
- **P30-H2B:** Shopping's authenticated Personal AI host remains explicitly deferred. The rejected arbitrary-HTTPS credential-forwarding approach must not return.
- **Phase 31 and Finance P30-M3:** The third review marked these areas resolved. They were not changed in this remediation pass.

## Review questions

1. Can any code path synthesize a recent authentication fact from token issue time, request time, or session time? Does missing upstream `auth_time` reliably prevent sensitive delegation?
2. Can a handle survive grant update, revocation, purge/recreation, actor/owner change, or destination change? Can the browser modify a handle or submit raw grant fields to widen authority?
3. Does discovery have a fixed grant cap and zero remote source checks? At actual use, are all existing currentness, source authorization, revocation, completeness, and disclosure checks preserved?
4. Does the Travel hosted route get the same verified session/user match and server-built Personal AI auth context as the existing sidecar operations? Do unrelated routes still reject identity headers?
5. Can Health federation be enabled while the broad context route remains closed, without bypassing shared service-identity or federation-key validation?
6. Are API/UI labels and logs free of grant IDs, source entity IDs, raw field lists, permission revisions, source values, and credential material?

## Recorded checks and limitations

The remediation evidence records these local results: Personal AI focused auth tests **12 passed**; federation/settings/Travel-context tests **75 passed**; backend Ruff passed; frontend tests **123 passed** and typecheck passed. Health's focused context/federation contract suite **19 passed** and changed-file Ruff passed. Travel's focused backend suite **57 passed**, Node suite **60 passed**, changed-file Ruff/ESLint and TypeScript passed.

Travel's hosted middleware integration test was added but skipped because `TEST_DATABASE_URL` was unset. PostgreSQL race behavior, deployed Google/Firebase identities, Cloud Run IAM, live providers, and browser/device acceptance remain unverified; do not infer failure or acceptance from their absence. No cloud/provider/emulator/production acceptance is claimed.

## Open Phase 30 scope

Phase 30 remains incomplete. Shopping has no approved destination host, canonical trusted Personal AI origin, and request-bound delegated-user contract. Keep Health ergonomic constraints, Travel trip data, and Finance budget data unavailable to Shopping until a dedicated destination-host subphase implements and reviews pinned HTTPS/service identity, user-owner binding, project/conversation anchoring, opaque choices, and credential containment. The three Shopping-bound flows and live Health → Travel revocation acceptance remain open.

## Supporting evidence

- Personal AI remediation evidence: `docs/personal-ai-chapter-2/phase-30-31-third-review-remediation-evidence-2026-10-12.md`
- Health remediation evidence: `health-app/docs/implementation/evidence/phase-30-third-review-remediation-2026-10-12.md`
- Travel follow-up: `personal-travel-app/docs/releases/phase-30-federation-export.md`
- Original re-review findings: `phase-30-31-third-independent-review-handoff-2026-10-12.md`
