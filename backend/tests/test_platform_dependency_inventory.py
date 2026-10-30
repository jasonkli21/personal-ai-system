"""Hermetic guard tests; also runnable via stdlib unittest without app imports."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/platform_dependency_inventory.py"
SPEC = importlib.util.spec_from_file_location("pi_inventory", SCRIPT)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def waiver(importer="personal_ai.main", target="personal_ai.context.travel"):
    return {
        "from": importer,
        "to": target,
        "rationale": "Retain legacy composition until PI-1",
        "phase": "PI-1",
        "review_status": "implementation-reviewed; independent-pending",
    }


def facade_waiver(importer="personal_ai.main", target="personal_ai.api.domains"):
    return {
        "from": importer,
        "to": target,
        "rationale": "Retain legacy example-facing composition until PI-1",
        "phase": "PI-1",
        "review_status": "implementation-reviewed; independent-pending",
    }


def baseline(*, waivers=(), facade_waivers=()):
    return {
        "review_date": "2026-10-30",
        "review_scope": "hermetic test",
        "schema_version": 1,
        "source_revision": "test-revision",
        "waivers": list(waivers),
        "facade_waivers": list(facade_waivers),
    }


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def source(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_new_forbidden_import_fails_cli_without_auto_waiver(self):
        self.source("personal_ai/main.py", "import personal_ai.context.travel\n")
        baseline = self.root / "waivers.json"
        baseline.write_text(json.dumps(globals()["baseline"]()))
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--source-root",
                str(self.root),
                "--check",
                "--baseline",
                str(baseline),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("unexpected: personal_ai.main -> personal_ai.context.travel", result.stdout)

    def test_exact_existing_debt_allowed_but_different_edge_rejected(self):
        self.source("personal_ai/main.py", "import personal_ai.context.travel\n")
        baseline = globals()["baseline"](waivers=[waiver()])
        self.assertEqual(guard.check(guard.inventory(self.root), baseline), [])
        self.source("personal_ai/main.py", "import personal_ai.context.health\n")
        self.assertEqual(len(guard.check(guard.inventory(self.root), baseline)), 2)

    def test_new_facade_import_fails_while_same_leaf_debt_is_waived(self):
        self.source(
            "personal_ai/main.py",
            "import personal_ai.context.travel\nimport personal_ai.api.domains\n",
        )
        self.source("personal_ai/context/travel.py", "VALUE = 1\n")
        self.source("personal_ai/api/domains.py", "VALUE = 1\n")
        current = guard.inventory(self.root)
        result = guard.check(
            current,
            baseline(waivers=[waiver()], facade_waivers=[]),
        )
        self.assertEqual(current["edges"], [{
            "from": "personal_ai.main",
            "to": "personal_ai.context.travel",
            "kind": "static_import",
            "evidence": {"path": "personal_ai/main.py", "lines": [1]},
        }])
        self.assertEqual(result, ["unexpected facade: personal_ai.main -> personal_ai.api.domains"])
        baseline_path = self.root / "waivers.json"
        baseline_path.write_text(json.dumps(baseline(waivers=[waiver()])), encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--source-root",
                str(self.root),
                "--check",
                "--baseline",
                str(baseline_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("unexpected facade: personal_ai.main -> personal_ai.api.domains", completed.stdout)

    def test_existing_facade_edges_require_exact_facade_waivers(self):
        self.source("personal_ai/api/domains.py", "from personal_ai.domains.fixtures import get_fixture\n")
        self.source("personal_ai/domains/fixtures.py", "VALUE = 1\n")
        current = guard.inventory(self.root)
        records = [facade_waiver("personal_ai.api.domains", "personal_ai.domains.fixtures")]
        self.assertEqual(guard.check(current, baseline(facade_waivers=records)), [])

    def test_relative_nested_type_only_and_package_submodule_imports(self):
        self.source("personal_ai/context/travel.py", "raise RuntimeError('must never import')\n")
        self.source("personal_ai/context/__init__.py", "from . import travel\n")
        self.source(
            "personal_ai/main.py",
            "if TYPE_CHECKING:\n from .context import travel\n"
            "def factory():\n from .context.travel import Provider\n",
        )
        edges = guard.inventory(self.root)["edges"]
        self.assertEqual(len(edges), 2)
        self.assertEqual(edges[1]["evidence"]["lines"], [2, 4])
        self.assertEqual(edges[0]["evidence"]["path"], "personal_ai/context/__init__.py")

    def test_example_and_evaluation_consumers_excluded_without_prefix_collision(self):
        for name in (
            "context/travel.py",
            "evaluation/probe.py",
            "context/traveler.py",
        ):
            self.source("personal_ai/" + name, "import personal_ai.context.health\n")
        self.source("personal_ai/api/domainsish.py", "VALUE = 1\n")
        self.source("personal_ai/core.py", "import personal_ai.api.domainsish\n")
        edges = guard.inventory(self.root)["edges"]
        self.assertEqual([e["from"] for e in edges], ["personal_ai.context.traveler"])
        self.assertEqual(guard.inventory(self.root)["facade_edges"], [])
        self.assertFalse(guard.is_example("personal_ai.api.domainsish"))
        self.assertFalse(guard.is_example_facade("personal_ai.api.domainsish"))

    def test_deterministic_sorted_output_and_no_application_import(self):
        self.source("personal_ai/z.py", "import personal_ai.context.health\n")
        first = guard.inventory(self.root)
        self.source("personal_ai/a.py", "import personal_ai.context.travel\n")
        second = guard.inventory(self.root)
        self.assertEqual(second, guard.inventory(self.root))
        self.assertEqual([e["from"] for e in second["edges"]], ["personal_ai.a", "personal_ai.z"])
        self.assertEqual(first["edges"], second["edges"][1:])

    def test_rejects_wildcard_unreviewed_duplicate_and_incomplete_waivers(self):
        invalid = [
            dict(waiver(), to="personal_ai.*"),
            dict(waiver(), review_status="pending"),
            dict(waiver(), rationale=""),
            dict(waiver(), phase="PI-9"),
        ]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ValueError):
                guard.check({"edges": [], "facade_edges": []}, baseline(waivers=[item]))
        with self.assertRaises(ValueError):
            guard.check({"edges": [], "facade_edges": []}, baseline(waivers=[waiver(), waiver()]))

    def test_rejects_semantically_empty_wrong_type_and_malformed_waivers(self):
        invalid = [
            dict(waiver(), rationale="  "),
            dict(waiver(), rationale=123),
            dict(waiver(), rationale=["placeholder"]),
            {key: value for key, value in waiver().items() if key != "phase"},
            dict(waiver(), phase=1),
        ]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ValueError):
                guard.check({"edges": [], "facade_edges": []}, baseline(waivers=[item]))
        malformed = baseline()
        malformed["unexpected"] = True
        with self.assertRaises(ValueError):
            guard.check({"edges": [], "facade_edges": []}, malformed)

    def test_missing_and_malformed_sources_fail_closed(self):
        with self.assertRaises(ValueError):
            guard.inventory(self.root)
        self.source("personal_ai/main.py", "from invalid syntax\n")
        with self.assertRaises(SyntaxError):
            guard.inventory(self.root)

    def test_moved_reference_namespace_is_forbidden_even_without_installed_sources(self):
        self.source("personal_ai/main.py", "from personal_ai_reference_apps import context\n")
        current = guard.inventory(self.root)
        self.assertIn("unexpected: personal_ai.main -> personal_ai_reference_apps", guard.check(current, baseline()))

    def test_removed_legacy_submodule_import_still_fails_guard(self):
        self.source("personal_ai/main.py", "from personal_ai.context import travel\n")
        current = guard.inventory(self.root)
        self.assertIn("unexpected: personal_ai.main -> personal_ai.context.travel", guard.check(current, baseline()))

    def test_repository_existing_edge_and_baseline_are_tracked(self):
        current = guard.inventory(guard.ROOT / "backend/src")
        baseline = json.loads(
            (guard.ROOT / "docs/platform-independence/pi-0-import-waivers.json").read_text()
        )
        self.assertEqual(guard.check(current, baseline), [])
        self.assertEqual(current["edges"], [])
        self.assertEqual(current["facade_edges"], [])



if __name__ == "__main__":
    unittest.main()
