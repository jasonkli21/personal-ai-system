"""Pure standard-library audit contract regressions."""

import json
import unittest

from pi8_check import DOCS, validate_cases


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.cases = json.loads((DOCS / "pi-8-verification.json").read_text())["cases"]

    def test_complete_matrix(self):
        validate_cases(self.cases)

    def test_duplicate_case_rejected(self):
        self.cases[-1] = self.cases[0]
        with self.assertRaisesRegex(ValueError, "exactly once"):
            validate_cases(self.cases)

    def test_missing_roadmap_link_rejected(self):
        self.cases[0]["roadmap"].pop()
        with self.assertRaisesRegex(ValueError, "roadmap mapping"):
            validate_cases(self.cases)

    def test_synthetic_evidence_cannot_pass_live_gate(self):
        case = self.cases[29]
        case.update(observed="synthetic", status="PASS")
        with self.assertRaisesRegex(ValueError, "matching evidence"):
            validate_cases(self.cases)
        case["required"] = "synthetic"
        with self.assertRaisesRegex(ValueError, "requirement changed"):
            validate_cases(self.cases)

    def test_live_attestation_cannot_be_added_to_dated_run(self):
        self.cases[29].update(observed="live", status="PASS")
        with self.assertRaisesRegex(ValueError, "unavailable in this dated run"):
            validate_cases(self.cases)
