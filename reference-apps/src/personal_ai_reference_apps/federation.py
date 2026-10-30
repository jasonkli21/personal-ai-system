"""Historical explicit reference federation allowlist."""
from personal_ai.contracts.federation import FederationExportDeclaration
from personal_ai.federation.broker import FederationCase
from personal_ai.federation.deployment import install_federation_metadata

INITIAL_FEDERATION_CASES = (
    FederationCase(
        "health",
        "travel",
        FederationExportDeclaration(
            category="dietary_restrictions",
            provider_id="federation.health_dietary_to_travel",
            fields=("dietary_restrictions",),
            sensitivity="restricted",
        ),
    ),
    FederationCase(
        "health",
        "shopping",
        FederationExportDeclaration(
            category="ergonomic_constraints",
            provider_id="federation.health_ergonomic_to_shopping",
            fields=("ergonomic_constraints",),
            sensitivity="restricted",
        ),
    ),
    FederationCase(
        "travel",
        "shopping",
        FederationExportDeclaration(
            category="trip",
            provider_id="federation.travel_trip_to_shopping",
            fields=("destination", "start_date", "end_date"),
            sensitivity="sensitive",
        ),
    ),
    FederationCase(
        "finance",
        "shopping",
        FederationExportDeclaration(
            category="discretionary_budget",
            provider_id="federation.finance_budget_to_shopping",
            fields=("amount", "currency", "period"),
            sensitivity="restricted",
        ),
    ),
)


def install_reference_federation_metadata(definitions, capabilities):
    return install_federation_metadata(definitions, capabilities, cases=INITIAL_FEDERATION_CASES)
