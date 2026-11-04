"""Closed, deterministic release evidence projection; never a release authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA = "release-profile-v1"
STATES = {"PASS", "FAIL", "BLOCKED", "NOT_RUN", "NOT_APPLICABLE"}
TIERS = {f"E{i}" for i in range(6)}
# Requirements are code-owned. Evidence cannot remove, downgrade or waive them.
GATES = {
    "inventory": ("E0", "release"),
    "validator": ("E1", "release"),
    "historical_integrity": ("E0", "evaluation"),
    "repeat_build": ("E0", "build"),
    "dependency_origin": ("E2", "operator"),
    "source_free_install": ("E2", "operator"),
    "public_protocol": ("E1", "sdk"),
    "signed_identity": ("E2", "identity"),
    "source_safety": ("E1", "source"),
    "attempt_safety": ("E1", "inference"),
    "native_task_resources": ("E2", "runtime"),
    "independent_review": ("E0", "reviewer"),
    "hosted_account_privacy": ("E3", "provider"),
    "cloud_restore_erasure": ("E4", "storage"),
}
OFFLINE = {
    "inventory",
    "validator",
    "historical_integrity",
    "public_protocol",
    "source_safety",
    "attempt_safety",
}
LOCAL = set(GATES) - {"hosted_account_privacy", "cloud_restore_erasure"}
PROFILES = {
    "offline_development": ("synthetic", OFFLINE),
    "local_developer_preview": ("local", LOCAL),
    "hosted_opt_in": ("hosted", LOCAL | {"hosted_account_privacy"}),
    "cloud_operator": ("cloud", set(GATES)),
}
CAPABILITIES = {
    "external_retrieval": False,
    "mcp_source": False,
    "local_model": False,
    "workflow": False,
    "memory_controls": False,
    "memory_portability": False,
    "hosted_inference": False,
    "cloud": False,
    "peer_disclosure": False,
    "mutating_effects": False,
}
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
LABEL = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.:/@+ -]{0,255}")


def require(condition, code):
    if not condition:
        raise ValueError(code)


def closed(value, keys):
    require(type(value) is dict and set(value) == set(keys.split()), "schema_fields")


def label(value):
    require(type(value) is str and LABEL.fullmatch(value) is not None, "invalid_label")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(raw):
    require(isinstance(raw, (bytes, str)) and len(raw) <= 262144, "input_size")

    def unique(pairs):
        value = dict(pairs)
        require(len(value) == len(pairs), "duplicate_field")
        return value

    try:
        return json.loads(
            raw, object_pairs_hook=unique, parse_constant=lambda _: require(False, "invalid_number")
        )
    except (RecursionError, json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("invalid_json") from None


def identity(value):
    closed(value, "commit tree")
    require(all(type(x) is str and HEX40.fullmatch(x) for x in value.values()), "source_identity")


def validate(manifest, *, expected, trusted, receipts, review_pin=None):
    """Pure projection. Pins must come from an independently controlled caller.

    trusted maps artifact IDs to externally checked SHA256 digests; receipts maps
    those IDs to raw receipt bytes. Neither is read from the submitted manifest.
    A matching review pin binds bytes, not reviewer identity or release authority.
    """
    closed(
        manifest,
        "schema source profile contract sdk toolchain capabilities scope author cases review",
    )
    require(manifest["schema"] == SCHEMA, "schema_version")
    identity(expected)
    identity(manifest["source"])
    require(manifest["source"] == expected, "wrong_source")
    profile = manifest["profile"]
    require(type(profile) is str and profile in PROFILES, "unknown_profile")
    topology, required = PROFILES[profile]
    require(manifest["contract"] == "1.2.0" and manifest["sdk"] == "0.1.0", "contract_version")
    closed(manifest["toolchain"], "python build_backend")
    for item in manifest["toolchain"].values():
        label(item)
    require(
        manifest["toolchain"]["build_backend"] == "hatchling-1.27.0"
        and re.fullmatch(r"3[.](?:11|12|13|14)[.][0-9]{1,3}", manifest["toolchain"]["python"]),
        "unsupported_toolchain",
    )
    require(
        type(manifest["capabilities"]) is dict
        and manifest["capabilities"] == CAPABILITIES
        and all(type(v) is bool for v in manifest["capabilities"].values()),
        "defaults_changed",
    )
    scope = manifest["scope"]
    closed(scope, "topology issuer actor application workspace purpose operation")
    require(scope["topology"] == topology and scope["operation"] == "read_only", "scope_mode")
    for item in scope.values():
        label(item)
    label(manifest["author"])
    cases = manifest["cases"]
    require(type(cases) is list and len(cases) == len(GATES), "missing_gate")
    require(all(type(c) is dict for c in cases), "case_type")
    require([c.get("id") for c in cases] == sorted(GATES), "gate_inventory")
    score = []
    for case in cases:
        closed(case, "id required observed status reason owner artifact")
        gate = case["id"]
        tier, owner = GATES[gate]
        require(case["required"] == tier and case["owner"] == owner, "gate_downgrade")
        status, observed = case["status"], case["observed"]
        require(type(status) is str and status in STATES, "status")
        require(observed is None or (type(observed) is str and observed in TIERS), "tier")
        label(case["reason"])
        applicable = gate in required
        require((status == "NOT_APPLICABLE") == (not applicable), "gate_applicability")
        artifact = case["artifact"]
        if status in {"PASS", "FAIL"}:
            require(observed == tier and type(artifact) is str, "unobserved_verdict")
            label(artifact)
            require(artifact in trusted and artifact in receipts, "untrusted_artifact")
            pin, raw = trusted[artifact], receipts[artifact]
            require(
                type(pin) is str
                and HEX64.fullmatch(pin)
                and isinstance(raw, bytes)
                and len(raw) <= 262144
                and sha(raw) == pin,
                "artifact_digest",
            )
            receipt = read_json(raw)
            closed(
                receipt,
                "schema source profile gate scope toolchain argv prerequisites fence exit artifacts provenance",
            )
            require(receipt["schema"] == "release-receipt-v1", "receipt_version")
            require(
                receipt["source"] == expected
                and receipt["profile"] == profile
                and receipt["gate"] == gate
                and receipt["scope"] == scope
                and receipt["toolchain"] == manifest["toolchain"],
                "stale_receipt",
            )
            require(receipt["provenance"] == "AUTHOR_REPORTED", "self_certified_receipt")
            for key in ("argv", "prerequisites"):
                require(type(receipt[key]) is list and 0 < len(receipt[key]) <= 64, "receipt_list")
                for item in receipt[key]:
                    require(
                        type(item) is str and 0 < len(item) <= 1024 and item.isprintable(),
                        "receipt_argument",
                    )
            label(receipt["fence"])
            require(
                type(receipt["exit"]) is int
                and 0 <= receipt["exit"] <= 255
                and (receipt["exit"] == 0) == (status == "PASS"),
                "contradictory_exit",
            )
            outputs = receipt["artifacts"]
            require(type(outputs) is dict and 0 < len(outputs) <= 64, "receipt_artifacts")
            for name, digest in outputs.items():
                label(name)
                require(
                    type(digest) is str and HEX64.fullmatch(digest) is not None, "output_digest"
                )
            # A command receipt alone never supplies independent acceptance.
            require(gate != "independent_review", "self_certified_review")
        else:
            require(observed is None and artifact is None, "contradictory_unobserved")
        score.append(
            {
                "id": gate,
                "status": status,
                "required": tier,
                "owner": owner,
                "mandatory": applicable,
                "observed": observed,
                "reason": "observed-result"
                if status in {"PASS", "FAIL"}
                else "outside-profile"
                if not applicable
                else "evidence-required",
            }
        )
    review = manifest["review"]
    if review is not None:
        closed(review, "reviewer source profile manifest_sha256 artifact_sha256")
        label(review["reviewer"])
        require(review["reviewer"] != manifest["author"], "self_review")
        require(review["source"] == expected and review["profile"] == profile, "wrong_review")
        unsigned = {**manifest, "review": None}
        require(review["manifest_sha256"] == sha(canonical(unsigned)), "review_manifest")
        require(
            type(review_pin) is str
            and HEX64.fullmatch(review_pin)
            and review["artifact_sha256"] == review_pin,
            "untrusted_review",
        )
    failures = any(c["status"] == "FAIL" for c in score if c["mandatory"])
    complete = all(c["status"] == "PASS" for c in score if c["mandatory"])
    return {
        "schema": "release-scorecard-v1",
        "source": expected,
        "profile": profile,
        "candidate": "FAIL" if failures else "PASS" if complete else "BLOCKED",
        "release": "NO_GO",
        "independent_acceptance": "PENDING",
        "review_reference": "PINNED_UNAUTHENTICATED" if review else "MISSING",
        "cases": score,
    }


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def template(source, profile, python):
    topology, required = PROFILES[profile]
    return {
        "schema": SCHEMA,
        "source": source,
        "profile": profile,
        "contract": "1.2.0",
        "sdk": "0.1.0",
        "toolchain": {"python": python, "build_backend": "hatchling-1.27.0"},
        "capabilities": CAPABILITIES.copy(),
        "author": "implementation-author",
        "scope": {
            "topology": topology,
            "issuer": "unverified",
            "actor": "synthetic",
            "application": "release-probe",
            "workspace": "disposable",
            "purpose": "synthetic-conformance",
            "operation": "read_only",
        },
        "cases": [
            {
                "id": gate,
                "required": tier,
                "observed": None,
                "status": "BLOCKED" if gate in required else "NOT_APPLICABLE",
                "reason": "evidence-required" if gate in required else "outside-profile",
                "owner": owner,
                "artifact": None,
            }
            for gate, (tier, owner) in sorted(GATES.items())
        ],
        "review": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument(
        "--trust",
        type=Path,
        help="externally controlled receipt pins, never generated by this command",
    )
    args = parser.parse_args()
    # The caller owns trust-file provenance; matching a digest cannot grant release.
    try:
        raw = args.manifest.open("rb")
        with raw:
            manifest = read_json(raw.read(262145))
        pins, receipts, review_pin = {}, {}, None
        if args.trust:
            with args.trust.open("rb") as handle:
                trust = read_json(handle.read(262145))
            closed(trust, "schema receipts review_sha256")
            require(trust["schema"] == "release-trust-v1", "trust_version")
            require(
                type(trust["receipts"]) is dict and len(trust["receipts"]) <= 64, "trust_inventory"
            )
            for name, entry in trust["receipts"].items():
                label(name)
                closed(entry, "file sha256")
                filename = entry["file"]
                require(
                    type(filename) is str and re.fullmatch(r"[a-zA-Z0-9_-]+[.]json", filename),
                    "receipt_filename",
                )
                pins[name] = entry["sha256"]
                with (args.trust.parent / filename).open("rb") as handle:
                    receipts[name] = handle.read(262145)
            review_pin = trust["review_sha256"]
        result = validate(
            manifest,
            expected={"commit": args.expected_commit, "tree": args.expected_tree},
            trusted=pins,
            receipts=receipts,
            review_pin=review_pin,
        )
    except (ValueError, OSError, TypeError, KeyError):
        print('{"error":"invalid_or_untrusted_evidence","release":"NO_GO"}')
        return 2
    print(canonical(result).decode())
    print(
        f"{result['profile']}: candidate {result['candidate']}; release NO_GO; "
        "independent acceptance pending",
        file=sys.stderr,
    )
    return 0 if result["candidate"] == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
