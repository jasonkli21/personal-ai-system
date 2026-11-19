"""Private ASGI composition over the existing application and source contracts."""

import json
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from threading import Lock, RLock
from uuid import uuid4

from pydantic import BaseModel, ConfigDict
from starlette.middleware import Middleware
from starlette.responses import JSONResponse

from personal_ai.api import dependencies as deps
from personal_ai.api.consumer_contract import OPERATIONS
from personal_ai.applications.contracts import (
    ApplicationContextPolicy,
    ApplicationDefinition,
    CapabilityRegistration,
    ContextFieldPolicy,
    ContextOperationPolicy,
    ContextProviderPolicy,
)
from personal_ai.applications.registry import (
    ApplicationContribution,
    ApplicationContributionCatalog,
)
from personal_ai.auth.application_clients import (
    client_binding_namespace,
    external_conversation_namespace,
    require_current_client_authority,
)
from personal_ai.auth.directory import IdentityMappingConflict, InMemoryPrincipalDirectory
from personal_ai.auth.scope import (
    ApplicationScope,
    current_request_scope,
    current_verified_principal,
)
from personal_ai.auth.verification import principal_from_google_token
from personal_ai.context.planner import ContextPlanningRule
from personal_ai.context.profile import InMemoryGlobalProfileRepository
from personal_ai.context.providers import (
    ContextOperationSpec,
    ContextPreparationError,
    ContextProviderError,
    ContextProviderSpec,
)
from personal_ai.context.repositories import InMemorySummaryRepository
from personal_ai.context.runtime import (
    ContextRuntimeContribution,
    ContextRuntimeContributionCatalog,
)
from personal_ai.context.tokens import FakeTokenCounter
from personal_ai.context.traces import InMemoryContextTraceRepository
from personal_ai.llm.execution import ExecutionPair
from personal_ai.main import create_app
from personal_ai.settings import Settings, get_settings
from personal_ai.storage.fake import InMemoryConversationRepository, InMemoryMessageRepository

from .client import Authority, Grant, Intent, SourceClient, TurnBudget
from .context import Itinerary, Workout, context_item
from .fixtures import FITNESS, TRAVEL
from .source import (
    SCHEMAS,
    Delegations,
    FixtureSource,
    Installations,
    Record,
    Service,
    SourceSchema,
    is_fresh,
    namespace,
)
from .wire import SCHEMA, ProtocolError, decode, digest, encode

ISSUER = "https://accounts.google.com"
HUMANS = ("synthetic-human-a", "synthetic-human-b")
RECIPIENT = "fixture-free-model"
MODEL_PURPOSE = "inference-disclosure"
RUNTIME_PURPOSE = "answer-context"
RUNTIME = "pas-runtime"
GRANT_PREFIX = "shared-source:"
PROJECTION_BYTES = 4096
PROJECTION_TOKENS = 256
SOURCE_SECONDS = 2.0
MAX_AUTHORITY_READS = 128
_authority_reads = ContextVar("shared_service_authority_reads", default=None)


def verified_actor(principal):
    return f"{principal.issuer}|{principal.subject}"


def source_actor(principal):
    return "actor:" + digest(verified_actor(principal))


def source_scope(principal, scope):
    if (scope.owner_id, scope.acting_user_id) != (principal.owner_id, verified_actor(principal)):
        raise ProtocolError("unavailable")
    return scope.model_copy(update={"acting_user_id": source_actor(principal)})


class ReadingProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    label: str


@dataclass(frozen=True)
class Contribution:
    app: str
    source: str
    schema: SourceSchema
    fields: tuple[str, ...]
    payload: type[BaseModel]
    workspace_kind: str = "required"


TRAVEL_APP = Contribution(TRAVEL, "itinerary-demo", SCHEMAS[TRAVEL], ("platform",), Itinerary)
FITNESS_APP = Contribution(
    FITNESS,
    "workout-demo",
    SCHEMAS[FITNESS],
    ("duration_minutes",),
    Workout,
)
READING_APP = Contribution(
    "reading-demo",
    "reading-records",
    SourceSchema("book", "reading-projection-v1", (("title", str), ("label", str)), "personal"),
    ("label",),
    ReadingProjection,
    "optional",
)


class HumanDirectory(InMemoryPrincipalDirectory):
    """The fixture's explicit human enrollment, separate from domain membership."""

    def __init__(self, recovery_current):
        super().__init__()
        self.checks = Counter()
        self.recovery_current = recovery_current
        self.native = None

    def ensure_active(self, principal, *, correlation_id):
        self.checks["identity"] += 1
        if (
            not self.recovery_current()
            or principal.issuer != ISSUER
            or principal.subject not in HUMANS
        ):
            raise IdentityMappingConflict
        if self.native is not None:
            if self.native.owner_is_fenced(principal.owner_id):
                raise IdentityMappingConflict
            self.native.ensure_active(principal, correlation_id=correlation_id)
            return
        super().ensure_active(principal, correlation_id=correlation_id)

    def owner_is_fenced(self, owner_id):
        return not self.recovery_current() or (
            self.native is not None and self.native.owner_is_fenced(owner_id)
        )


@dataclass(frozen=True)
class ScopedGrant(Grant):
    client_namespace: str = ""


class OwnerSourceControls(Authority):
    """Extend the existing synthetic authority with revision-checked owner controls."""

    def __init__(self, clock, installations, contributions, recovery_current):
        super().__init__(clock, registry=None)
        self.installations = installations
        self.contributions = {item.app: item for item in contributions}
        self.recovery_current = recovery_current
        self.links = {}
        self._lock = RLock()

    def is_member(self, principal, application_id, workspace_id):
        with self._lock:
            membership = self.memberships.get(
                (principal.issuer, principal.subject, application_id, workspace_id)
            )
            return self.recovery_current() and membership == (
                principal.owner_id,
                source_actor(principal),
            )

    def enroll(self, principal, app, workspace):
        with self._lock:
            self.memberships[principal.issuer, principal.subject, app, workspace] = (
                principal.owner_id,
                source_actor(principal),
            )

    def owner_control(
        self,
        principal,
        app,
        workspace,
        binding,
        *,
        operation,
        expected_revision,
        recipient=None,
        fields=(),
        expires_at=None,
    ):
        # Control receives a separately verified owner. A data-lane token or
        # a membership/grant echo cannot call this internal control.
        self.require_principal(principal)
        if (principal.issuer, principal.audience, principal.authorized_party) != (
            ISSUER,
            "owner-control",
            "owner-control",
        ):
            raise ProtocolError("unauthenticated")
        if app not in self.contributions or not self.recovery_current():
            raise ProtocolError("unavailable")
        key = principal.owner_id, app, workspace, binding
        with self._lock:
            revision, linked = self.links.get(key, (0, False))
            if expected_revision != revision:
                raise ProtocolError("stale_dependency")
            if operation == "disconnect":
                # This lane deliberately survives loss of data membership.
                self.links[key] = revision + 1, False
                for identifier, grant in tuple(self.grants.items()):
                    if self._key(grant) == key:
                        self.grants.pop(identifier)
                return revision + 1
            if not self.is_member(principal, app, workspace):
                raise ProtocolError("unavailable")
            if operation == "link" and not linked:
                self.links[key] = revision + 1, True
                return revision + 1
            if not linked or operation not in {"grant", "revoke"}:
                raise ProtocolError("unavailable")
            purposes = {
                RUNTIME: RUNTIME_PURPOSE,
                RECIPIENT: MODEL_PURPOSE,
                "manual-chatgpt": "manual-export",
                "chatgpt-mcp": "mcp-read",
                "local-siwc": "local-inference",
            }
            purpose = purposes.get(recipient)
            if purpose is None:
                raise ProtocolError("invalid_request")
            current = self.find(key, purpose, recipient, required=False)
            if operation == "revoke":
                if current is None:
                    raise ProtocolError("unavailable")
                self.grants.pop(current.id)
            else:
                config = self.contributions[app]
                install = self.installations.active(config.source)
                if (
                    not fields
                    or len(fields) != len(set(fields))
                    or not set(fields) <= install.schema.field_types.keys()
                    or expires_at is None
                    or not self.clock()
                    < expires_at
                    <= min(install.expires_at, self.clock() + timedelta(minutes=5))
                ):
                    raise ProtocolError("invalid_request")
                identifier = current.id if current else GRANT_PREFIX + uuid4().hex
                self.grants[identifier] = ScopedGrant(
                    identifier,
                    principal.issuer,
                    principal.subject,
                    principal.owner_id,
                    source_actor(principal),
                    app,
                    workspace,
                    install.source_id,
                    install.epoch,
                    recipient,
                    purpose,
                    config.schema.kind,
                    tuple(fields),
                    ("search", "fetch") if recipient == RUNTIME else ("fetch",),
                    config.schema.sensitivity,
                    expires_at,
                    version=revision + 1,
                    epoch=revision + 1,
                    client_namespace=binding,
                )
            self.links[key] = revision + 1, True
            return revision + 1

    def _key(self, grant):
        return grant.owner, grant.app, grant.workspace, grant.client_namespace

    def allows_request(self, scope, binding):
        with self._lock:
            key = scope.owner_id, scope.application_id, scope.workspace_id, binding
            return self.recovery_current() and self.links.get(key, (0, True))[1]

    def find(self, key, purpose, recipient, *, required=True):
        with self._lock:
            grant = next(
                (
                    row
                    for row in self.grants.values()
                    if self._key(row) == key
                    and (row.purpose, row.recipient) == (purpose, recipient)
                ),
                None,
            )
        if grant is None and required:
            raise ProtocolError("unavailable")
        return grant

    def authorize(self, principal, scope, intent, operation, install):
        require_current_client_authority()
        with self._lock:
            grant = super().authorize(principal, scope, intent, operation, install)
            if grant.client_namespace != external_conversation_namespace():
                raise ProtocolError("unavailable")
            return grant

    def authorize_delegation(self, claims, install):
        with self._lock:
            return super().authorize_delegation(claims, install)


class SourcePermissions:
    """Rebuild payload-free dependencies from independent source metadata on reuse."""

    permission_namespaces = (GRANT_PREFIX,)

    def __init__(self, authority, client):
        self.authority = authority
        self.client = client

    def supports(self, dependency):
        return dependency.permission_id.startswith(GRANT_PREFIX)

    def dependency(self, grant, install, entity, revision, watermark):
        from personal_ai.contracts.context_references import ContextPermissionDependency

        return ContextPermissionDependency(
            source_scope=ApplicationScope(application_id=grant.app, workspace_id=grant.workspace),
            entity_ref=entity,
            source_revision=revision,
            permission_id=grant.id,
            version=digest(
                [
                    grant.dependency_version,
                    install.revision,
                    watermark,
                    self.authority.policy_fingerprint(grant.app),
                    grant.client_namespace,
                    grant.recipient,
                    grant.purpose,
                    grant.fields,
                ]
            ),
            purpose=grant.purpose,
            owner_id=grant.owner,
            acting_user_id=f"{grant.issuer}|{grant.subject}",
        )

    def is_current(self, dependency):
        principal, scope = current_verified_principal(), current_request_scope()
        if not principal or not scope or not dependency.entity_ref:
            return False
        require_current_client_authority()
        scope = source_scope(principal, scope)
        with self.authority._lock:
            grant = self.authority.grants.get(dependency.permission_id)
            if grant is None:
                return False
            install = self.client.installations.active(grant.source_id)
            intent = Intent(grant.source_id, grant.id, grant.recipient, grant.purpose, grant.fields)
            self.authority.authorize(principal, scope, intent, "fetch", install)
        source = self.client.sources[grant.source_id]
        reads = _authority_reads.get()
        if reads is None or not reads.take():
            return False
        raw = encode(
            {
                "schema_version": SCHEMA,
                "operation": "fetch",
                "source_id": grant.source_id,
                "application_id": scope.application_id,
                "workspace_id": scope.workspace_id,
                "record_ref": dependency.entity_ref.entity_id,
                "source_revision": dependency.source_revision,
            }
        )
        delegation = self.client.delegations.issue(
            raw,
            grant,
            scope,
            source.service,
            "fetch",
            grant.fields,
        )
        watermark, record = source.attest_record(raw, delegation)
        with self.authority._lock:
            return (
                self.authority.grants.get(grant.id) == grant
                and self.client.installations.active(grant.source_id) == install
                and is_fresh(record, install, grant.expires_at, self.authority.clock())
                and dependency
                == self.dependency(
                    grant,
                    install,
                    dependency.entity_ref,
                    record.revision,
                    watermark,
                )
            )


class SharedSourceProvider:
    """One planned installation and a separate exact grant for the model recipient."""

    def __init__(self, config, client, counter, permissions, caller):
        self.spec = ContextProviderSpec(
            provider_id=config.source,
            source_class="domain_current",
            source_version=SCHEMA,
            maximum_items_per_call=1,
            operations=(
                ContextOperationSpec(
                    operation="search",
                    allowed_fields=config.fields,
                    maximum_results=1,
                    maximum_bytes=PROJECTION_BYTES,
                    maximum_timeout_seconds=SOURCE_SECONDS,
                ),
            ),
        )
        self.config = config
        self.client = client
        self.counter = counter
        self.permissions = permissions
        self.caller = caller

    def validate_selection(self, selection, inputs):
        if (
            inputs.scope.application_id != self.config.app
            or inputs.scope.workspace_id is None
            or selection.fields != self.config.fields
        ):
            raise ContextPreparationError("context_source_not_authorized")

    def fetch(self, selection, scope, *, deadline):
        with hold_worker_slot():
            return self._fetch(selection, scope, deadline=deadline)

    def _fetch(self, selection, scope, *, deadline):
        authority = self.permissions.authority
        key = (
            scope.owner_id,
            scope.application_id,
            scope.workspace_id,
            external_conversation_namespace(),
        )
        principal = current_verified_principal()
        try:
            scope = source_scope(principal, scope)
            runtime = authority.find(key, RUNTIME_PURPOSE, RUNTIME)
            inference = authority.find(key, MODEL_PURPOSE, RECIPIENT)
            install = self.client.installations.active(self.config.source)
            model_intent = Intent(
                install.source_id,
                inference.id,
                RECIPIENT,
                MODEL_PURPOSE,
                selection.fields,
            )
            authority.authorize(principal, scope, model_intent, "fetch", install)
            authority.field_sensitivity(install, inference, selection.fields)
            budget = TurnBudget(
                deadline,
                self.counter,
                max_bytes=selection.max_bytes,
                max_tokens=selection.max_tokens,
                max_results=selection.max_results,
            )
            search_intent = Intent(
                install.source_id,
                runtime.id,
                RUNTIME,
                RUNTIME_PURPOSE,
                ("title",),
            )
            page = self.client.read(
                "search",
                principal,
                scope,
                search_intent,
                budget,
                caller=self.caller,
                record_kind=self.config.schema.kind,
                query="",
                limit=selection.max_results,
            )
            if not page.value.items or page.value.next_cursor is not None:
                raise ProtocolError("unavailable")
            projected = tuple(
                self.client.read(
                    "fetch",
                    principal,
                    scope,
                    replace(search_intent, fields=selection.fields),
                    budget,
                    caller=self.caller,
                    record_ref=hit.record_ref,
                    source_revision=hit.source_revision,
                )
                for hit in page.value.items
            )
            self.client.revalidate(page, principal, scope, self.caller)
            items = []
            for result in projected:
                self.client.revalidate(result, principal, scope, self.caller)
                budget.check()
                item = context_item(result, payload_type=self.config.payload)
                entity = item.entity_refs[0].model_copy(update={"entity_id": digest(item.item_id)})
                deps = tuple(
                    self.permissions.dependency(
                        grant,
                        install,
                        entity,
                        result.value.source_revision,
                        result.value.watermark,
                    )
                    for grant in (runtime, inference)
                )
                if not all(self.permissions.is_current(dep) for dep in deps):
                    raise ProtocolError("stale_dependency")
                model_expiry = min(inference.expires_at, item.expires_at)
                items.append(
                    item.model_copy(
                        update={
                            "item_id": entity.entity_id,
                            "entity_refs": (),  # Scope and grant identities stay with PAS.
                            "source_refs": tuple(
                                ref.model_copy(update={"reference_id": entity.entity_id})
                                for ref in item.source_refs
                            ),
                            "expires_at": model_expiry,
                            "permission_dependencies": deps,
                            "source_version": GRANT_PREFIX
                            + digest([result.value.source_revision, result.value.watermark]),
                        }
                    )
                )
            return tuple(items)
        except ProtocolError:
            raise ContextProviderError("context_source_not_authorized") from None


_worker_slot = ContextVar("shared_service_worker_slot", default=None)


class AuthorityReads:
    def __init__(self):
        self._used = 0
        self._lock = Lock()

    def take(self):
        with self._lock:
            if self._used >= MAX_AUTHORITY_READS:
                return False
            self._used += 1
            return True


@contextmanager
def hold_worker_slot():
    slot = _worker_slot.get()
    if slot is None:
        raise ContextPreparationError("context_capacity_exceeded")
    slots, client = slot
    with slots._lock:
        if client not in slots.active:
            raise ContextPreparationError("context_capacity_exceeded")
        slots.active[client] += 1
    try:
        yield
    finally:
        slots.release(client)


class SharedSlots:
    """Reject overload before provider work; retain slots through ASGI cleanup."""

    def __init__(self, app):
        self.app = app
        self.active = Counter()
        self._lock = Lock()

    async def __call__(self, scope, receive, send):
        client = external_conversation_namespace()
        if client is None:
            await self.app(scope, receive, send)
            return
        budget = _authority_reads.set(AuthorityReads())
        try:
            await self._serve(client, scope, receive, send)
        finally:
            _authority_reads.reset(budget)

    async def _serve(self, client, scope, receive, send):
        if scope["method"] != "POST" or not scope["path"].endswith(
            ("/context-preview", "/continue")
        ):
            await self.app(scope, receive, send)
            return
        with self._lock:
            admitted = len(self.active) < 2 and client not in self.active
            if admitted:
                self.active[client] = 1
        if not admitted:
            await JSONResponse(
                {"error": {"code": "context_capacity_exceeded", "message": "Try again later."}},
                status_code=429,
                headers={"Retry-After": "1"},
            )(scope, receive, send)
            return
        bound = _worker_slot.set((self, client))
        try:
            await self.app(scope, receive, send)
        finally:
            _worker_slot.reset(bound)
            self.release(client)

    def release(self, client):
        with self._lock:
            self.active[client] -= 1
            if self.active[client] == 0:
                del self.active[client]


def make_application(config, authority):
    baseline = ApplicationContextPolicy()
    definition = ApplicationDefinition(
        application_id=config.app,
        display_name=config.app,
        workspace_kind=config.workspace_kind,
        memory_namespace=config.app,
        context_provider_ids=(config.source,),
        context_policy=ApplicationContextPolicy(
            maximum_model_sensitivity="sensitive",
            provider_policies=(
                *tuple(
                    provider
                    for provider in baseline.provider_policies
                    if provider.provider_id == "conversation_history"
                ),
                ContextProviderPolicy(
                    provider_id=config.source,
                    operations=(
                        ContextOperationPolicy(
                            operation="search",
                            sensitivity=config.schema.sensitivity,
                            fields=tuple(
                                ContextFieldPolicy(
                                    field=name, sensitivity=config.schema.sensitivity
                                )
                                for name in config.schema.field_types
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    return ApplicationContribution(
        (definition,),
        (
            CapabilityRegistration(
                capability_id=config.source,
                kind="context_provider",
                available=True,
            ),
        ),
        workspace_authorizers={config.app: authority} if authority is not None else {},
    )


class SharedService:
    def __init__(
        self,
        path,
        *,
        selected=(TRAVEL_APP, FITNESS_APP),
        recovery_current=lambda: True,
        without_workspace_authorizer=frozenset(),
    ):
        self.bindings = []
        self.policy_file = path / "application-clients.json"
        self.settings = Settings(
            _env_file=None,
            app_environment="test",
            ai_provider="fake",
            ai_model="fixture-model",
            auth_mode="google_oidc",
            auth_required=True,
            auth_audience="owner-control",
            auth_allowed_emails=("same@example.invalid",),
            auth_hosted_domain="example.invalid",
            auth_application_clients_file=str(self.policy_file),
            max_context_tokens=4096,
            max_response_tokens=100,
            context_safety_margin_tokens=20,
            summary_trigger_tokens=1000,
            max_summary_tokens=512,
            request_timeout_seconds=5,
        )
        self.now = datetime.now(UTC)
        clock = lambda: self.now
        self.operator = object()
        self.selected = {item.app: item for item in selected}
        self.installations = Installations(
            self.operator,
            clock,
            (item.source for item in selected),
            schemas={item.app: item.schema for item in selected},
        )
        self.controls = OwnerSourceControls(clock, self.installations, selected, recovery_current)
        self.directory = HumanDirectory(recovery_current)
        self.counter = FakeTokenCounter()
        self.sources = {}
        self.install_requests = {}
        callers = {item.app: object() for item in selected}
        delegations = Delegations(clock, {item.app: item.app.encode() for item in selected})
        for item in selected:
            service = Service(f"service-{item.app}", f"https://{item.app}.invalid", item.app)
            install = {
                "schema_version": SCHEMA,
                "operation": "install",
                "application_id": item.app,
                "installation_id": f"install-{item.app}",
                "origin": service.origin,
                "service_identity": service.identity,
                "projection_schema_id": item.schema.projection_schema_id,
                "max_sensitivity": item.schema.sensitivity,
                "max_ttl_seconds": 300,
            }
            self.install_requests[item.app] = install
            assert (
                decode(self.installations.mutate(encode(install), self.operator))["source_id"]
                == item.source
            )
            self.sources[item.source] = FixtureSource(
                self.installations,
                delegations,
                service,
                clock,
                self.controls.authorize_delegation,
            )
            self.add_binding(item.app)
        self.source_client = SourceClient(
            self.installations,
            self.controls,
            delegations,
            self.sources,
            clock,
            callers,
        )
        self.permissions = SourcePermissions(self.controls, self.source_client)
        application_catalog = ApplicationContributionCatalog(
            (
                item.app,
                lambda item=item: make_application(
                    item,
                    None if item.app in without_workspace_authorizer else self.controls,
                ),
            )
            for item in selected
        )
        runtime_catalog = ContextRuntimeContributionCatalog(
            (
                (
                    "shared-sources",
                    lambda _: ContextRuntimeContribution(
                        provider_factories={
                            item.source: SharedSourceProvider(
                                item,
                                self.source_client,
                                self.counter,
                                self.permissions,
                                callers[item.app],
                            )
                            for item in selected
                        },
                        planning_rules=tuple(
                            ContextPlanningRule(
                                rule_id=f"{item.source}:v1",
                                category="app-record",
                                phrases=("app records",),
                                provider_id=item.source,
                                operation="search",
                                fields=item.fields,
                                max_results=1,
                                max_bytes=PROJECTION_BYTES,
                                max_tokens=PROJECTION_TOKENS,
                                timeout_seconds=SOURCE_SECONDS,
                                application_ids=(item.app,),
                                required=True,
                                explanation="Use the explicitly shared application record.",
                            )
                            for item in selected
                        ),
                        permission_revalidators=(self.permissions,),
                    ),
                ),
            )
        )
        self.app = create_app(
            application_catalog=application_catalog,
            context_runtime_catalog=runtime_catalog,
            selected_contributions=tuple(self.selected),
        )
        self.controls.registry = self.app.state.application_registry
        self.app.state.principal_directory = self.directory
        self.app.state.isolate_external_conversations = True
        self.app.state.external_conversation_access = self.controls.allows_request
        self.app.user_middleware.append(Middleware(SharedSlots))
        # Keep the installed v1 operations and protected legacy route guards.
        # Interactive discovery is unnecessary in the isolated composition.
        discovery = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
        self.app.router.routes[:] = [
            route
            for route in self.app.router.routes
            if getattr(route, "path", None) not in discovery
        ]
        paths = self.app.openapi()["paths"]
        assert all(
            method in paths[path] for path, methods in OPERATIONS.items() for method in methods
        )
        self.conversations = InMemoryConversationRepository()
        self.messages = InMemoryMessageRepository(self.conversations)
        self.traces = InMemoryContextTraceRepository()
        ports = {
            get_settings: self.settings,
            deps.get_conversation_repository: self.conversations,
            deps.get_message_repository: self.messages,
            deps.get_context_trace_repository: self.traces,
            deps.get_global_profile_repository: InMemoryGlobalProfileRepository(),
            deps.get_summary_repository: InMemorySummaryRepository(),
            deps.get_provider_usage_accounting: None,
            deps.get_memory_adapter: None,
        }

        def port(value):
            return lambda: value

        self.app.dependency_overrides.update({key: port(value) for key, value in ports.items()})

    def configure_inference(self, generation):
        self.app.dependency_overrides[deps.get_inference_execution] = lambda: ExecutionPair(
            generation,
            self.counter,
        )

    def add_binding(self, app, *, audience=None, party=None, **updates):
        audience = audience or f"{app}-client"
        binding = {
            "audience": audience,
            "authorized_party": party or audience,
            "application_id": app,
            "enabled": True,
            "expires_at": int(self.now.timestamp()) + 1800,
        } | updates
        self.bindings.append(binding)
        self.write_policy()
        return binding

    def write_policy(self):
        temporary = self.policy_file.with_suffix(".next")
        temporary.write_text(
            json.dumps(
                {
                    "schema_version": "application-client-policy-v1",
                    "bindings": self.bindings,
                }
            )
        )
        temporary.replace(self.policy_file)

    def identify(self, token):
        return principal_from_google_token(token, self.settings)

    def seed(self, principal, config, workspace, data, *, revision="v1"):
        self.controls.enroll(principal, config.app, workspace)
        partition = namespace(
            config.source, config.app, workspace, principal.owner_id, config.schema.kind
        )
        source = self.sources[config.source]
        source.memberships.add((principal.subject, source_actor(principal), partition))
        source.seed(
            partition,
            Record(
                "r01",
                revision,
                self.now - timedelta(seconds=1),
                self.now,
                self.now + timedelta(seconds=200),
                config.schema.sensitivity,
                tuple(data.items()),
            ),
            watermark=f"w-{revision}",
        )
        return partition

    def control(self, token, config, workspace, client_token, **kwargs):
        principal = self.identify(token)
        self.directory.ensure_active(principal, correlation_id="owner-control")
        client_namespace = client_binding_namespace(self.identify(client_token), config.app)
        return self.controls.owner_control(
            principal, config.app, workspace, client_namespace, **kwargs
        )

    def grant(self, token, config, workspace, client_token):
        revision = self.control(
            token, config, workspace, client_token, operation="link", expected_revision=0
        )
        for recipient, fields in (
            (RUNTIME, tuple(dict.fromkeys(("title", *config.fields)))),
            (RECIPIENT, config.fields),
        ):
            revision = self.control(
                token,
                config,
                workspace,
                client_token,
                operation="grant",
                expected_revision=revision,
                recipient=recipient,
                fields=fields,
                expires_at=self.now + timedelta(minutes=2),
            )
        return revision
