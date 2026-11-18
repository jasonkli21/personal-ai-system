"""Frozen travel and fitness rows and private application composition."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from time import monotonic

from personal_ai.applications.contracts import (
    ApplicationContextPolicy,
    ApplicationContextRequest,
    ApplicationDefinition,
    CapabilityRegistration,
    ContextFieldPolicy,
    ContextOperationPolicy,
    ContextProviderPolicy,
)
from personal_ai.applications.registry import ApplicationRegistry
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import (
    bind_request_scope,
    bind_verified_principal,
    reset_request_scope,
    reset_verified_principal,
)
from personal_ai.context.assembler import ContextAssembler
from personal_ai.context.planner import ContextPlanner, ContextPlanningRule
from personal_ai.context.providers import ContextProviderCoordinator, StaticContextProviderFactory
from personal_ai.context.tokens import FakeTokenCounter
from personal_ai.settings import Settings

from .client import Authority, Grant, Intent, SourceClient, TurnBudget
from .context import DisclosureAuthority, SourceProvider
from .snapshot import Selection, SnapshotActions, SnapshotIntent
from .source import SCHEMAS, Delegations, FixtureSource, Installations, Record, Service, namespace
from .wire import SCHEMA, decode, encode

NOW = datetime(2030, 1, 2, 9, tzinfo=UTC)
TRAVEL = "travel-demo"
FITNESS = "fitness-demo"
SOURCES = {TRAVEL: "itinerary-demo", FITNESS: "workout-demo"}
FROZEN = (
    ("a", TRAVEL, "trip-a", "v7", {"title": "Demo shuttle A", "platform": "Blue"}),
    ("a", FITNESS, "gym-a", "v2", {"title": "Fixture session A", "duration_minutes": 20}),
    ("b", TRAVEL, "trip-b", "v4", {"title": "Demo shuttle B", "platform": "Green"}),
    ("b", FITNESS, "gym-b", "v3", {"title": "Fixture session B", "duration_minutes": 30}),
    ("a", TRAVEL, "trip-a-ungranted", "v1", {"title": "Unshared shuttle", "platform": "Gray"}),
)


def app_registry(*, ceiling="sensitive", policy_version="application-context-policy-v1"):
    definitions = []
    capabilities = []
    for app, source in SOURCES.items():
        schema = SCHEMAS[app]
        base = ApplicationContextPolicy()
        definitions.append(ApplicationDefinition(
            application_id=app, display_name=app, workspace_kind="required",
            memory_namespace=app, context_provider_ids=(source,),
            context_policy=ApplicationContextPolicy(
                version=policy_version, provider_policies=(*base.provider_policies, ContextProviderPolicy(
                    provider_id=source, operations=(ContextOperationPolicy(
                        operation="search", sensitivity=schema.sensitivity,
                        fields=tuple(ContextFieldPolicy(field=name, sensitivity=schema.sensitivity)
                                     for name in schema.field_types),
                    ),),
                )), maximum_model_sensitivity=ceiling,
            ),
        ))
        capabilities.append(CapabilityRegistration(
            capability_id=source, kind="context_provider", available=True,
        ))
    return ApplicationRegistry(definitions, capabilities)


class Composition:
    def __init__(self):
        self.now = NOW

        def clock():
            return self.now

        self.operator = object()
        self.registry = app_registry()
        self.app_clients = {app: object() for app in SOURCES}
        self.authority = Authority(clock, self.registry)
        self.installations = Installations(self.operator, clock, tuple(SOURCES.values()))
        self.delegations = Delegations(clock, {f"key-{app}": app.encode() for app in SOURCES})
        self.counter = FakeTokenCounter()
        self.sources = {}
        self.binding_requests = {}
        self.principals = {
            owner: AuthenticatedPrincipal(
                "fixture-idp", f"subject-{owner}", f"owner-{owner}", "same@example.invalid",
                int(NOW.timestamp()), True,
            )
            for owner in ("a", "b", "unmapped")
        }
        for app, source_id in SOURCES.items():
            service = Service(f"service-{app}", f"https://{app}.invalid", f"key-{app}")
            self.binding_requests[app] = {
                "schema_version": SCHEMA, "operation": "install", "application_id": app,
                "installation_id": f"install-{app}", "origin": service.origin,
                "service_identity": service.identity, "projection_schema_id": SCHEMAS[app].projection_schema_id,
                "max_sensitivity": "sensitive", "max_ttl_seconds": 300,
            }
            installed = decode(self.installations.mutate(encode(self.binding_requests[app]), self.operator))
            assert installed["source_id"] == source_id
            self.sources[source_id] = FixtureSource(
                self.installations, self.delegations, service, clock, self.authority.authorize_delegation,
            )
        assert not self.authority.grants and not self.authority.memberships

        self.partitions = {}
        self.records = {}
        for owner, app, workspace, revision, data in FROZEN:
            actor = "actor-b" if owner == "b" else None
            principal = self.principals[owner]
            schema = SCHEMAS[app]
            source_id = SOURCES[app]
            partition = namespace(source_id, app, workspace, principal.owner_id, schema.kind)
            self.partitions[owner, app, workspace] = partition
            source = self.sources[source_id]
            self.authority.memberships[
                principal.issuer, principal.subject, app, workspace
            ] = principal.owner_id, actor
            source.memberships.add((principal.subject, actor, partition))
            record = Record(
                "r01", revision, NOW - timedelta(hours=1), NOW, NOW + timedelta(minutes=5),
                schema.sensitivity, tuple(data.items()),
            )
            self.records[workspace] = record
            source.seed(partition, record, watermark=f"w{revision[1:]}")
            if workspace != "trip-a-ungranted":
                grant = Grant(
                    f"grant-{workspace}", principal.issuer, principal.subject, principal.owner_id,
                    actor, app, workspace, source_id, 1, f"runtime-{owner.upper()}",
                    "answer-context", schema.kind, tuple(schema.field_types),
                    ("describe", "search", "fetch"), "sensitive", NOW + timedelta(minutes=5),
                )
                self.authority.grants[grant.id] = grant

        self.client = SourceClient(
            self.installations, self.authority, self.delegations, self.sources, clock, self.app_clients,
        )
        self.snapshots = SnapshotActions(self.client, clock, self.counter, self.app_clients[TRAVEL])

    def subject(self, owner="a", app=TRAVEL, workspace=None):
        workspace = workspace or f"{'trip' if app == TRAVEL else 'gym'}-{owner}"
        principal = self.principals[owner]
        scope = self.authority.scope(principal, app, workspace, "fixture-request")
        intent = Intent(
            SOURCES[app], f"grant-{workspace}", f"runtime-{owner.upper()}",
            "answer-context", tuple(SCHEMAS[app].field_types),
        )
        return principal, scope, intent

    def read(self, operation, subject=None, budget=None, *, caller=None, **parameters):
        principal, scope, intent = subject or self.subject()
        if operation == "search":
            intent = replace(intent, fields=("title",))
            parameters = {"query": "", "limit": 10, "record_kind": SCHEMAS[scope.application_id].kind,
                          **parameters}
        elif operation == "fetch":
            parameters = {"record_ref": "r01", "source_revision": self.records[scope.workspace_id].revision,
                          **parameters}
        return self.client.read(
            operation, principal, scope, intent, budget if budget is not None else self.budget(),
            caller=self.app_clients[scope.application_id] if caller is None else caller, **parameters,
        )

    def budget(self, **limits):
        return TurnBudget(monotonic() + 2, self.counter, **limits)

    def manual(self, *, second=False):
        grant = replace(
            self.authority.grants["grant-trip-a"], id="grant-manual-a",
            recipient="manual-chatgpt", operations=("fetch",),
        )
        self.authority.grants[grant.id] = grant
        selections = [Selection(grant.source_id, grant.id, "r01", "v7", ("title",))]
        if second:
            self.supplement("r02", revision="v1")
            selections.append(Selection(grant.source_id, grant.id, "r02", "v1", grant.fields))
        return SnapshotIntent(grant.recipient, grant.purpose, tuple(selections))

    def supplement(self, ref, *, revision="v1", **updates):
        partition = self.partitions["a", TRAVEL, "trip-a"]
        record = replace(self.records["trip-a"], ref=ref, revision=revision, **updates)
        self.sources[SOURCES[TRAVEL]].seed(partition, record, watermark=f"w-{ref}-{revision}")
        return record

    def assembly(self, subject, *, max_bytes=16_384, max_tokens=256):
        _, scope, intent = subject
        registration = self.registry.registration(scope.application_id)
        context = ApplicationContextRequest(
            definition=registration.definition, scope=scope,
            context_provider_capabilities=registration.context_providers,
        )
        disclosure = DisclosureAuthority(self.client)
        provider = SourceProvider(
            intent.source_id, SCHEMAS[scope.application_id], self.client, intent, self.counter, disclosure,
            self.app_clients[scope.application_id],
        )
        planner = ContextPlanner((ContextPlanningRule(
            rule_id="fixture-records:v1", category="fixture", phrases=("fixture records",),
            provider_id=intent.source_id, operation="search", fields=intent.fields,
            max_bytes=max_bytes, max_tokens=max_tokens, application_ids=(scope.application_id,),
            explanation="Use the owning app's bounded source records.",
        ),), include_default_rules=False)
        assembler = ContextAssembler(
            Settings(
                ai_provider="gemini", ai_model="fixture-model", max_context_tokens=4096,
                max_response_tokens=100, context_safety_margin_tokens=20,
                summary_trigger_tokens=1000, max_summary_tokens=512,
            ),
            self.counter,
            context_provider_coordinator=ContextProviderCoordinator({
                intent.source_id: StaticContextProviderFactory(provider),
            }),
            permission_revalidator=disclosure, context_planner=planner,
        )
        return assembler, context


@contextmanager
def request_identity(principal, scope):
    request = bind_request_scope(scope)
    identity = bind_verified_principal(principal)
    try:
        yield
    finally:
        reset_verified_principal(identity)
        reset_request_scope(request)
