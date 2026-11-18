"""In-memory installation control plane and independently authorized source."""

import hashlib
import hmac
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from itertools import count
from threading import Lock, RLock
from uuid import uuid4

from personal_ai.applications.contracts import SENSITIVITY_RANK

from .wire import (
    MAX_MESSAGE,
    MAX_STRING,
    REQUESTS,
    SCHEMA,
    Binding,
    Claims,
    Describe,
    Disable,
    Fetch,
    Install,
    ProtocolError,
    Search,
    Update,
    checked,
    decode,
    digest,
    encode,
    screen,
    utf8_bound,
)


@dataclass(frozen=True)
class SourceSchema:
    kind: str
    projection_schema_id: str
    fields: tuple[tuple[str, type], ...]
    sensitivity: str

    @property
    def field_types(self):
        return dict(self.fields)


SCHEMAS = {
    "travel-demo": SourceSchema(
        "itinerary_leg", "travel-projection-v1", (("title", str), ("platform", str)), "personal"
    ),
    "fitness-demo": SourceSchema(
        "workout", "fitness-projection-v1", (("title", str), ("duration_minutes", int)), "sensitive"
    ),
}


@dataclass(frozen=True)
class Installation:
    binding: Binding
    source_id: str
    epoch: int
    expires_at: datetime
    enabled: bool = True

    @property
    def revision(self):
        return f"i{self.epoch}"

    @property
    def schema(self):
        return SCHEMAS[self.binding.application_id]

    def envelope(self):
        return {
            "source_id": self.source_id, "installation_epoch": self.epoch,
            "installation_revision": self.revision,
        }


class Installations:
    def __init__(self, operator, clock, source_ids):
        self._operator = operator
        self._clock = clock
        self._source_ids = iter(source_ids)
        self._by_id = {}
        self._sources = {}
        self._lock = Lock()
        self.counts = Counter()

    def mutate(self, raw, principal):
        screen(raw)
        if principal is not self._operator:
            raise ProtocolError("unauthenticated")
        data = decode(raw)
        model = {"install": Install, "update": Update, "disable": Disable}.get(
            str(data.get("operation"))
        )
        if model is None:
            raise ProtocolError("invalid_request")
        request = checked(model, data)
        binding = None
        if isinstance(request, (Install, Update)):
            binding = checked(Binding, request.model_dump(exclude={"operation", "expected_revision"}))
            schema = SCHEMAS.get(binding.application_id)
            if schema is None or schema.projection_schema_id != binding.projection_schema_id:
                raise ProtocolError("invalid_request")
        with self._lock:
            current = self._by_id.get(request.installation_id)
            if isinstance(request, Install):
                if current is not None:
                    raise ProtocolError("invalid_request")
                source_id = next(self._source_ids, None)
                if source_id is None or source_id in self._sources:
                    raise ProtocolError("source_unavailable")
                current = Installation(binding, source_id, 1, self._clock() + timedelta(hours=1))
            else:
                if current is None:
                    raise ProtocolError("unavailable")
                if request.expected_revision != current.revision:
                    raise ProtocolError("stale_dependency")
                if binding is not None and binding.application_id != current.binding.application_id:
                    raise ProtocolError("invalid_request")
                current = replace(
                    current, binding=binding or current.binding, epoch=current.epoch + 1,
                    enabled=isinstance(request, Update),
                )
            self._by_id[request.installation_id] = current
            self._sources[current.source_id] = current
            self.counts[request.operation] += 1
            return encode(current.envelope())

    def active(self, source_id):
        with self._lock:
            self.counts["read_registry"] += 1
            install = self._sources.get(source_id)
            if install is None or not install.enabled or self._clock() >= install.expires_at:
                raise ProtocolError("unavailable")
            return install


@dataclass(frozen=True)
class Service:
    identity: str
    origin: str
    key_id: str


@dataclass(frozen=True)
class Delegation:
    body: bytes
    signature: bytes


class Delegations:
    """Injected test signer/verifier. The source consumes nonces under a lock."""

    def __init__(self, clock, keys):
        self.clock = clock
        self.keys = dict(keys)
        self._next_nonce = count(1)
        self._used = {}
        self._lock = Lock()

    def seal(self, claims, *, key_id):
        body = encode(claims)
        return Delegation(body, hmac.digest(self.keys[key_id], body, "sha256"))

    def issue(self, raw, grant, scope, service, operation, fields):
        now = int(self.clock().timestamp())
        claims = Claims(
            iss="fixture-pas", aud=service.identity, sub=grant.subject,
            owner_id=scope.owner_id, acting_user_id=scope.acting_user_id,
            application_id=scope.application_id, workspace_id=scope.workspace_id,
            source_id=grant.source_id, installation_epoch=grant.installation_epoch,
            kind_allowlist=[grant.kind], field_allowlist=list(fields),
            purpose=grant.purpose, recipient=grant.recipient, operation=operation,
            request_digest=digest(decode(raw)), nonce=f"nonce-{next(self._next_nonce)}",
            grant_id=grant.id, grant_epoch=grant.epoch, iat=now,
            exp=min(now + 15, int(grant.expires_at.timestamp())), kid=service.key_id,
        )
        return self.seal(claims, key_id=service.key_id)

    def authenticate(self, delegation, service):
        try:
            if delegation is None or len(delegation.body) > MAX_MESSAGE:
                raise ProtocolError("unauthenticated")
            expected = hmac.digest(self.keys[service.key_id], delegation.body, "sha256")
            if not hmac.compare_digest(expected, delegation.signature):
                raise ProtocolError("unauthenticated")
            claims = checked(Claims, decode(delegation.body))
            now = self.clock().timestamp()
            if (
                claims.iss != "fixture-pas" or claims.aud != service.identity
                or claims.kid != service.key_id or not claims.iat <= now < claims.exp
                or not 0 < claims.exp - claims.iat <= 15
                or len(set(claims.field_allowlist)) != len(claims.field_allowlist)
                or len(set(claims.kind_allowlist)) != len(claims.kind_allowlist)
            ):
                raise ProtocolError("unauthenticated")
            return claims
        except (KeyError, ProtocolError) as error:
            raise ProtocolError("unauthenticated") from error

    def consume(self, claims):
        with self._lock:
            now = self.clock().timestamp()
            self._used = {key: exp for key, exp in self._used.items() if exp > now}
            key = claims.kid, claims.nonce
            if key in self._used or now >= claims.exp:
                raise ProtocolError("unauthenticated")
            if len(self._used) >= 1024:
                raise ProtocolError("rate_limited")
            self._used[key] = claims.exp


def namespace(source, app, workspace, owner, kind):
    return source, app, workspace, owner, kind


def record_id(partition, ref, revision):
    value = encode([*partition, ref, revision]).decode()
    if len(value) > 200:
        raise ProtocolError("invalid_request")
    return value


def source_version(revision):
    value = encode([SCHEMA, revision]).decode()
    if len(value) > 100:
        raise ProtocolError("invalid_request")
    return value


@dataclass(frozen=True)
class Record:
    ref: str
    revision: str
    effective_at: datetime
    observed_at: datetime
    expires_at: datetime
    sensitivity: str
    values: tuple[tuple[str, str | int], ...]

    def version(self):
        return RecordVersion(
            self.revision, self.observed_at, self.effective_at, self.expires_at,
            self.sensitivity, tuple((key, digest(value)) for key, value in self.values),
        )


@dataclass(frozen=True)
class RecordVersion:
    revision: str
    observed_at: datetime
    effective_at: datetime
    expires_at: datetime
    sensitivity: str
    field_digests: tuple[tuple[str, str], ...]

    def matches_fields(self, values):
        expected = dict(self.field_digests)
        return all(expected.get(field) == digest(value) for field, value in values.items())


@dataclass(frozen=True)
class SourceReadPolicy:
    operations: tuple[str, ...]
    fields: tuple[str, ...]
    ceiling: str
    grant_version: int
    app_policy: str
    expires_at: datetime


@dataclass(frozen=True)
class Cursor:
    binding: tuple
    grant_epoch: int
    grant_version: int
    app_policy: str
    watermark: str
    offset: int
    expires_at: float


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


class FixtureSource:
    """Owns record partitions and membership independently from PAS grants."""

    def __init__(self, installations, delegations, service, clock, authorize):
        self.installations = installations
        self.delegations = delegations
        self.service = service
        self.authorize = authorize
        self.clock = clock
        self.memberships = set()
        self._hidden = set()
        self.counts = Counter()
        self.lookup_paths = []
        self._records = {}
        self._versions = {}
        self._watermarks = {}
        self._cursors = {}
        self._lock = RLock()

    def seed(self, partition, record, *, watermark):
        record_id(partition, record.ref, record.revision)
        source_version(record.revision)
        with self._lock:
            rows = self._records.setdefault(partition, {})
            if record.ref not in rows and len(rows) >= 32:
                raise ProtocolError("limit_exceeded")
            if record.ref in rows and (
                record.revision == rows[record.ref].revision
                or watermark == self._watermarks[partition]
            ):
                raise ProtocolError("invalid_request")
            rows[record.ref] = record
            self._versions[partition, record.ref] = record.version()
            self._watermarks[partition] = watermark

    def hide(self, partition, ref, *, watermark):
        with self._lock:
            self._hidden.add((partition, ref))
            self._watermarks[partition] = watermark

    def _namespace(self, install, request, claims):
        self.counts["check_source_membership"] += 1
        binding = install.binding
        kind = install.schema.kind
        if (
            (binding.service_identity, binding.origin) != (self.service.identity, self.service.origin)
            or claims.installation_epoch != install.epoch
            or (claims.source_id, claims.application_id, claims.workspace_id, claims.operation)
            != (request.source_id, request.application_id, request.workspace_id, request.operation)
            or kind not in claims.kind_allowlist
            or (isinstance(request, Search) and request.record_kind != kind)
            or not set(claims.field_allowlist) <= install.schema.field_types.keys()
            or (isinstance(request, Search) and "title" not in claims.field_allowlist)
        ):
            raise ProtocolError("unavailable")
        partition = namespace(
            request.source_id, request.application_id, request.workspace_id, claims.owner_id, kind
        )
        if (claims.sub, claims.acting_user_id, partition) not in self.memberships:
            raise ProtocolError("unavailable")
        return partition

    def status(self, install, request, claims, ref=None):
        """Inspect independent rights and revision metadata without reading a projection."""
        with self._lock:
            partition = self._namespace(install, request, claims)
            self.counts["check_source_revision"] += 1
            key = (partition, ref)
            if ref is not None and (key in self._hidden or key not in self._versions):
                raise ProtocolError("unavailable")
            return self._watermarks.get(partition, "w0"), self._versions.get(key)

    def exchange(self, raw, delegation):
        self.counts["exchange"] += 1
        try:
            screen(raw)
            claims = self.delegations.authenticate(delegation, self.service)
            data = decode(raw)
            if not hmac.compare_digest(claims.request_digest, digest(data)):
                raise ProtocolError("unauthenticated")
            model = REQUESTS.get(str(data.get("operation")))
            if model is None:
                raise ProtocolError("invalid_request")
            request = checked(model, data)
            install = self.installations.active(request.source_id)
            if install.binding.application_id != request.application_id:
                raise ProtocolError("unavailable")
            with self._lock:
                partition = self._namespace(install, request, claims)
                policy = self.authorize(claims, install)
                self.delegations.consume(claims)
                result = self._run(install, request, claims, partition, policy)
            response = encode(result)
            screen(response)
            return response
        except ProtocolError as error:
            return encode({
                "schema_version": SCHEMA,
                "error": {"code": error.code, "request_id": f"req-{uuid4().hex}"},
            })

    def _run(self, install, request, claims, partition, policy):
        if SENSITIVITY_RANK[install.schema.sensitivity] > min(
            SENSITIVITY_RANK[install.binding.max_sensitivity], SENSITIVITY_RANK[policy.ceiling]
        ):
            raise ProtocolError("unavailable")
        if isinstance(request, Describe):
            operations = describe_operations(policy.operations, policy.fields)
            return describe(install, claims.field_allowlist, operations)
        base = {
            "schema_version": SCHEMA, "source_id": request.source_id,
            "application_id": request.application_id, "workspace_id": request.workspace_id,
            "record_kind": install.schema.kind,
            "watermark": self._watermarks.get(partition, "w0"),
        }
        if isinstance(request, Search):
            return self._search(request, claims, partition, base, install, policy)
        assert isinstance(request, Fetch)
        record_id(partition, request.record_ref, request.source_revision)
        source_version(request.source_revision)
        _, binding = self.status(install, request, claims, request.record_ref)
        if not is_fresh(binding, install, policy.expires_at, self.clock()):
            raise ProtocolError("unavailable")
        if binding.revision != request.source_revision:
            raise ProtocolError("stale_dependency")
        self._lookup("fetch", partition)
        record = self._records[partition][request.record_ref]
        values = dict(record.values)
        projection = {field: values[field] for field in claims.field_allowlist if field in values}
        validate_projection(install.schema, claims.field_allowlist, projection)
        return base | {
            "record_ref": record.ref, "source_revision": record.revision,
            "observed_at": stamp(record.observed_at), "effective_at": stamp(record.effective_at),
            "expires_at": stamp(record.expires_at), "sensitivity": record.sensitivity,
            "content_projection": projection,
        }

    def _lookup(self, operation, partition):
        self.counts[f"{operation}_lookup"] += 1
        self.lookup_paths.append(partition)

    def _search(self, request, claims, partition, base, install, policy):
        schema = install.schema
        binding = (
            claims.sub, claims.acting_user_id, partition, request.query, request.limit,
            claims.installation_epoch, tuple(claims.field_allowlist), claims.recipient,
            claims.purpose, claims.grant_id,
        )
        now = int(self.clock().timestamp())
        offset = 0
        if request.cursor is not None:
            cursor = self._cursors.get(request.cursor)
            if cursor is None or cursor.binding != binding:
                raise ProtocolError("unavailable")
            if (
                cursor.watermark != base["watermark"] or cursor.grant_epoch != claims.grant_epoch
                or cursor.grant_version != policy.grant_version
                or cursor.app_policy != policy.app_policy or cursor.expires_at <= self.clock().timestamp()
            ):
                raise ProtocolError("stale_dependency")
            offset = cursor.offset
        utf8_bound(request.query, 256)
        self._lookup("search", partition)
        matches = []
        for ref, record in self._records.get(partition, {}).items():
            if (partition, ref) in self._hidden or not is_fresh(record, install, policy.expires_at, self.clock()):
                continue
            title = dict(record.values).get("title")
            validate_projection(schema, ("title",), {"title": title})
            if request.query in title:
                matches.append(record)
        # Two stable sorts retain ascending refs for equal effective times.
        matches.sort(key=lambda record: record.ref)
        matches.sort(key=lambda record: record.effective_at, reverse=True)
        end = offset + request.limit
        next_cursor = None
        if end < len(matches):
            cursor = Cursor(
                binding, claims.grant_epoch, policy.grant_version, policy.app_policy,
                base["watermark"], end, min(
                    now + 60, *(expiry(row, install, policy.expires_at).timestamp() for row in matches),
                ),
            )
            # An integrity-protected handle reveals no binding or position.
            next_cursor = hmac.new(
                self.delegations.keys[self.service.key_id],
                encode([binding, cursor.grant_epoch, cursor.grant_version, cursor.app_policy,
                        cursor.watermark, end, str(cursor.expires_at)]),
                hashlib.sha256,
            ).hexdigest()
            self._cursors = {key: value for key, value in self._cursors.items()
                             if value.expires_at > now}
            if len(self._cursors) >= 256 and next_cursor not in self._cursors:
                raise ProtocolError("rate_limited")
            self._cursors[next_cursor] = cursor
        return base | {
            "items": [{
                "record_ref": record.ref, "source_revision": record.revision,
                "record_kind": schema.kind, "effective_at": stamp(record.effective_at),
                "title": dict(record.values)["title"],
            } for record in matches[offset:end]],
            "next_cursor": next_cursor,
        }


def expiry(record, install, grant_expiry):
    return min(
        record.expires_at,
        record.observed_at + timedelta(seconds=install.binding.max_ttl_seconds),
        install.expires_at, grant_expiry,
    )


def is_fresh(record, install, grant_expiry, now):
    timestamps = (record.effective_at, record.observed_at, record.expires_at)
    return (
        all(value.utcoffset() == timedelta(0) for value in timestamps)
        and record.effective_at <= record.observed_at <= now < expiry(record, install, grant_expiry)
        and record.sensitivity == install.schema.sensitivity
    )


def describe_operations(operations, allowed_fields):
    return tuple(op for op in ("search", "fetch") if op in operations
                 and (op != "search" or "title" in allowed_fields))


def validate_projection(schema, fields, values):
    if set(values) != set(fields):
        raise ProtocolError("invalid_request")
    for field, value in values.items():
        if type(value) is not schema.field_types.get(field):
            raise ProtocolError("invalid_request")
        if type(value) is str:
            utf8_bound(value, MAX_STRING)


def describe(install, fields, operations):
    return install.envelope() | {
        "schema_version": SCHEMA, "operations": list(operations),
        "kinds": [{
            "name": install.schema.kind,
            "fields": [{
                "name": name, "type": "string" if python_type is str else "integer",
                "sensitivity": install.schema.sensitivity,
            } for name, python_type in install.schema.fields if name in fields],
        }],
        "max_page_size": 10, "max_record_bytes": MAX_MESSAGE,
        "max_ttl_seconds": install.binding.max_ttl_seconds,
    }
