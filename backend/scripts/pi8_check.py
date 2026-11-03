"""Validate immutable PI-8 audit structure without running application commands."""

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs/platform-independence"
GROUPS = {
    "static": (1, 5, 26, 28, 31, 32, 33, 34, 35, 36),
    "installed": (2, 3, 4, 27),
    "synthetic": (6, 7, 8, 9, 10, 11, 12, 14, 16, 17, 19, 20, 21, 22),
    "live": (13, 15, 18, 25, 29, 30),
    "native": (23, 24),
}
REQUIRED = {f"P8-{n:02}": kind for kind, numbers in GROUPS.items() for n in numbers}
MAPPING = (
    (1, 21), (1, 21), (2,), (3, 4), (4,), (5, 6), (7,),
    (8,), (9,), (10,), (11,), (12,), (17,), (18,), (19,),
    (13,), (14, 16), (15, 17, 18), (15, 17, 18), (15, 16),
    (7, 20), (7, 11), (20,), (20,), (20,), (16, 18), (21,),
    (10, 22), (6, 22), (10, 19), (11, 20, 22), (22,), (22,), (22,), (22,), (22,),
)
STATUSES = {"PASS", "FAIL", "BLOCKED", "NOT_RUN"}
HISTORICAL_STATUSES = (
    "PASS", "BLOCKED", "BLOCKED", "BLOCKED", "PASS", "BLOCKED", "BLOCKED", "PASS",
    "PASS", "PASS", "PASS", "PASS", "BLOCKED", "PASS", "BLOCKED", "PASS", "PASS",
    "BLOCKED", "BLOCKED", "PASS", "PASS", "PASS", "BLOCKED", "BLOCKED", "BLOCKED",
    "PASS", "BLOCKED", "PASS", "BLOCKED", "BLOCKED", "PASS", "PASS", "PASS", "PASS",
    "PASS", "PASS",
)
HISTORICAL = "a80236648e2635a267f122ba0fd958cafa09c096"
BASELINE = "9b4b0f4db358ac97c156a615831dbb81a0a636a9"
LEDGER = "docs/platform-independence/pi-8-verification.json"
HISTORICAL_BLOB = "cd4c4dda26b878e8b1ea35843d9032c68d143b69"
RECEIPTS = "docs/platform-independence/pi-8-review-verification-v2.json"
RECEIPT_FIELDS = {
    "argv", "revision", "cwd", "prerequisites", "class", "fence", "exit",
    "counts", "warnings", "artifact_sha256", "provenance",
}
AUDITED_PATHS = (
    ".gitignore", "Makefile", "backend/src", "backend/tests", "backend/scripts",
    "backend/evaluation", "backend/pyproject.toml", "backend/uv.lock",
    "examples/reading-logbook", "reference-apps", "infrastructure",
    "docs/README.md", "docs/current-state.md", "docs/platform-independence",
)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, timeout=10)


def validate_checkout(expected, run_git=git):
    """Require a reviewer-pinned exact commit and an unmodified tracked checkout."""
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{40}", expected):
        raise ValueError("expected a full reviewer-supplied commit SHA")
    run_git("merge-base", "--is-ancestor", BASELINE, expected)
    run_git("merge-base", "--is-ancestor", HISTORICAL, expected)
    head = run_git("rev-parse", "HEAD").decode().strip()
    if head != expected:
        raise ValueError("HEAD differs from the expected commit")
    status = run_git(
        "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
        "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=none",
    )
    if status:
        raise ValueError("checkout has staged, unstaged or untracked changes")
    ignored = run_git(
        "ls-files", "--others", "--ignored", "--exclude-standard", "-z", "--", *AUDITED_PATHS,
    )
    unexpected_ignored = [
        path for path in ignored.decode().split("\0") if path
        and not (path.endswith((".pyc", ".pyo")) or Path(path).name == ".DS_Store")
    ]
    if unexpected_ignored:
        raise ValueError("ignored untracked file inside audited paths")
    if any(entry[:1] != b"H" for entry in run_git("ls-files", "-vz").split(b"\0") if entry):
        raise ValueError("checkout has hidden or unmerged index entries")
    return run_git("rev-parse", f"{expected}^{{tree}}").decode().strip()


def read_json(raw):
    if not isinstance(raw, (bytes, str)) or len(raw) > 512_000:
        raise ValueError("PI-8 evidence exceeds size limit or has invalid type")

    def unique_fields(pairs):
        fields = dict(pairs)
        if len(fields) != len(pairs):
            raise ValueError("duplicate JSON field")
        return fields

    return json.loads(raw, object_pairs_hook=unique_fields)


def validate_cases(cases):
    if not isinstance(cases, list) or [case.get("id") for case in cases] != sorted(REQUIRED):
        raise ValueError("case IDs must appear exactly once in order")
    for case, roadmap, expected_status in zip(cases, MAPPING, HISTORICAL_STATUSES, strict=True):
        case_id = case["id"]
        if set(case) != {"id", "roadmap", "required", "observed", "status", "reproduction", "result"}:
            raise ValueError(f"{case_id}: unexpected fields")
        if case["roadmap"] != [f"A{n:02}" for n in roadmap]:
            raise ValueError(f"{case_id}: roadmap mapping changed")
        if case["required"] != REQUIRED[case_id]:
            raise ValueError(f"{case_id}: evidence requirement changed")
        if case["observed"] not in {*GROUPS, "none"} or case["status"] not in STATUSES:
            raise ValueError(f"{case_id}: invalid status or evidence class")
        if case["status"] != expected_status:
            raise ValueError(f"{case_id}: historical disposition changed")
        if case["status"] in {"PASS", "FAIL"} and case["observed"] != case["required"]:
            raise ValueError(f"{case_id}: verdict requires matching evidence")
        if case["observed"] in {"installed", "native", "live"}:
            raise ValueError(f"{case_id}: evidence unavailable in this dated run")
        if (
            REQUIRED[case_id] in {"installed", "native", "live"}
            and case["status"] not in {"BLOCKED", "FAIL"}
        ):
            raise ValueError(f"{case_id}: unavailable mandatory evidence cannot be cleared")
        if case["status"] == "NOT_RUN" and case["observed"] != "none":
            raise ValueError(f"{case_id}: NOT_RUN requires no observed evidence")
        if not all(isinstance(case[key], str) and case[key].strip()
                   for key in ("reproduction", "result")):
            raise ValueError(f"{case_id}: missing reproduction or result")


def validate_ledger(ledger):
    expected_keys = {"schema", "date", "baseline", "environment", "production", "independent_acceptance", "counts", "cases", "commands", "sha256"}
    if not isinstance(ledger, dict) or set(ledger) != expected_keys:
        raise ValueError("unexpected historical ledger structure")
    if (ledger["schema"], ledger["date"], ledger["baseline"]) != (
        "pi8-audit-v1", "2026-11-03", BASELINE,
    ):
        raise ValueError("unexpected historical ledger identity")
    validate_cases(ledger["cases"])
    if Counter(case["status"] for case in ledger["cases"]) != ledger["counts"] or ledger["counts"] != {
        "PASS": 21, "BLOCKED": 15,
    }:
        raise ValueError("case counts differ from ledger summary")
    if ledger["independent_acceptance"] != "pending" or ledger["production"] != "no_go":
        raise ValueError("PI-8 audit candidate cannot grant release acceptance")


def validate_receipts(evidence):
    if not isinstance(evidence, dict) or set(evidence) != {"schema", "reviewed_commit", "commands"} or (
        evidence["schema"], evidence["reviewed_commit"]
    ) != ("pi8-command-receipts-v2", HISTORICAL):
        raise ValueError("unexpected receipt register identity")
    commands = evidence["commands"]
    if not isinstance(commands, list) or not commands:
        raise ValueError("missing command receipts")
    for receipt in commands:
        if not isinstance(receipt, dict) or set(receipt) != RECEIPT_FIELDS:
            raise ValueError("unexpected receipt fields")
        if receipt["provenance"] != "AUTHOR_REPORTED":
            raise ValueError("independent reproduction requires an external reviewer receipt")
        revision = receipt["revision"]
        if not isinstance(revision, str) or not (
            revision == BASELINE
            or re.fullmatch(rf"WORKTREE:{HISTORICAL}:[0-9a-f]{{64}}", revision)
        ) or receipt["cwd"] != ".":
            raise ValueError("unexpected tested revision or working directory")
        if (receipt["class"], receipt["fence"]) not in {
            ("static", "no application execution"), ("synthetic", "Python audit hook"),
            ("synthetic", "no network-capable application code"),
        }:
            raise ValueError("unsupported receipt evidence class or fence")
        for key in ("argv", "prerequisites"):
            value = receipt[key]
            if not isinstance(value, list) or not value or not all(
                isinstance(item, str) and 0 < len(item.strip()) <= 1024 and item.isprintable()
                for item in value
            ):
                raise ValueError(f"invalid receipt {key}")
        counts = receipt["counts"]
        if not isinstance(counts, dict) or set(counts) != {"passed", "failed", "skipped"}:
            raise ValueError("invalid receipt counts")
        numeric = [*counts.values(), receipt["warnings"], receipt["exit"]]
        if any(type(value) is not int or value < 0 for value in numeric):
            raise ValueError("invalid receipt numeric result")
        if receipt["exit"] == 0 and counts["failed"]:
            raise ValueError("successful command reports failures")
        if not isinstance(receipt["artifact_sha256"], str) or not re.fullmatch(
            r"[0-9a-f]{64}", receipt["artifact_sha256"]
        ):
            raise ValueError("invalid receipt artifact digest")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args()
    tree = validate_checkout(args.expected_commit)
    for revision in (HISTORICAL, args.expected_commit):
        if git("rev-parse", f"{revision}:{LEDGER}").decode().strip() != HISTORICAL_BLOB:
            raise ValueError("historical ledger bytes changed")
    validate_ledger(read_json(git("cat-file", "blob", HISTORICAL_BLOB)))
    validate_receipts(read_json(git("show", f"{args.expected_commit}:{RECEIPTS}")))
    print(f"PI8_TARGET={args.expected_commit} PI8_TREE={tree}")
    print("PI8_LEDGER_STRUCTURE=VALID; EXECUTION_EVIDENCE=AUTHOR_REPORTED; "
          "INDEPENDENT_ACCEPTANCE=PENDING; PRODUCTION=NO_GO")


if __name__ == "__main__":
    main()
