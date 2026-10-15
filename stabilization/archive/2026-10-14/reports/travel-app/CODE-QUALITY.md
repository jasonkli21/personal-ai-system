> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Travel code and context inventory

Inventory basis: tracked blobs at Travel `HEAD` `09584976d46c67c97a19c72d173b2ee88dbcb31c`, captured 2026-10-13 before implementation edits. It includes 342 tracked files; the two preserved untracked user files are excluded. Bytes are exact blob sizes. “Physical lines” uses UTF-8 `splitlines()`; “nonblank lines” is a reproducible logical-line proxy, not a statement or AST count. Binary files have zero text lines. Directory totals are recursive and overlap their child directories. Categories are path-based and are intended to locate context hotspots, not set LOC targets.

| Category | Files | Bytes | Physical lines | Nonblank lines |
| --- | ---: | ---: | ---: | ---: |
| Handwritten production code | 171 | 1,188,287 | 29,062 | 26,628 |
| Handwritten tests | 49 | 517,540 | 13,555 | 12,076 |
| Documentation | 69 | 578,547 | 10,200 | 8,207 |
| Configuration, manifests, and locks | 9 | 533,405 | 6,163 | 5,256 |
| Migrations | 19 | 55,295 | 1,497 | 1,329 |
| Operator tooling and scripts | 6 | 67,677 | 1,694 | 1,561 |
| Fixtures and evaluation data | 5 | 13,804 | 367 | 325 |
| Other | 14 | 28,016 | 869 | 821 |

## Largest tracked files by bytes

| File | Bytes | Physical / nonblank lines | Category |
| --- | ---: | ---: | --- |
| `backend/uv.lock` | 396,740 | 1,952 / 1,868 | Lockfile |
| `frontend/pnpm-lock.yaml` | 125,656 | 3,808 / 3,007 | Lockfile |
| `backend/src/personal_travel/services/trip_exports.py` | 56,536 | 1,495 / 1,406 | Production |
| `backend/src/personal_travel/clients/personal_ai.py` | 52,742 | 1,218 / 1,126 | Production |
| `backend/tests/test_phase5_proposal_lifecycle.py` | 51,437 | 1,261 / 1,140 | Test |
| `backend/src/personal_travel/services/booking_imports.py` | 43,210 | 999 / 958 | Production |
| `backend/src/personal_travel/services/proposals.py` | 41,634 | 1,014 / 950 | Production |
| `backend/tests/test_secure_sources.py` | 39,749 | 1,013 / 912 | Test |
| `backend/tests/test_booking_imports.py` | 39,033 | 927 / 851 | Test |
| `frontend/app/globals.css` | 37,943 | 434 / 432 | Production styling |
| `frontend/components/trip-workspace/booking-import-panel.tsx` | 34,741 | 639 / 615 | Production |
| `backend/tests/test_auth_sessions_postgres.py` | 34,520 | 871 / 785 | Test |
| `backend/tests/test_personal_ai_client.py` | 33,909 | 947 / 808 | Test |
| `backend/scripts/secure_backup.py` | 33,629 | 799 / 734 | Operator tooling |
| `backend/src/personal_travel/services/travel_comparisons.py` | 32,420 | 769 / 736 | Production |

## Largest directories

| Directory | Bytes | Physical / nonblank lines | Tracked files |
| --- | ---: | ---: | ---: |
| `backend` | 2,203,287 | 40,091 / 36,313 | 176 |
| `backend/tests` | 925,747 | 24,419 / 21,663 | 71 |
| `backend/src/personal_travel` | 832,974 | 20,817 / 18,890 | 107 |
| `docs` | 828,686 | 14,855 / 11,907 | 85 |
| `backend/src/personal_travel/services` | 819,878 | 20,080 / 18,718 | 54 |
| `frontend` | 711,422 | 18,363 / 16,057 | 106 |
| `frontend/components` | 343,696 | 7,643 / 7,182 | 30 |
| `frontend/components/trip-workspace` | 300,504 | 6,910 / 6,492 | 32 |
| `backend/src/personal_travel/api` | 238,794 | 6,222 / 5,541 | 44 |
| `backend/src/personal_travel/api/routes` | 217,046 | 6,022 / 5,400 | 34 |

The largest handwritten candidates are cohesive domain boundaries by their names and current service map, but this inventory is not a substitute for module-level review. The lockfiles are expected reproducibility inputs. The migration files and test corpora are separate from handwritten production code. No code was split merely to lower line counts in this gate.

## Bounded Gate 2 responsibility review — 2026-10-13

This review follows the top production modules and tests by their public entry
points and helper groupings. It is a maintainability pass, not a claim that every
module was audited line by line.

- `backend/src/personal_travel/services/trip_exports.py` keeps snapshot
  projection, revision stamping, bounded render-worker lifecycle, and JSON,
  HTML, and ICS serialization in one export pipeline. The render-worker limits
  and data projection share security and timeout assumptions. A per-format split
  may be possible later, but would spread these invariants and is not justified
  as a line-count reduction.
- `backend/src/personal_travel/clients/personal_ai.py` is the largest client;
  it groups sidecar, research, comparison, proposal, and booking-extraction
  methods over shared outbound identity, request bounds, and retry/unknown
  outcomes. Splitting capability clients without first defining a shared
  transport contract risks fragmenting those rules. Record as a design seam,
  not a current defect.
- `backend/src/personal_travel/services/booking_imports.py` combines source
  claim/extraction, idempotency recovery, candidate review, rejection, and
  confirmation. This workflow is cohesive end to end, though the overlap with
  source-lifecycle and reservation-confirmation services deserves an explicit
  ownership map before future extraction.
- `backend/scripts/secure_backup.py` has distinct create, verify, and restore
  phases, but they share archive, filesystem-inventory, private-object, and
  database-revision invariants. Keep the security-critical sequence together
  until a security review supports a safer module boundary.
- `backend/src/personal_travel/services/travel_comparisons.py` owns a gated
  comparison and candidate-validation pipeline. Its size follows the domain
  contract rather than an obvious accidental responsibility.
- Large lifecycle/source/import tests cover retry, races, reconciliation,
  timezones, and state transitions. No duplicated fixture block or dead test
  cluster was identified as a safe deletion target; preserve the test coverage.

The frontend's `frontend/lib/api.ts` contract types are handwritten; repository
search found no OpenAPI/Swagger generator or generated API client. The
`typecheck` script's `next typegen` creates Next route types only. Introducing a
contract generator would change the maintenance boundary and needs a separate
contract decision, so no generated-code cleanup was made. The docs router
`docs/README.md` establishes current-state and authority order and routes the
main domain/security/deployment work to owning docs; the backend service map
documents service ownership and key workflows. No navigation change was
needed.

Result: no behavior-preserving source edit was warranted by this bounded pass.
The next quality improvement should first settle the Personal AI transport and
booking source/confirmation ownership seams with the root reviewer, then add a
small focused design/test change if a safe boundary is agreed. No test was
removed and no module was split for size alone.
