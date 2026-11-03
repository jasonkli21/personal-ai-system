import unittest

from naming_policy_check import PHASE_PATH, PHASE_TEXT


class NamingPolicyCheckTests(unittest.TestCase):
    def test_rejects_phase_coded_paths_and_visible_labels(self):
        self.assertIsNotNone(PHASE_PATH.search("backend/tests/test_phase21_routing.py"))
        self.assertIsNotNone(PHASE_TEXT.search("Phase 7 · evidence-based comparison"))

    def test_allows_capability_names_and_technical_versions(self):
        self.assertIsNone(PHASE_PATH.search("backend/tests/test_routing_decision_lifecycle.py"))
        self.assertIsNone(PHASE_TEXT.search("two-phase commit uses API v1"))


if __name__ == "__main__":
    unittest.main()
