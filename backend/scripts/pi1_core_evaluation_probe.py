"""Run complete offline planning fixtures without the optional package on sys.path."""

from __future__ import annotations

import importlib.abc
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/src"))
network_attempts = []
reference_import_attempts = []


def offline_fence(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg"} or (
        event == "socket.__new__" and len(args) > 1 and args[1] in (2, 10)
    ):
        network_attempts.append(event)
        raise PermissionError("PI-1 core evaluation offline fence")


class DenyReferencePackage(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "personal_ai_reference_apps" or fullname.startswith(
            "personal_ai_reference_apps."
        ):
            reference_import_attempts.append(fullname)
            raise AssertionError(f"core evaluation imported optional package: {fullname}")


sys.addaudithook(offline_fence)
sys.meta_path.insert(0, DenyReferencePackage())

from personal_ai.applications.registry import default_application_registry
from personal_ai.evaluation import context_planner, planning

assert default_application_registry().application_ids == {"personal_ai"}
context_rows = context_planner.evaluate()
expected_context_ids = {
    "standalone-personal-recall",
    "standalone-profile-units",
    "synthetic-travel-hotel-dates",
    "synthetic-shopping-saved-chair",
    "synthetic-finance-cash-position",
    "synthetic-health-medication-history",
    "ambiguous-travel-and-health-request",
    "optional-provider-unavailable",
    "standalone-profile-unshared-locale",
}
assert {row["fixture"] for row in context_rows} == expected_context_ids
assert len(context_rows) == 9 and all(row["result"] == "passed" for row in context_rows)

planning_result = planning.evaluate()
assert len(planning_result["rows"]) == 30
assert planning_result["decision"] == "non_promotion"
assert planning_result["planner_calls"] == planning_result["planner_tokens"] == 0
assert not network_attempts and not reference_import_attempts

print(
    json.dumps(
        {
            "default_applications": sorted(default_application_registry().application_ids),
            "context_fixture_count": len(context_rows),
            "reference_context_fixture_count": 4,
            "context_fixture_failures": sum(row["result"] != "passed" for row in context_rows),
            "planning_case_count": len(planning_result["rows"]),
            "planning_decision": planning_result["decision"],
            "planner_calls": planning_result["planner_calls"],
            "planner_tokens": planning_result["planner_tokens"],
            "reference_import_attempts": reference_import_attempts,
            "network_attempts": network_attempts,
        },
        indent=2,
    )
)
