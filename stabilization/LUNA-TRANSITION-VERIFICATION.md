# Luna-to-direct-session verification

2026-10-14. Earlier worker patches were preserved and inspected against the
baseline tuple in the review handoff. Direct execution corrected further defects,
ran the affected native paths, and repeated standalone checks at the final source
state. A model's name or completion message is not evidence of correctness.
Separate independent review remains required; this is implementation QA.

| Earlier work | Direct reconciliation and polish | Strongest local evidence |
| --- | --- | --- |
| PAI portable planner unit lock | Verified tests use only a temporary runtime-bound lock; production source/runtime/unrelated-revision guards remain strict. Preserve v10/v11; justified v12 covers the initial implementation; v13 anchors the final publication follow-up without changing corpus/configuration or promoting experiments | Focused planner guard tests, full offline suite, strict v12/v13 replay |
| PAI retention helper forwarding | Inspected required physical attempt ID and publication status forwarded intact; no silent event/status loss | Native P19 accounting, operational event and retention tests |
| PAI database-clock UTC | Inspected timezone normalization before elapsed deadline arithmetic; added/retained native DST/cooldown assertions | Native routing/retention suite and offline routing tests |
| PAI native fixtures and assertions | UUID schemas replace reused names; current contract fields retained; authoritative unknown capacity is not fabricated | Full native suite;14 unavailable DynamoDB cases explicitly skipped |
| Shopping container migration path | Absolute image Alembic path preserved; workflow changes inspected. No local container claim | Static workflow inspection; fresh hosted image job required |
| Shopping bounded-response/time fixture | Preserved too-large rejection and aware-time instant comparison | Full offline API and native context tests |
| Shopping Discover derived goal | Preserved synchronous initial derived value, then user edit ownership; SSR regression retained |69 web tests, lint/type/build |
| Shopping generated context fields | Regenerated current types and checked generator equality; no handwritten drift | API-types --check and web types/build |
| Health readiness URL object | Inspected SQLAlchemy URL passed without password-masking conversion; readiness recovers after sanitized failure | Earlier synthetic SCRAM reproduction/fix and final native suite; final trust-mode test does not replace SCRAM evidence |
| Health provider owner ordering | User flush precedes ProviderIdentity FK; actual constraints kept | Native auth/provider/context tests |
| Health timezone/domain/member assertions | Optional-domain validation and unordered membership assertion preserve actual contract; no clinical/metric value weakened | Native API/domain suite |
| Health imports/types/Terraform | Inspected structural/import-only changes separately from behavior; UID typed, literal schema Final, CI lint/format/mypy and Terraform fmt rerun | Full Python checks, scaffold, generated client/mobile checks; provider validation remains separate |
| Travel recovery head/fixture | Current Alembic head replaces stale0015 assumption; interrupted promotion hard-link direction corrected; hosted/private guard kept | Actual age/SQL/blob recovery at 0020; native backend and web suite |
| Travel secret baseline/type cleanup | Reviewed synthetic allowlist/location changes and typed context binding/rollback guard | Final lint/types/migration/secret scan; no personal key added |
| Finance OpenAPI/client and factory typing | Regenerated budget/task API, retained authoritative schema/factory types; no financial calculation rewritten | Full package check, types and native suite |
| Finance valuation/recovery fixtures | Cached quote pins valuation instant rather than changing expected financial math; schema counts/head updated honestly | Native recovery/valuation tests and package check |

Further defects found and corrected during direct execution:

- PAI grant listing sorted a nonexistent physical updated_at column; use the
  stored JSON timestamp and native regression.
- Global domain catalog was wrongly included in owner export/deletion inventory;
  remove it because it has no owner/record columns. Native account tests cover it.
- Provider-matrix deterministic baseline dropped real quota buckets; preserve
  latest observed buckets and keep unknown capacity unknown.
- Callback assertion audience was incorrectly compared to PAI instead of its
  Shopping-bound original assertion; exact callback/request binding is retained.
- Shopping retired-contract observation ran current fingerprint checks too early;
  observe a known exact receipt first while refusing unknown new writes.
- Current Firebase Google link and revocation epoch were missing from delegated
  owner checks; recheck both in Shopping/Health and test negative SDK records.
- Health narrow route mounting depended on the broad gate; make the independent
  gate explicit and replace duplicate handwritten JWT verification with canonical
  closed verification.
- Source status omitted the original confirmation ID, preventing recovery after a
  lost confirm acknowledgement; return only the canonical small status fields.
- Source handlers were carrying duplicated settings/transport and creation logic;
  share generated transport/settings/status and extract domain creation services.
- Travel had no whole-owner restore fence; add freeze/bounded cleanup, independent
  current-marker replay and actual encrypted post-backup erasure smoke. Health gains
  a bounded isolated replay primitive without claiming cloud promotion.
- Populated task recovery migrations could discard deduplication state on rollback;
  refuse populated downgrade and verify native receipt/source preservation.
- Finance Alembic ignored an explicit connection. Honor the connection/search path
  so the all-five harness applies migrations in its actual source schema. The
  native rollback test exposed this; it now passes against real command rows.
- Shopping task auth was inline and absent from the route dependency inventory;
  expose explicit signed owner and exact service-only metadata dependencies.
- Shopping metadata FK cycles produced warnings; declare the existing named
  cycle edge separately without changing database FK semantics. Native migration
  checks now retain only the existing Starlette deprecation warning.
- Runner defaults could inherit configured DB/private-store settings. Supply
  explicit synthetic overrides and preserve Shopping's separate runtime-DB refusal.
  Finance evidence-key tests now supply their own synthetic key.

- Final real HTTPS verification exposed Health body deadlines using the logging
  clock rather than the event-loop clock. Use the loop clock, add distinct-epoch
  regression coverage, and rerun 281 native tests and 32 cross-app cases.
- Health’s root CI lint invocation did not preserve first-party import ownership
  or generated-format exclusions. Declare explicit ownership and robust globs;
  the exact root invocation now passes without rewriting generated modules.

Fresh hosted CI additionally exposed the container migration’s missing explicit
local-auth environment, Linux-only parser tuple inference, sibling-only document
links and a timezone-dependent mobile fixture. These were corrected with the
production guards/semantics retained, then checked locally and republished.

Additional exact-revision CI exposed the Travel pool test’s masked URL password,
Finance’s fixed browser quotes valued after their freshness window, and a missing
Phase36 offline phrase in Root’s shorter status. Pass the URL object; choose the
explicit historical fixture valuation; restore the truthful offline phrase.
SCRAM recovery, all seven browser journeys and final full backend checks cover
these corrections without changing product/security semantics.

No earlier worker change was discarded merely because execution switched models.
The inventory records changed files/content identities and structurally identical
Python changes; tests and manual inspection supply behavioral evidence. The code
is prepared for independent review, not certified defect-free. Actual IAM/SDK,
provider, cloud, device, process-crash and full rendered acceptance remain open.
See [verification](VERIFICATION.md) for exact final commands and counts.
