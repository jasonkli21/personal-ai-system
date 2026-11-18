"""PAS-side authority and bounded read orchestration for synthetic sources."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from time import monotonic

from personal_ai.applications.contracts import SENSITIVITY_RANK
from personal_ai.auth.scope import RequestScope
from personal_ai.llm.client import ChatMessage

from .source import (
    Installation,
    SourceReadPolicy,
    describe,
    describe_operations,
    expiry,
    is_fresh,
    namespace,
    record_id,
    source_version,
    validate_projection,
)
from .wire import (
    REQUESTS,
    SCHEMA,
    Claims,
    Describe,
    Description,
    ErrorEnvelope,
    Fetch,
    Page,
    Projection,
    ProtocolError,
    Search,
    checked,
    decode,
    digest,
    encode,
    screen,
)


@dataclass(frozen=True)
class Grant:
    id: str
    issuer: str
    subject: str
    owner: str
    actor: str | None
    app: str
    workspace: str
    source_id: str
    installation_epoch: int
    recipient: str
    purpose: str
    kind: str
    fields: tuple[str, ...]
    operations: tuple[str, ...]
    ceiling: str
    expires_at: datetime
    version: int = 1
    epoch: int = 1

    def fields_for(self, operation):
        return ("title",) if operation == "search" else self.fields

    @property
    def dependency_version(self):
        return f"r{self.version}:e{self.epoch}"


@dataclass(frozen=True)
class Intent:
    source_id: str
    grant_id: str
    recipient: str
    purpose: str
    fields: tuple[str, ...]


class Authority:
    """Separate verified human resolution, PAS memberships and live source grants."""

    def __init__(self, clock, registry):
        self.clock = clock
        self.registry = registry
        self.memberships = {}
        self.grants = {}
        self.counts = Counter()

    @staticmethod
    def require_principal(principal):
        if principal is None or not principal.authenticated or principal.owner_id == "local":
            raise ProtocolError("unauthenticated")

    def scope(self, principal, app, workspace, request_id):
        self.counts["check_pas_membership"] += 1
        self.require_principal(principal)
        # A verified issuer/subject is the lookup key. Email is irrelevant.
        membership = self.memberships.get((principal.issuer, principal.subject, app, workspace))
        if membership is None or membership[0] != principal.owner_id:
            raise ProtocolError("unavailable")
        owner, actor = membership
        return RequestScope(
            owner_id=owner, acting_user_id=actor, application_id=app,
            workspace_id=workspace, request_id=request_id,
        )

    def authorize(self, principal, scope, intent, operation, install):
        current = self.scope(principal, scope.application_id, scope.workspace_id, scope.request_id)
        if current != scope:
            raise ProtocolError("unavailable")
        grant = self._current_grant(intent.grant_id, install, operation)
        if (
            (principal.issuer, principal.subject, scope.owner_id, scope.acting_user_id,
             scope.application_id, scope.workspace_id, intent.source_id, intent.purpose,
             intent.recipient)
            != (grant.issuer, grant.subject, grant.owner, grant.actor, grant.app,
                grant.workspace, grant.source_id, grant.purpose, grant.recipient)
            or not intent.fields or len(set(intent.fields)) != len(intent.fields)
            or not set(intent.fields) <= set(grant.fields)
            or (operation == "search" and intent.fields != ("title",))
        ):
            raise ProtocolError("unavailable")
        return grant

    def _current_grant(self, grant_id, install, operation):
        self.counts["check_grant"] += 1
        current = self.grants.get(grant_id)
        if (
            current is None or current.expires_at <= self.clock()
            or current.installation_epoch != install.epoch
            or (current.source_id, current.app, current.kind)
            != (install.source_id, install.binding.application_id, install.schema.kind)
            or operation not in current.operations
            or not set(current.fields) <= install.schema.field_types.keys()
            or (operation == "search" and "title" not in current.fields)
            or current.ceiling not in SENSITIVITY_RANK or current.ceiling == "unknown"
        ):
            raise ProtocolError("unavailable")
        return current

    def authorize_delegation(self, claims, install):
        grant = self._current_grant(claims.grant_id, install, claims.operation)
        membership = self.memberships.get((grant.issuer, grant.subject, grant.app, grant.workspace))
        if (
            membership != (grant.owner, grant.actor)
            or (claims.sub, claims.owner_id, claims.acting_user_id, claims.application_id,
                claims.workspace_id, claims.source_id, claims.installation_epoch, claims.purpose,
                claims.recipient, claims.grant_epoch, tuple(claims.kind_allowlist))
            != (grant.subject, grant.owner, grant.actor, grant.app, grant.workspace, grant.source_id,
                grant.installation_epoch, grant.purpose, grant.recipient, grant.epoch, (grant.kind,))
            or not set(claims.field_allowlist) <= set(grant.fields_for(claims.operation))
        ):
            raise ProtocolError("unavailable")
        self.field_sensitivity(install, grant, claims.field_allowlist)
        return SourceReadPolicy(
            grant.operations, grant.fields, grant.ceiling, grant.version,
            self.policy_fingerprint(grant.app),
            grant.expires_at,
        )

    def field_sensitivity(self, install, grant, fields):
        policy = self.registry.get(grant.app).context_policy
        operation = policy.operation(install.source_id, "search")
        if operation is None or not operation.source_access or not operation.model_disclosure:
            raise ProtocolError("unavailable")
        field_policies = {field.field: field for field in operation.fields}
        if any(field not in field_policies or not field_policies[field].source_access
               or not field_policies[field].model_disclosure for field in fields):
            raise ProtocolError("unavailable")
        labels = tuple(
            (field, max((install.schema.sensitivity, operation.sensitivity,
                         field_policies[field].sensitivity), key=SENSITIVITY_RANK.__getitem__))
            for field in fields
        )
        ceiling = min(
            SENSITIVITY_RANK[limit] for limit in
            (install.binding.max_sensitivity, grant.ceiling, policy.maximum_model_sensitivity)
        )
        if any(SENSITIVITY_RANK[label] > ceiling for _, label in labels):
            raise ProtocolError("unavailable")
        return labels

    def policy_fingerprint(self, app):
        return digest(self.registry.get(app).context_policy)


class TurnBudget:
    """One page and ten exact fetches within the coordinator's absolute deadline."""

    def __init__(self, deadline, counter, *, max_bytes=16_384, max_tokens=16_384, max_results=10):
        self.deadline = deadline
        self.counter = counter
        self.max_bytes = max_bytes
        self.max_tokens = max_tokens
        self.max_results = max_results
        self.calls = Counter()
        self.bytes = 0
        self.tokens = 0
        self.results = 0

    def check(self):
        if monotonic() >= self.deadline:
            raise TimeoutError("synthetic source deadline exceeded")

    def start(self, operation, raw):
        self.check()
        if self.calls[operation] >= {"describe": 1, "search": 1, "fetch": 10}[operation]:
            raise ProtocolError("limit_exceeded")
        self.calls[operation] += 1
        self.charge_bytes(raw)

    def charge_bytes(self, raw):
        self.bytes += len(raw)
        screen(raw)
        self.check()
        if self.bytes > self.max_bytes:
            raise ProtocolError("limit_exceeded")

    def charge_tokens(self, raw):
        self.tokens += self.counter.count(
            (ChatMessage(role="user", content=raw.decode()),)
        ).tokens
        self.check()
        if self.tokens > self.max_tokens:
            raise ProtocolError("limit_exceeded")


@dataclass(frozen=True)
class ReadResult:
    value: Description | Page | Projection
    raw: bytes
    grant: Grant
    install: Installation
    claims: Claims
    request: Describe | Search | Fetch
    intent: Intent
    policy: str
    expires_at: datetime | None = None
    field_sensitivity: tuple[tuple[str, str], ...] = ()

    @property
    def sensitivity(self):
        return max((label for _, label in self.field_sensitivity), key=SENSITIVITY_RANK.__getitem__)


class SourceClient:
    def __init__(self, installations, authority, delegations, sources, clock, app_clients):
        self.installations = installations
        self.authority = authority
        self.delegations = delegations
        self.sources = sources
        self.clock = clock
        self.app_clients = app_clients
        self.services = {source_id: source.service for source_id, source in sources.items()}

    def _admit(self, request, principal, scope, intent, caller):
        # Membership precedes registry lookup; the verified scope owns the selectors.
        current = self.authority.scope(
            principal, scope.application_id, scope.workspace_id, scope.request_id
        )
        if current != scope or (request.application_id, request.workspace_id, request.source_id) != (
            scope.application_id, scope.workspace_id, intent.source_id
        ):
            raise ProtocolError("unavailable")
        if caller is None or self.app_clients.get(request.application_id) is not caller:
            raise ProtocolError("unavailable")
        install = self.installations.active(request.source_id)
        source = self.sources.get(install.source_id)
        if (
            source is None or source.service != self.services.get(request.source_id)
            or (source.service.identity, source.service.origin)
            != (install.binding.service_identity, install.binding.origin)
        ):
            raise ProtocolError("unavailable")
        grant = self.authority.authorize(principal, scope, intent, request.operation, install)
        self.authority.field_sensitivity(install, grant, intent.fields)
        return source, install, grant, self.authority.policy_fingerprint(grant.app)

    def read(self, operation, principal, scope, intent, budget, *, caller, **parameters):
        data = {
            "schema_version": SCHEMA, "operation": operation, "source_id": intent.source_id,
            "application_id": scope.application_id, "workspace_id": scope.workspace_id,
            **parameters,
        }
        raw = encode(data)
        screen(raw)
        budget.check()
        self.authority.require_principal(principal)
        request = checked(REQUESTS[operation], data)
        source, install, grant, policy = self._admit(request, principal, scope, intent, caller)
        if isinstance(request, Fetch):
            self._identity(request, grant, request.record_ref, request.source_revision)
        base = self.delegations.issue(raw, grant, scope, source.service, operation, intent.fields)
        claims = self.delegations.authenticate(base, source.service)
        budget.start(operation, raw)
        response = source.exchange(raw, base)
        budget.charge_bytes(response)
        # Recompute admissibility before inspecting source claims or exposing staleness.
        if self._admit(request, principal, scope, intent, caller) != (source, install, grant, policy):
            raise ProtocolError("stale_dependency")
        data = decode(response)
        budget.charge_tokens(response)
        if "error" in data:
            raise ProtocolError(checked(ErrorEnvelope, data).error.code)
        value, expires_at, labels = self._validate(
            data, source, install, grant, request, claims, intent.fields
        )
        if isinstance(value, Projection):
            budget.results += 1
            if budget.results > budget.max_results:
                raise ProtocolError("limit_exceeded")
        return ReadResult(value, response, grant, install, claims, request, intent,
                          policy, expires_at, labels)

    def _validate(self, data, source, install, grant, request, claims, fields):
        if isinstance(request, Describe):
            source.status(install, request, claims)
            description = checked(Description, data)
            operations = describe_operations(grant.operations, grant.fields)
            if description.model_dump(mode="json") != describe(install, fields, operations):
                raise ProtocolError("unavailable")
            return description, None, ()

        value = checked(Page if isinstance(request, Search) else Projection, data)
        if (value.source_id, value.application_id, value.workspace_id, value.record_kind) != (
            request.source_id, request.application_id, request.workspace_id, grant.kind
        ):
            raise ProtocolError("unavailable")
        if isinstance(value, Projection) and (
            value.record_ref, value.source_revision
        ) != (request.record_ref, request.source_revision):
            raise ProtocolError("unavailable")
        ref = request.record_ref if isinstance(request, Fetch) else None
        watermark, entry = source.status(install, request, claims, ref)
        if value.watermark != watermark:
            raise ProtocolError("stale_dependency")
        if isinstance(value, Page):
            if (
                len(value.items) > request.limit
                or len({hit.record_ref for hit in value.items}) != len(value.items)
                or (value.next_cursor is not None and len(value.items) != request.limit)
                or value.items != sorted(
                    sorted(value.items, key=lambda hit: hit.record_ref),
                    key=lambda hit: hit.effective_at, reverse=True,
                )
            ):
                raise ProtocolError("invalid_request")
            for hit in value.items:
                self._identity(request, grant, hit.record_ref, hit.source_revision)
                current_watermark, entry = source.status(install, request, claims, hit.record_ref)
                if current_watermark != watermark:
                    raise ProtocolError("stale_dependency")
                validate_projection(install.schema, fields, {"title": hit.title})
                if (
                    hit.record_kind != grant.kind or request.query not in hit.title
                    or entry.revision != hit.source_revision or entry.effective_at != hit.effective_at
                    or not entry.matches_fields({"title": hit.title})
                    or not is_fresh(entry, install, grant.expires_at, self.clock())
                ):
                    raise ProtocolError("unavailable")
            return value, None, ()

        validate_projection(install.schema, fields, value.content_projection)
        if (
            not is_fresh(value, install, grant.expires_at, self.clock())
            or (entry.revision, entry.observed_at, entry.effective_at, entry.expires_at, entry.sensitivity)
            != (value.source_revision, value.observed_at, value.effective_at, value.expires_at, value.sensitivity)
            or not entry.matches_fields(value.content_projection)
        ):
            raise ProtocolError("unavailable")
        return (
            value, expiry(value, install, grant.expires_at),
            self.authority.field_sensitivity(install, grant, fields),
        )

    @staticmethod
    def _identity(request, grant, ref, revision):
        record_id(
            namespace(request.source_id, request.application_id, request.workspace_id,
                      grant.owner, grant.kind), ref, revision
        )
        source_version(revision)

    def revalidate(self, result, principal, scope, caller):
        source, install, grant, policy = self._admit(
            result.request, principal, scope, result.intent, caller
        )
        if (install, grant, policy) != (result.install, result.grant, result.policy):
            raise ProtocolError("stale_dependency")
        value, expires_at, labels = self._validate(
            decode(result.raw), source, install, grant, result.request, result.claims,
            result.intent.fields,
        )
        if (value, expires_at, labels) != (result.value, result.expires_at, result.field_sensitivity):
            raise ProtocolError("stale_dependency")
