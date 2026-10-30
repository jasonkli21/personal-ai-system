"""Run optional reference evaluations from the separately installed wheel."""

from __future__ import annotations

import asyncio
import importlib.abc
import json
import sys
from importlib.machinery import PathFinder
from importlib.metadata import distribution
from pathlib import Path

network_attempts = []


def offline_fence(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg"} or (
        event == "socket.__new__" and len(args) > 1 and args[1] in (2, 10)
    ):
        network_attempts.append(event)
        raise PermissionError("PI-1 reference evaluation offline fence")


class RequireInstalledReference(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "personal_ai_reference_apps" or fullname.startswith(
            "personal_ai_reference_apps."
        ):
            spec = PathFinder.find_spec(fullname, path)
            if spec is None or not spec.origin or not Path(spec.origin).is_relative_to(
                Path(sys.prefix)
            ):
                raise AssertionError(f"reference module is not installed: {fullname}")


sys.addaudithook(offline_fence)
sys.meta_path.insert(0, RequireInstalledReference())

import personal_ai_reference_apps
from personal_ai_reference_apps.evaluation.domain import evaluate as evaluate_domain
from personal_ai_reference_apps.evaluation.itinerary_proposals import (
    evaluate as evaluate_itinerary,
)

installed = distribution("personal-ai-reference-apps")
domain_report = evaluate_domain()
itinerary_report = asyncio.run(evaluate_itinerary())
assert domain_report["passed"]
assert domain_report["counts_by_domain"] == {
    "travel": {"fixtures": 4, "passed": 4},
    "shopping": {"fixtures": 6, "passed": 6},
}
assert itinerary_report["passed"] and len(itinerary_report["results"]) == 6
assert itinerary_report["external_providers_called"] is False
assert Path(personal_ai_reference_apps.__file__).is_relative_to(Path(sys.prefix))
assert not network_attempts

print(
    json.dumps(
        {
            "reference_distribution": installed.version,
            "module_root": personal_ai_reference_apps.__file__,
            "domain_counts": domain_report["counts_by_domain"],
            "itinerary_cases": len(itinerary_report["results"]),
            "provider_calls": 0,
            "network_attempts": network_attempts,
        },
        indent=2,
    )
)
