# PI-0 independent review remediation — 2026-10-30

## Scope and source identity

This bounded remediation addresses findings R01–R03 from the [independent
review](pi-0-review.md). It was performed on the exact reviewed base
`7db14ab72f29a520aba373b9cb3784fe01d45d3b` (`git rev-parse HEAD` before edits).
The resulting source and documentation are delivered together in the single
commit identified by repository history; the original [PI-0 source manifest](pi-0-source-manifest.json)
and [implementation report](pi-0-implementation-report.md) remain unchanged as
historical evidence for that base. The remediation source identity is the
versioned file set in this commit plus its Git tree; no claim is made that the
original manifest describes these later edits.

Only the diagnostic guard, its tests, PI inventory/waiver documentation and
current status pointers changed. There are no production Python modules,
frontend files, migrations, evaluation fixtures or existing tests in the
change. The memory freeze remains at MEM-2, and all independent, identity,
source-fence, physical-send, deletion, backup, provider, cloud and production
gates remain open.

## Finding dispositions

| Finding | Disposition | Evidence |
| --- | --- | --- |
| PI0-R01 — facade imports can bypass leaf-only guard | Accepted and closed for direct static imports | Source review confirmed four direct edges into three explicitly classified facades: `main -> api.domains`, `api.domains -> domains.fixtures`, `applications.registry -> domains.registry`, and `domains.service -> domains.registry`. The guard now inventories these separately and fails on unwaived edges. A negative fixture retains an otherwise waived leaf edge while adding a facade edge and observes nonzero CLI status. |
| PI0-R02 — malformed rationale can pass | Accepted and closed for waiver records | Waivers now require exact keys and primitive types, nonblank already-trimmed rationale, exact phase/status, exact non-wildcard endpoints, valid category, and unique records. Top-level metadata is also schema-checked. Tests cover blank, numeric/list rationale, missing keys, malformed fields and duplicate records. |
| PI0-R03 — stale roadmap next action | Accepted and closed | The old imperative is labeled historical/superseded. The active instruction is independent PI-0 remediation/reverification and acceptance, then PI-1 planning for explicit review; implementation still requires its own approval and gates. |

The facade classification is deliberately narrow: `personal_ai.api.domains`,
`personal_ai.domains.fixtures`, and `personal_ai.domains.registry`. Neutral
`domains.contracts`, `domains.providers`, and shared decision modules were
inspected and remain unclassified. Existing facade-to-facade imports are
captured as exact debt. The executable waiver baseline preserves all 20 original
implementation pairs and adds four facade pairs; no existing implementation
edge or waiver was removed or merged. The machine inventory now contains 60
records total, including the four new facade-edge records.

## Verification

Run from the repository root, on the remediation source committed here:

| Command | Result |
| --- | --- |
| `git diff --check` | **Passed.** |
| `backend/.venv/bin/python -m ruff check backend/scripts/platform_dependency_inventory.py backend/tests/test_platform_dependency_inventory.py` | **Passed.** |
| `backend/.venv/bin/python backend/scripts/platform_dependency_inventory.py > /tmp/pi-0-inventory-1.json`, repeat to `/tmp/pi-0-inventory-2.json`, then `cmp` | **Passed.** Outputs are byte-identical and contain 20 implementation edges plus four facade edges. |
| `backend/.venv/bin/python backend/scripts/platform_dependency_inventory.py --check` | **Passed.** 20 implementation edges, four facade edges, zero issues; 24 exact waivers. |
| `backend/.venv/bin/python -m unittest discover -s backend/tests -p test_platform_dependency_inventory.py -v` | **Passed: 11 tests.** |
| Synthetic CLI negative with new facade edge and unchanged waived leaf edge (included in the unittest command) | **Passed.** Expected exit status 1 and `unexpected facade: personal_ai.main -> personal_ai.api.domains`. |
| `git diff --name-status 7db14ab72f29a520aba373b9cb3784fe01d45d3b` | **Passed scope review.** Changed paths are the diagnostic, its tests, and PI documentation/records; no production/runtime/data path changed. The new remediation report was untracked during this pre-commit comparison and is included in the single commit. |

An initial expanded test run exposed a faulty prefix-collision fixture, which
also imported a leaf example; the fixture was corrected to isolate the near-
prefix case and the final 11-test run passed. The six broader historical
regression files were not run. The review requires a
safe no-egress harness and fake-provider injection for those checks; neither was
established for this bounded task. No full offline suite, provider, database,
emulator, cloud, deployment, or personal-data check was run. The reviewer's
independent connector observations remain attributed to the review and are not
represented as local reruns.

## Remaining coverage and decision gate

The AST guard observes direct static imports, including nested and
`TYPE_CHECKING` imports, relative imports, and package/submodule imports. It is
not a transitive-closure solver and does not observe `importlib`, `__import__`,
entry-point loading, string references, native extensions, runtime composition,
or installed-wheel physical absence. Existing dynamic composition evidence and
all PI-1 physical-absence requirements remain in force. PI-1 implementation is
not authorized by this remediation. The documentary baseline can inform PI-1
planning only after a fresh independent PI-0 acceptance; separate explicit
approval and PI-1 entry gates are still required before implementation.

Rollback is limited to reverting this single remediation commit. It restores
the former leaf-only guard and stale roadmap wording; it does not touch runtime
behavior or alter historical memory records. The original PI-0 baseline commit
and artifacts remain available in history.
