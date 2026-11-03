"""Validate PI-8's dated evidence without running application or operator commands."""

import hashlib
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
STATUSES = {"PASS", "FAIL", "BLOCKED", "NOT_RUN", "NOT_APPLICABLE"}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, timeout=10)


def source_hashes(baseline):
    # Use the baseline inventory so a reviewer gets the same input set before
    # and after committing the audit. Audit code and its tests are added explicitly.
    paths = git(
        "ls-tree", "-rz", "--name-only", baseline, "--",
        "backend/src", "backend/tests", "backend/scripts", "backend/evaluation",
        "backend/pyproject.toml", "backend/uv.lock", "examples/reading-logbook",
        "reference-apps", "infrastructure", "docs/platform-independence",
    ).decode().strip("\0").split("\0")
    paths += [".gitignore", "Makefile", "backend/scripts/pi8_check.py", "backend/scripts/test_pi8_check.py"]
    paths.remove("docs/platform-independence/README.md")
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in sorted(paths)}


def validate_cases(cases):
    if [case["id"] for case in cases] != sorted(REQUIRED):
        raise ValueError("case IDs must appear exactly once in order")
    for case, roadmap in zip(cases, MAPPING, strict=True):
        case_id = case["id"]
        if set(case) != {"id", "roadmap", "required", "observed", "status", "reproduction", "result"}:
            raise ValueError(f"{case_id}: unexpected fields")
        if case["roadmap"] != [f"A{n:02}" for n in roadmap]:
            raise ValueError(f"{case_id}: roadmap mapping changed")
        if case["required"] != REQUIRED[case_id]:
            raise ValueError(f"{case_id}: evidence requirement changed")
        if case["observed"] not in {*GROUPS, "none"} or case["status"] not in STATUSES:
            raise ValueError(f"{case_id}: invalid status or evidence class")
        if case["status"] in {"PASS", "FAIL"} and case["observed"] != case["required"]:
            raise ValueError(f"{case_id}: verdict requires matching evidence")
        if case["observed"] in {"installed", "native", "live"}:
            raise ValueError(f"{case_id}: evidence unavailable in this dated run")
        if not all(isinstance(case[key], str) and case[key].strip()
                   for key in ("reproduction", "result")):
            raise ValueError(f"{case_id}: missing reproduction or result")


def main():
    path = DOCS / "pi-8-verification.json"
    if path.stat().st_size > 512_000:
        raise ValueError("PI-8 ledger exceeds size limit")
    ledger = json.loads(path.read_text())
    if ledger["schema"] != "pi8-audit-v1" or ledger["date"] != "2026-11-03":
        raise ValueError("unexpected schema or audit date")
    validate_cases(ledger["cases"])
    if Counter(case["status"] for case in ledger["cases"]) != ledger["counts"]:
        raise ValueError("case counts differ from ledger summary")
    baseline = ledger["baseline"]
    if not re.fullmatch("[0-9a-f]{40}", baseline):
        raise ValueError("expected full baseline revision")
    git("merge-base", "--is-ancestor", baseline, "HEAD")
    if source_hashes(baseline) != ledger["sha256"]:
        raise ValueError("PI-8 audited inputs differ from dated evidence")
    if ledger["independent_acceptance"] != "pending" or ledger["production"] != "no_go":
        raise ValueError("PI-8 audit candidate cannot grant release acceptance")
    print("PI8_LEDGER=VALID (36 cases, A01–A22, input hashes; release no_go)")


if __name__ == "__main__":
    main()
