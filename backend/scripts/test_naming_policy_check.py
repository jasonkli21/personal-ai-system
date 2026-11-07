import tempfile
import unittest
from pathlib import Path

from naming_policy_check import (
    PHASE_DECLARATION,
    PHASE_PATH,
    PHASE_TEXT,
    active_paths,
    current_doc_files,
    is_allowed_text,
    visible_text,
)


class NamingPolicyCheckTests(unittest.TestCase):
    def test_rejects_phase_coded_paths_and_visible_labels(self):
        self.assertIsNotNone(PHASE_PATH.search("backend/tests/test_" + "phase" + "21_routing.py"))
        self.assertIsNotNone(PHASE_TEXT.search("Phase " + "7 · evidence-based comparison"))
        self.assertIsNotNone(PHASE_TEXT.search("test_" + "phase" + "_five" + "_research"))
        self.assertIsNotNone(PHASE_DECLARATION.search("class Legacy" + "PI" + "4"))

    def test_allows_capability_names_and_technical_versions(self):
        self.assertIsNone(PHASE_PATH.search("backend/tests/test_routing_decision_lifecycle.py"))
        self.assertIsNone(PHASE_TEXT.search("two-phase commit uses API v1"))
        self.assertIsNone(PHASE_TEXT.search("P0 acceptance priority and P1 follow-up"))

    def test_exact_compatibility_exception_is_scoped_to_path_and_identifier(self):
        identifier = "phase" + "8-run"
        self.assertTrue(
            is_allowed_text(
                "backend/src/personal_ai/agents/research/iterative/service.py",
                identifier,
                f'uuid5(namespace, "{identifier}")',
            )
        )
        self.assertFalse(
            is_allowed_text(
                "backend/tests/test_unrelated.py",
                identifier,
                f'uuid5(namespace, "{identifier}")',
            )
        )
        self.assertFalse(
            is_allowed_text(
                "backend/src/personal_ai/agents/research/iterative/service.py",
                "phase" + "99-run",
                f'new comment: "{"phase" + "99-run"}"',
            )
        )
        self.assertFalse(
            is_allowed_text(
                "backend/scripts/naming_policy_check.py",
                "Phase " + "99",
                f'new comment: "{"Phase " + "99"}"',
            )
        )

    def test_active_paths_and_current_docs_are_scanned(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / ("backend/src/personal_ai/" + "pi" + "4_adapter.py")
            source.parent.mkdir(parents=True)
            source.write_text("", encoding="utf-8")
            current_doc = root / "docs/current-guide.md"
            current_doc.parent.mkdir(parents=True)
            current_doc.write_text("Current API guide", encoding="utf-8")
            historical_doc = root / ("docs/" + "phase" + "-4-implementation-plan.md")
            historical_doc.write_text("Historical plan", encoding="utf-8")
            archived_prd = root / "docs/personal-ai-system-dynamic-reasoning-engine-prd.md"
            archived_prd.write_text("PI" + "-7 historical roadmap", encoding="utf-8")
            phase_current_doc = root / ("docs/phase-" + "99-current-guide.md")
            phase_current_doc.write_text("Phase " + "99 current guide", encoding="utf-8")
            experiment_doc = root / "experiments/memory/README.md"
            experiment_doc.parent.mkdir(parents=True)
            experiment_doc.write_text("Current experiment guide", encoding="utf-8")
            phase_experiment_doc = root / "experiments/ranking/README.md"
            phase_experiment_doc.parent.mkdir(parents=True)
            phase_experiment_doc.write_text("Phase " + "18 ranking guide", encoding="utf-8")
            historical_stabilization_doc = root / "stabilization/2026-11-01-report.md"
            historical_stabilization_doc.parent.mkdir(parents=True)
            historical_stabilization_doc.write_text("Phase " + "18 historical", encoding="utf-8")
            self.assertEqual(
                active_paths(root),
                [
                    "backend/src/personal_ai/" + "pi" + "4_adapter.py",
                    "docs/phase-" + "99-current-guide.md",
                ],
            )
            visible_errors = visible_text(root)
            self.assertTrue(any("experiments/ranking/README.md" in error for error in visible_errors))
            current_docs = {path.relative_to(root).as_posix() for path in current_doc_files(root)}
            self.assertIn("experiments/memory/README.md", current_docs)
            self.assertNotIn("docs/personal-ai-system-dynamic-reasoning-engine-prd.md", current_docs)
            self.assertNotIn("stabilization/2026-11-01-report.md", current_docs)

            current_doc.write_text("Phase " + "12" + " behavior", encoding="utf-8")
            self.assertIsNotNone(PHASE_TEXT.search(current_doc.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
