"""Probe independently installed reference entry points with fake startup inventory."""

import json
import sys

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

print(
    json.dumps(
        {
            "reference_module": personal_ai_reference_apps.__file__,
            "selections": results,
            "legacy_four_cases": "PASS",
            "network_attempts": attempts,
        },
        indent=2,
    )
)
