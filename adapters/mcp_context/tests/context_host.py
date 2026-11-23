"""Test-only host for the frozen PAS source fixture and a signed synthetic issuer."""

import asyncio
import json
import threading
from contextvars import copy_context
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from app_context_support.client import Intent, TurnBudget
from app_context_support.context import context_item
from app_context_support.fixtures import FITNESS, TRAVEL, Composition
from app_context_support.source import expiry
from app_context_support.wire import Page, ProtocolError
from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import ApplicationScope
from personal_ai.context.authorization import (
    apply_item_policy,
    authorize_context_selection,
)
from personal_ai.context.providers import ContextSelection
from personal_ai_mcp_context.contracts import (
    MAX_HITS,
    PURPOSE,
    READ_SCOPE,
    RECIPIENT,
    AuthorizedRead,
    BrowserPrincipal,
    FetchedRecord,
    Identity,
    SearchHit,
    SearchPage,
    SourceBinding,
    VerifiedAccess,
)
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

ISSUER = "https://fixture-idp.invalid"
RESOURCE = "https://context.example.invalid/mcp"
CITATION_RESOURCE = "https://context.example.invalid/mcp-citations/v1"
TRAVEL_CLIENT = "chatgpt-travel"
FITNESS_CLIENT = "chatgpt-fitness"
ALT_CLIENT = "chatgpt-alternate"
CLIENTS = frozenset({TRAVEL_CLIENT, FITNESS_CLIENT, ALT_CLIENT})
FIXTURE_SIGNING_KEY = b"fixture-only-outbound-mcp-signing-key"
_SOURCE_WORKER_SLOTS = threading.BoundedSemaphore(8)


@dataclass(frozen=True)
class Connection:
    id: str
    generation: int
    tenant: str
    application: str
    workspace: str | None
    source_id: str
    grant_id: str


class _SingleReadBudget(TurnBudget):
    def start(self, operation, raw):
        if self.calls:
            raise ProtocolError("limit_exceeded")
        super().start(operation, raw)
        self.charge_tokens(raw)

    def charge_hits(self, count):
        self.results += count
        if self.results > self.max_results:
            raise ProtocolError("limit_exceeded")


class SyntheticHost:
    def __init__(self):
        self.pas = Composition()
        self.accounts = {
            (ISSUER, principal.subject): principal
            for owner, principal in self.pas.principals.items() if owner in {"a", "b"}
        }
        self.tenants = {(ISSUER, f"subject-{owner}"): f"tenant-{owner}" for owner in ("a", "b")}
        self.clients = set(CLIENTS)
        self.revocation_state = set()
        self.browser_sessions = {}
        self.connections = {}
        self.budgets = []
        self.before_release = None
        for owner in ("a", "b"):
            self.connect(owner, TRAVEL, TRAVEL_CLIENT)
            self.connect(owner, FITNESS, FITNESS_CLIENT)

    def connect(self, owner, app, client):
        principal, scope, intent = self.pas.subject(owner, app)
        binding = self.pas.authority.grants[intent.grant_id]
        grant = replace(
            binding, id=f"grant-mcp-{scope.workspace_id}", recipient=RECIPIENT,
            fields=binding.fields if scope.workspace_id == "trip-b" else ("title",),
            operations=("search", "fetch"),
        )
        self.pas.authority.grants[grant.id] = grant
        connection = Connection(
            f"connection-{client}-{scope.workspace_id}", 1, f"tenant-{owner}",
            app, scope.workspace_id, grant.source_id, grant.id,
        )
        self.connections[Identity(ISSUER, principal.subject, client)] = (connection,)

    def token(self, owner="a", client=TRAVEL_CLIENT, *, key=FIXTURE_SIGNING_KEY, **claims):
        return jwt.encode({
            "iss": ISSUER, "sub": f"subject-{owner}", "aud": RESOURCE, "client_id": client,
            "jti": uuid4().hex, "exp": int((self.pas.now + timedelta(minutes=10)).timestamp()),
            "nbf": int(self.pas.now.timestamp()), "scope": READ_SCOPE,
            "token_kind": "access_token", "human": True,
            **claims,
        }, key, algorithm="HS256", headers={"typ": "at+jwt"})

    async def verify_access(self, token):
        # Fixed key and algorithm. Time, issuer, resource, client and scope are
        # validated by the resource edge against its configured values.
        value = jwt.decode(
            token, FIXTURE_SIGNING_KEY, algorithms=["HS256"],
            options={"verify_aud": False, "verify_exp": False, "verify_nbf": False,
                     "require": ["iss", "sub", "aud", "exp", "jti"]},
        )
        return VerifiedAccess(
            Identity(value["iss"], value["sub"], value["client_id"]), value["aud"],
            value["token_kind"], frozenset(value["scope"].split()),
            datetime.fromtimestamp(value["exp"], UTC),
            datetime.fromtimestamp(value["nbf"], UTC) if "nbf" in value else None,
            self.revocation_state is not None and value["jti"] not in self.revocation_state
            and value["client_id"] in self.clients, value["human"],
        )

    def _resolve(self, identity, operation):
        account = (identity.issuer, identity.subject)
        principal = self.accounts.get(account)
        connections = self.connections.get(identity, ())
        if not isinstance(principal, AuthenticatedPrincipal) or len(connections) != 1:
            raise ProtocolError("unavailable")
        connection = connections[0]
        if connection.tenant != self.tenants.get(account):
            raise ProtocolError("unavailable")
        scope = self.pas.authority.scope(principal, connection.application, connection.workspace, "mcp-fixture")
        install = self.pas.installations.active(connection.source_id)
        grant = self.pas.authority.grants.get(connection.grant_id)
        if grant is None:
            raise ProtocolError("unavailable")
        intent = Intent(
            connection.source_id, connection.grant_id, RECIPIENT, PURPOSE,
            ("title",) if operation == "search" else grant.fields,
        )
        grant = self.pas.authority.authorize(principal, scope, intent, operation, install)
        self.pas.authority.field_sensitivity(install, grant, grant.fields)
        registration = self.pas.authority.registry.registration(scope.application_id)
        if not any(
            capability.capability_id == install.source_id and capability.is_enabled({})
            for capability in registration.context_providers
        ):
            raise ProtocolError("unavailable")
        context = ApplicationContextRequest(
            definition=registration.definition, scope=scope,
            context_provider_capabilities=registration.context_providers,
        )
        selection = ContextSelection(provider_id=install.source_id, operation="search", fields=grant.fields)
        authorize_context_selection(context, selection)
        binding = SourceBinding(
            connection.tenant, ApplicationScope(application_id=scope.application_id, workspace_id=scope.workspace_id),
            scope.owner_id, scope.acting_user_id, connection.id, connection.generation,
            install.source_id, install.revision, install.epoch, grant.id, grant.version, grant.epoch,
            self.pas.authority.policy_fingerprint(grant.app), grant.recipient, grant.purpose,
            grant.fields, min(install.expires_at, grant.expires_at),
            installation_id=install.binding.installation_id,
        )
        return binding, principal, context, selection, intent, install

    async def resolve(self, identity, operation):
        return self._resolve(identity, operation)[0]

    def budget(self, deadline):
        budget = _SingleReadBudget(deadline, self.pas.counter)
        self.budgets.append(budget)
        return budget

    def browser_session(self, identity, **changes):
        binding = self._resolve(identity, "fetch")[0]
        session = uuid4().hex
        principal = BrowserPrincipal(
            identity.issuer, identity.subject, binding.tenant, binding.owner_id, binding.acting_user_id,
        )
        self.browser_sessions[session] = replace(principal, **changes)
        return session

    async def verify_browser(self, request):
        return self.browser_sessions.get(request.cookies.get("fixture-session"))

    async def read(self, identity, binding, selection, budget):
        operation = "search" if isinstance(selection, str) else "fetch"
        current, principal, context, policy_selection, intent, install = self._resolve(identity, operation)
        if current != binding:
            raise ProtocolError("unavailable")
        scope = context.scope
        caller = self.pas.app_clients[scope.application_id]
        parameters = (
            {"query": selection, "limit": MAX_HITS, "record_kind": install.schema.kind}
            if operation == "search" else {
                "record_ref": selection.record_ref, "source_revision": selection.revision,
            }
        )
        if not _SOURCE_WORKER_SLOTS.acquire(blocking=False):
            raise ProtocolError("unavailable")

        def source_read():
            try:
                return self.pas.client.read(
                    operation, principal, scope, intent, budget, caller=caller, **parameters,
                )
            finally:
                # A timed-out caller cannot stop arbitrary synchronous fixture
                # code. Keep the slot until that physical operation completes.
                _SOURCE_WORKER_SLOTS.release()

        try:
            worker = asyncio.get_running_loop().run_in_executor(None, copy_context().run, source_read)
        except RuntimeError:
            _SOURCE_WORKER_SLOTS.release()
            raise
        # Keep the admitted job alive until it runs its physical release, even
        # if the caller is cancelled before the executor starts the function.
        worker.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)
        read = await asyncio.shield(worker)
        value = read.value

        if isinstance(value, Page):
            budget.charge_hits(len(value.items))
            source = self.pas.sources[binding.source_id]
            hits = []
            for hit in value.items:
                watermark, record = source.status(install, read.request, read.claims, hit.record_ref)
                if watermark != value.watermark or record.revision != hit.source_revision:
                    raise ProtocolError("stale_dependency")
                fresh_until = expiry(record, install, read.grant.expires_at)
                hits.append(SearchHit(hit.record_ref, hit.source_revision, hit.title, fresh_until))
            projected = SearchPage(value.watermark, tuple(hits))
        else:
            item = apply_item_policy(context, policy_selection, context_item(read))
            payload = item.disclosed_payload.model_dump(mode="json")
            projected = FetchedRecord(
                value.record_ref, item.permission_dependencies[0].source_revision, value.watermark,
                item.source_id, payload["title"], json.dumps(payload, ensure_ascii=False),
                item.observed_at, item.expires_at,
            )

        def revalidate():
            if self._resolve(identity, operation)[0] != binding:
                raise ProtocolError("unavailable")
            self.pas.client.revalidate(read, principal, scope, caller)

        if self.before_release is not None:
            await self.before_release()
        budget.check()
        return AuthorizedRead(projected, revalidate)

    def app(self, **kwargs):
        from personal_ai_mcp_context.server import context_mcp_app

        return context_mcp_app(**({
            "issuer": ISSUER, "resource": RESOURCE, "approved_clients": CLIENTS,
            "verify_access": self.verify_access, "reader": self, "enabled": True,
            "environment": "test", "clock": lambda: self.pas.now,
        } | kwargs))

    def citation_app(self, **kwargs):
        return self.app(**({"resource": CITATION_RESOURCE, "verify_browser": self.verify_browser} | kwargs))

    def issuer_app(self):
        async def metadata(_request):
            return JSONResponse({
                "issuer": ISSUER, "authorization_endpoint": f"{ISSUER}/authorize",
                "token_endpoint": f"{ISSUER}/token", "revocation_endpoint": f"{ISSUER}/revoke",
                "response_types_supported": ["code"], "code_challenge_methods_supported": ["S256"],
                "scopes_supported": [READ_SCOPE],
            })

        return Starlette(routes=[Route("/.well-known/oauth-authorization-server", metadata)])
