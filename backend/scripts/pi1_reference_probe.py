"""Probe independently installed reference entry points with fake startup inventory."""

import json
import sys
from importlib.metadata import distribution
from pathlib import Path

attempts = []


def fence(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg"} or (
        event == "socket.__new__" and len(args) > 1 and args[1] in (2, 10)
    ):
        attempts.append(event)
        raise PermissionError("PI-1 reference offline fence")


sys.addaudithook(fence)
from fastapi.testclient import TestClient

from personal_ai.applications.registry import default_application_registry
from personal_ai.main import create_app
from personal_ai.persistence import factory as persistence
from personal_ai.settings import Settings, get_settings

assert default_application_registry().application_ids == {"personal_ai"}
settings = Settings(_env_file=None, ai_provider="fake", ai_model="fake", app_environment="test")


class Factory:
    def mutation_repository(self):
        return self

    def required_operation_contracts(self):
        return ()


persistence.persistence_factory = lambda _: Factory()
results = []
for name in ("travel", "shopping", "finance", "health"):
    app = create_app(selected_contributions=(name,))
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert app.state.application_registry.application_ids == {"personal_ai", name}
        paths = app.openapi()["paths"]
        assert ("/v1/travel/itinerary-proposals" in paths) == (name == "travel")
        assert ("/v1/domains" in paths) == (name in {"travel", "shopping"})
        absent = "shopping" if name != "shopping" else "travel"
        assert client.get("/v1/profile", headers={"X-Application-Id": absent}).status_code == 404
        results.append(
            {
                "selected": name,
                "apps": sorted(app.state.application_registry.application_ids),
                "federation_cases": len(app.state.context_runtime_registry.federation_cases),
            }
        )
app = create_app(selected_contributions=("travel", "shopping", "finance", "health"))
app.dependency_overrides[get_settings] = lambda: settings
with TestClient(app):
    assert len(app.state.context_runtime_registry.federation_cases) == 4
assert not attempts
import personal_ai_reference_apps

reference_distribution = distribution("personal-ai-reference-apps")
assert Path(personal_ai_reference_apps.__file__).is_relative_to(Path(sys.prefix))
assert "personal-ai-backend==0.1.0" in (reference_distribution.requires or [])
expected_entries = {
    (group, name)
    for group in (
        "personal_ai.application_contributions",
        "personal_ai.context_contributions",
    )
    for name in ("travel", "shopping", "finance", "health")
}
assert {
    (entry.group, entry.name) for entry in reference_distribution.entry_points
} == expected_entries
print(
    json.dumps(
        {
            "reference_module": personal_ai_reference_apps.__file__,
            "sys_path": sys.path,
            "requires_dist": reference_distribution.requires,
            "entry_points": sorted(
                [entry.group, entry.name, entry.value]
                for entry in reference_distribution.entry_points
            ),
            "selections": results,
            "legacy_four_cases": "PASS",
            "network_attempts": attempts,
        },
        indent=2,
    )
)
