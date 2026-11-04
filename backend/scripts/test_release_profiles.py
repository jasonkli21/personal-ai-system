"""Evidence cannot waive gates, forge observations or supply its own trust root."""

import ast
import copy
import unittest
from pathlib import Path

from release_profiles import (
    GATES,
    OFFLINE,
    PROFILES,
    canonical,
    read_json,
    sha,
    template,
    validate,
)

SOURCE = {"commit": "a" * 40, "tree": "b" * 40}


class ProfileTest(unittest.TestCase):
    def setUp(self):
        self.manifest = template(SOURCE.copy(), "offline_development", "3.11.13")
        self.pins = {}
        self.receipts = {}

    def check(self):
        return validate(self.manifest, expected=SOURCE, trusted=self.pins, receipts=self.receipts)

    def observe(self, gate, status="PASS"):
        case = next(c for c in self.manifest["cases"] if c["id"] == gate)
        receipt = {
            "schema": "release-receipt-v1",
            "source": SOURCE,
            "profile": self.manifest["profile"],
            "gate": gate,
            "scope": self.manifest["scope"],
            "toolchain": self.manifest["toolchain"],
            "argv": ["python", "-m", "unittest"],
            "prerequisites": ["prepared offline environment"],
            "fence": "Python audit hook",
            "exit": 0 if status == "PASS" else 1,
            "artifacts": {"output": "c" * 64},
            "provenance": "AUTHOR_REPORTED",
        }
        self.receipts[gate] = canonical(receipt)
        self.pins[gate] = sha(self.receipts[gate])
        case.update(status=status, observed=GATES[gate][0], artifact=gate)

    def test_capability_inventory_matches_production_default_boundaries(self):
        settings = Path(__file__).resolve().parents[1] / "src/personal_ai/settings.py"
        tree = ast.parse(settings.read_text())
        defaults = {
            node.target.id: ast.literal_eval(node.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and isinstance(node.value, ast.Constant)
        }
        for flag in (
            "retrieval_enabled",
            "retrieval_context_enabled",
            "retrieval_external_enabled",
            "memory_user_management_enabled",
            "memory_portability_enabled",
            "memory_knowledge_admission_enabled",
            "memory_knowledge_selection_enabled",
            "task_delegation_enabled",
            "task_shopping_enabled",
            "groq_adapter_enabled",
            "cloudflare_adapter_enabled",
            "external_turn_acceptance_enabled",
        ):
            self.assertIs(defaults[flag], False, flag)
        self.assertEqual(defaults["inference_profile"], "offline_fake")
        self.assertEqual(defaults["inference_cost_mode"], "offline_fake")
        self.assertEqual(defaults["inference_summary_profile"], "disabled")

    def test_deterministic_candidate_is_never_release(self):
        for gate in OFFLINE:
            self.observe(gate)
        result = self.check()
        self.assertEqual(result, self.check())
        self.assertEqual(result["candidate"], "PASS")
        self.assertEqual(result["release"], "NO_GO")
        self.assertEqual(result["independent_acceptance"], "PENDING")
        self.observe("validator", "FAIL")
        self.assertEqual(self.check()["candidate"], "FAIL")

    def test_all_profiles_have_fixed_blocked_inventory(self):
        for profile in PROFILES:
            self.manifest = template(SOURCE.copy(), profile, "3.11.13")
            self.assertEqual(self.check()["candidate"], "BLOCKED")
            self.assertEqual(len(self.check()["cases"]), len(GATES))

    def test_closed_inputs_and_gate_waivers(self):
        original = copy.deepcopy(self.manifest)
        mutations = [
            lambda m: m.update(unknown=True),
            lambda m: m.update(schema="release-profile-v0"),
            lambda m: m.update(profile="unknown"),
            lambda m: m.update(contract="2.0.0"),
            lambda m: m["toolchain"].update(build_backend="untrusted"),
            lambda m: m["toolchain"].update(python="3.10.0"),
            lambda m: m["source"].update(commit="c" * 40),
            lambda m: m["source"].update(tree="c" * 40),
            lambda m: m["capabilities"].update(cloud=True),
            lambda m: m["capabilities"].update(cloud=0),
            lambda m: m["scope"].update(operation="write"),
            lambda m: m["cases"].pop(),
            lambda m: m["cases"].append(m["cases"][0]),
            lambda m: m["cases"][0].update(required="E0"),
            lambda m: m["cases"][0].update(owner="author"),
            lambda m: m["cases"][0].update(status="NOT_APPLICABLE"),
            lambda m: m["cases"][0].update(observed="E6"),
            lambda m: m["cases"][0].update(artifact="../../secret"),
        ]
        for mutation in mutations:
            self.manifest = copy.deepcopy(original)
            mutation(self.manifest)
            with self.subTest(manifest=self.manifest), self.assertRaises(ValueError):
                self.check()

    def test_missing_and_tampered_artifacts(self):
        self.observe("validator")
        raw = self.receipts["validator"]
        self.pins.clear()
        with self.assertRaisesRegex(ValueError, "untrusted_artifact"):
            self.check()
        self.pins["validator"] = sha(raw)
        self.receipts["validator"] += b" "
        with self.assertRaisesRegex(ValueError, "artifact_digest"):
            self.check()

    def test_stale_wrong_profile_scope_exit_and_independent_receipts(self):
        for key, value in [
            ("source", {"commit": "c" * 40, "tree": "b" * 40}),
            ("profile", "hosted_opt_in"),
            ("scope", {}),
            ("toolchain", {}),
            ("exit", 1),
            ("exit", False),
            ("provenance", "INDEPENDENT"),
            ("argv", []),
            ("artifacts", {}),
            ("fence", "raw\nsecret"),
        ]:
            self.observe("validator")
            receipt = read_json(self.receipts["validator"])
            receipt[key] = value
            self.receipts["validator"] = canonical(receipt)
            self.pins["validator"] = sha(self.receipts["validator"])
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.check()

    def test_review_reference_is_not_independent_authority(self):
        review = {
            "reviewer": self.manifest["author"],
            "source": SOURCE,
            "profile": "offline_development",
            "manifest_sha256": sha(canonical(self.manifest)),
            "artifact_sha256": "d" * 64,
        }
        self.manifest["review"] = review
        with self.assertRaisesRegex(ValueError, "self_review"):
            self.check()
        review["reviewer"] = "other-name"
        with self.assertRaisesRegex(ValueError, "untrusted_review"):
            self.check()
        result = validate(
            self.manifest, expected=SOURCE, trusted={}, receipts={}, review_pin="d" * 64
        )
        self.assertEqual(result["release"], "NO_GO")
        self.assertEqual(result["independent_acceptance"], "PENDING")
        self.manifest["toolchain"]["python"] = "3.12.0"
        with self.assertRaisesRegex(ValueError, "review_manifest"):
            validate(self.manifest, expected=SOURCE, trusted={}, receipts={}, review_pin="d" * 64)

    def test_review_gate_cannot_be_filled_by_command(self):
        self.manifest = template(SOURCE.copy(), "local_developer_preview", "3.11.13")
        self.observe("independent_review")
        with self.assertRaisesRegex(ValueError, "self_certified_review"):
            self.check()

    def test_duplicate_oversize_deep_and_nonfinite_json(self):
        for raw in [b'{"x":1,"x":2}', b" " * 262145, b"[" * 2000, b'{"x":NaN}']:
            with self.subTest(raw=raw[:40]), self.assertRaises(ValueError):
                read_json(raw)


if __name__ == "__main__":
    unittest.main()
