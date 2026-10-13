"""Pytest node-level receipts, with no prompts, outputs, credentials or traceback bodies."""

import json
import os
from pathlib import Path

_cases = {}


def pytest_runtest_logreport(report):
    case = _cases.setdefault(report.nodeid, {"nodeid": report.nodeid, "status": "unverified"})
    if report.failed:
        case["status"] = "failed"
    elif report.skipped and case["status"] != "failed":
        case["status"] = "unverified"
    elif report.when == "call" and report.passed and case["status"] != "failed":
        case["status"] = "passed"
    for name, value in report.user_properties:
        if name == "phase36_metrics":
            case["metrics"] = json.loads(value)


def pytest_collection_finish(session):
    for item in session.items:
        _cases.setdefault(item.nodeid, {"nodeid": item.nodeid, "status": "unverified"})


def pytest_sessionfinish(session, exitstatus):
    Path(os.environ["PHASE36_RECEIPTS"]).write_text(
        json.dumps(
            {
                "exit_code": int(exitstatus),
                "cases": sorted(_cases.values(), key=lambda c: c["nodeid"]),
            },
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )
