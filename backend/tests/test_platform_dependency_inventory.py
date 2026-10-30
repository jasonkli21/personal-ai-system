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
        baseline.write_text(json.dumps({"schema_version": 1, "waivers": []}))
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
        baseline = {"schema_version": 1, "waivers": [waiver()]}
        self.assertEqual(guard.check(guard.inventory(self.root), baseline), [])
        self.source("personal_ai/main.py", "import personal_ai.context.health\n")
        self.assertEqual(len(guard.check(guard.inventory(self.root), baseline)), 2)

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
        for name in ("context/travel.py", "evaluation/probe.py", "context/traveler.py"):
            self.source("personal_ai/" + name, "import personal_ai.context.health\n")
        edges = guard.inventory(self.root)["edges"]
        self.assertEqual([e["from"] for e in edges], ["personal_ai.context.traveler"])

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
                guard.check({"edges": []}, {"schema_version": 1, "waivers": [item]})
        with self.assertRaises(ValueError):
            guard.check({"edges": []}, {"schema_version": 1, "waivers": [waiver(), waiver()]})

    def test_missing_and_malformed_sources_fail_closed(self):
        with self.assertRaises(ValueError):
            guard.inventory(self.root)
        self.source("personal_ai/main.py", "from invalid syntax\n")
        with self.assertRaises(SyntaxError):
            guard.inventory(self.root)

    def test_repository_existing_edge_and_baseline_are_tracked(self):
        current = guard.inventory(guard.ROOT / "backend/src")
        baseline = json.loads(
            (guard.ROOT / "docs/platform-independence/pi-0-import-waivers.json").read_text()
        )
        self.assertEqual(guard.check(current, baseline), [])
        self.assertIn(
            ("personal_ai.context.deployment", "personal_ai.context.travel"),
            {(e["from"], e["to"]) for e in current["edges"]},
        )


if __name__ == "__main__":
    unittest.main()
