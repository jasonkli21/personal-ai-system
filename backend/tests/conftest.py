"""Explicit empty mutation inventory for environment-independent API fixtures.

The production lifespan still composes installed contributions and runs the
retirement guard. Offline API tests start with no retained mutation contracts;
tests needing populated metadata override the factory with their own repository.
Persistence/cloud suites keep the real factory and are never covered by this fake.
This fixture establishes no PostgreSQL acceptance evidence.
"""

import pytest


@pytest.fixture(autouse=True)
def offline_startup_mutation_inventory(request, monkeypatch):
    if request.node.get_closest_marker(
        "persistence_integration"
    ) or request.node.get_closest_marker("cloud_smoke"):
        return
    from personal_ai.persistence import factory as module

    original = module.persistence_factory

    class EmptyMutationInventory:
        def required_operation_contracts(self):
            return ()

    class StartupFactory:
        def __init__(self, settings):
            self.settings = settings

        def mutation_repository(self):
            return EmptyMutationInventory()

        def __getattr__(self, name):
            return getattr(original(self.settings), name)

    # The lifespan imports this seam at startup. API services retain their normal
    # independently overridden repositories; unknown operations are not faked.
    monkeypatch.setattr(module, "persistence_factory", StartupFactory)
