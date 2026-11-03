"""Adversarial structural regressions for the PI-8 audit checker."""

import copy
import json
import unittest

from pi8_check import (
    DOCS,
    HISTORICAL,
    read_json,
    validate_cases,
    validate_checkout,
    validate_ledger,
    validate_receipts,
)


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.ledger = json.loads((DOCS / "pi-8-verification.json").read_text())
        self.cases = copy.deepcopy(self.ledger["cases"])

    def test_complete_historical_matrix(self):
        validate_cases(self.cases)
        validate_ledger(self.ledger)

    def test_duplicate_or_missing_case_rejected(self):
        self.cases[-1] = copy.deepcopy(self.cases[0])
        with self.assertRaisesRegex(ValueError, "exactly once"):
            validate_cases(self.cases)
        with self.assertRaisesRegex(ValueError, "exactly once"):
            validate_cases(self.ledger["cases"][:-1])

    def test_mapping_and_required_evidence_are_fixed(self):
        self.cases[0]["roadmap"].pop()
        with self.assertRaisesRegex(ValueError, "roadmap mapping"):
            validate_cases(self.cases)
        self.cases = copy.deepcopy(self.ledger["cases"])
        self.cases[17]["required"] = "synthetic"
        with self.assertRaisesRegex(ValueError, "requirement changed"):
            validate_cases(self.cases)

    def test_live_and_native_requirements_cannot_be_cleared(self):
        for index in (17, 22, 23, 24, 28, 29):
            with self.subTest(case=self.cases[index]["id"]):
                candidate = copy.deepcopy(self.cases)
                candidate[index].update(status="NOT_APPLICABLE", observed="none")
                with self.assertRaisesRegex(ValueError, "invalid status"):
                    validate_cases(candidate)
                candidate[index].update(status="PASS", observed="static")
                with self.assertRaisesRegex(ValueError, "historical disposition changed"):
                    validate_cases(candidate)

    def test_forged_live_or_installed_evidence_is_rejected(self):
        for index, evidence_class in ((17, "live"), (22, "native"), (28, "live")):
            with self.subTest(case=self.cases[index]["id"]):
                candidate = copy.deepcopy(self.cases)
                candidate[index].update(status="BLOCKED", observed=evidence_class)
                with self.assertRaisesRegex(ValueError, "unavailable in this dated run"):
                    validate_cases(candidate)

    def test_summary_cannot_launder_a_case_disposition(self):
        candidate = copy.deepcopy(self.ledger)
        candidate["cases"][17].update(status="NOT_APPLICABLE", observed="none")
        candidate["counts"] = {"PASS": 21, "BLOCKED": 14, "NOT_APPLICABLE": 1}
        with self.assertRaisesRegex(ValueError, "invalid status"):
            validate_ledger(candidate)
        candidate = copy.deepcopy(self.ledger)
        candidate["counts"] = {"PASS": 21, "BLOCKED": 14, "NOT_APPLICABLE": 1}
        with self.assertRaisesRegex(ValueError, "counts differ"):
            validate_ledger(candidate)

    def test_release_rollup_is_pinned_no_go(self):
        candidate = copy.deepcopy(self.ledger)
        candidate["production"] = "ready"
        with self.assertRaisesRegex(ValueError, "cannot grant release"):
            validate_ledger(candidate)

    def test_historical_pass_cannot_be_downgraded_with_adjusted_counts(self):
        candidate = copy.deepcopy(self.ledger)
        candidate["cases"][7]["status"] = "BLOCKED"
        candidate["counts"] = {"PASS": 20, "BLOCKED": 16}
        with self.assertRaisesRegex(ValueError, "historical disposition changed"):
            validate_ledger(candidate)


class ProvenanceTest(unittest.TestCase):
    def setUp(self):
        self.ledger = json.loads((DOCS / "pi-8-verification.json").read_text())

    def test_exact_sha_and_clean_checkout_required(self):
        calls = []

        def fake_git(*args):
            calls.append(args)
            if args[:2] == ("merge-base", "--is-ancestor"):
                return b""
            if args == ("rev-parse", "HEAD"):
                return (HISTORICAL + "\n").encode()
            if "status" in args:
                return b""
            if args[:2] == ("ls-files", "--others"):
                return b""
            if args == ("ls-files", "-vz"):
                return b"H backend/scripts/pi8_check.py\0"
            if args == ("rev-parse", f"{HISTORICAL}^{{tree}}"):
                return b"1" * 40
            raise AssertionError(args)

        self.assertEqual(validate_checkout(HISTORICAL, fake_git), "1" * 40)
        self.assertIn(("merge-base", "--is-ancestor", "9b4b0f4db358ac97c156a615831dbb81a0a636a9", HISTORICAL), calls)
        self.assertIn(("merge-base", "--is-ancestor", HISTORICAL, HISTORICAL), calls)
        with self.assertRaisesRegex(ValueError, "full reviewer-supplied"):
            validate_checkout("main", fake_git)

    def test_divergent_dirty_or_untracked_checkout_rejected(self):
        for head, status in (("2" * 40, b""), (HISTORICAL, b"?? new.py\0")):
            def fake_git(*args, _head=head, _status=status):
                if args[:2] == ("merge-base", "--is-ancestor"):
                    return b""
                if args == ("rev-parse", "HEAD"):
                    return (_head + "\n").encode()
                if "status" in args:
                    return _status
                if args[:2] == ("ls-files", "--others"):
                    return b""
                if args == ("ls-files", "-vz"):
                    return b"H tracked.py\0"
                return b"1" * 40

            with self.subTest(head=head, status=status), self.assertRaises(ValueError):
                validate_checkout(HISTORICAL, fake_git)

    def test_ignored_source_inside_audited_paths_rejected(self):
        def fake_git(*args):
            if args[:2] == ("merge-base", "--is-ancestor"):
                return b""
            if args == ("rev-parse", "HEAD"):
                return (HISTORICAL + "\n").encode()
            if "status" in args:
                return b""
            if args[:2] == ("ls-files", "--others"):
                return b"backend/src/personal_ai/hidden_policy.py\0"
            if args == ("ls-files", "-vz"):
                return b"H tracked.py\0"
            return b"1" * 40

        with self.assertRaisesRegex(ValueError, "ignored untracked"):
            validate_checkout(HISTORICAL, fake_git)

    def test_author_receipt_schema_rejects_forged_independent_claim(self):
        valid = {
            "schema": "pi8-command-receipts-v2",
            "reviewed_commit": HISTORICAL,
            "commands": [{
                "argv": ["python", "-m", "unittest"],
                "revision": "9b4b0f4db358ac97c156a615831dbb81a0a636a9",
                "cwd": ".",
                "prerequisites": ["prepared Python 3.11 environment"],
                "class": "synthetic",
                "fence": "Python audit hook",
                "exit": 0,
                "counts": {"passed": 1, "failed": 0, "skipped": 0},
                "warnings": 0,
                "artifact_sha256": "a" * 64,
                "provenance": "AUTHOR_REPORTED",
            }],
        }
        validate_receipts(valid)
        forged = copy.deepcopy(valid)
        forged["commands"][0]["provenance"] = "INDEPENDENTLY_REPRODUCED"
        with self.assertRaisesRegex(ValueError, "external reviewer receipt"):
            validate_receipts(forged)
        forged = copy.deepcopy(valid)
        forged["commands"][0]["counts"]["failed"] = 1
        with self.assertRaisesRegex(ValueError, "reports failures"):
            validate_receipts(forged)

    def test_committed_author_receipt_register_is_well_formed(self):
        evidence = json.loads((DOCS / "pi-8-review-verification-v2.json").read_text())
        validate_receipts(evidence)

    def test_historical_v1_bytes_remain_verifiable(self):
        self.assertEqual(self.ledger["schema"], "pi8-audit-v1")
        self.assertEqual(self.ledger["independent_acceptance"], "pending")
        self.assertEqual(self.ledger["production"], "no_go")

    def test_duplicate_or_oversized_json_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate JSON field"):
            read_json(b'{"production":"no_go","production":"ready"}')
        with self.assertRaisesRegex(ValueError, "size limit"):
            read_json(b" " * 512_001)


if __name__ == "__main__":
    unittest.main()
