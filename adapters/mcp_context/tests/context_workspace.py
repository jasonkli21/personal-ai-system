"""Synthetic workspace-less Travel authority over owning-domain trip records."""

import json
from collections import Counter
from dataclasses import replace

from app_context_support.fixtures import FITNESS, SOURCES, TRAVEL
from app_context_support.source import expiry, is_fresh, validate_projection
from app_context_support.wire import ProtocolError, encode
from context_host import ALT_CLIENT, ISSUER, TRAVEL_CLIENT, SyntheticHost
from personal_ai.applications.registry import ApplicationRegistry
from personal_ai_mcp_context.contracts import (
    MAX_HITS,
    AuthorizedRead,
    FetchedRecord,
    Identity,
    SearchHit,
    SearchPage,
    SourceInstallation,
)

TRAVEL_INSTALLATIONS = frozenset(
    SourceInstallation(tenant, TRAVEL, SOURCES[TRAVEL], f"install-{TRAVEL}")
    for tenant in ("tenant-a", "tenant-b")
)
TRAVEL_INSTALLATION = next(item for item in TRAVEL_INSTALLATIONS if item.tenant == "tenant-a")


class TravelRecords:
    def __init__(self):
        self.records = {}
        self.owner_acl = set()
        self.record_acl = {}
        self.watermarks = {}
        self.counts = Counter()
        self.lookup_paths = []
        self.before_lookup = None

    def owner(self, binding, identity):
        if (
            binding.tenant, identity.issuer, identity.subject, binding.owner_id, binding.acting_user_id,
        ) not in self.owner_acl:
            raise ProtocolError("unavailable")
        return binding.tenant, binding.owner_id

    def dependency(self, key, binding, install, ref, fields, now):
        record = self.records[key][ref]
        allowed = self.record_acl.get((key, binding.grant_id, ref), frozenset())
        if not set(fields) <= allowed or not is_fresh(record, install, binding.expires_at, now):
            raise ProtocolError("unavailable")
        return self.watermarks[key], record.version(), allowed

    async def read(self, identity, binding, install, selection, budget, clock):
        search = isinstance(selection, str)
        parameters = {"query": selection} if search else {
            "record_ref": selection.record_ref, "revision": selection.revision,
        }
        budget.start("search" if search else "fetch", encode(parameters))
        self.counts["entered"] += 1
        self.counts["active"] += 1
        try:
            if self.before_lookup is not None:
                await self.before_lookup()
            budget.check()
            now = clock()
            key = self.owner(binding, identity)
            self.lookup_paths.append(key)
            watermark = self.watermarks[key]
            dependencies = {}
            fields = ("title",) if search else binding.fields
            if search:
                hits = []
                for ref, record in self.records[key].items():
                    try:
                        dependency = self.dependency(key, binding, install, ref, fields, now)
                    except ProtocolError:
                        continue
                    title = dict(record.values)["title"]
                    validate_projection(install.schema, fields, {"title": title})
                    if selection.casefold() not in title.casefold():
                        continue
                    dependencies[ref] = dependency
                    hits.append(SearchHit(ref, record.revision, title, expiry(record, install, binding.expires_at)))
                    if len(hits) == MAX_HITS:
                        break
                projected = SearchPage(watermark, tuple(hits))
                budget.charge_hits(len(hits))
                raw = encode([hit.title for hit in hits])
            else:
                ref = selection.record_ref
                dependency = self.dependency(key, binding, install, ref, fields, now)
                record = self.records[key][ref]
                if (selection.watermark, selection.revision) != (watermark, record.revision):
                    raise ProtocolError("unavailable")
                dependencies[ref] = dependency
                values = dict(record.values)
                payload = {field: values[field] for field in fields}
                validate_projection(install.schema, fields, payload)
                raw = encode(payload)
                budget.charge_hits(1)
                projected = FetchedRecord(
                    ref, record.revision, watermark, binding.source_id, payload["title"],
                    json.dumps(payload, ensure_ascii=False), record.observed_at,
                    expiry(record, install, binding.expires_at),
                )
            budget.charge_bytes(raw)
            budget.charge_tokens(raw)
            return projected, fields, watermark, dependencies
        finally:
            self.counts["active"] -= 1
            self.counts["exited"] += 1


class WorkspaceLessHost(SyntheticHost):
    def __init__(self):
        super().__init__()
        self.travel = TravelRecords()
        registry = self.pas.registry
        self.pas.authority.registry = ApplicationRegistry(
            (registry.get(TRAVEL).model_copy(update={"workspace_kind": "unsupported"}), registry.get(FITNESS)),
            registry.capabilities,
        )
        for owner, client, trip in (
            ("a", TRAVEL_CLIENT, "trip-a"), ("a", ALT_CLIENT, "trip-a-ungranted"),
            ("b", TRAVEL_CLIENT, "trip-b"),
        ):
            principal = self.pas.principals[owner]
            identity = Identity(ISSUER, principal.subject, client)
            connection, = self.connections[Identity(ISSUER, principal.subject, TRAVEL_CLIENT)]
            grant = self.pas.authority.grants[connection.grant_id]
            fields = ("title", "platform") if client == ALT_CLIENT else grant.fields
            grant_id = f"grant-record-{owner}-{client}"
            self.pas.authority.grants[grant_id] = replace(grant, id=grant_id, workspace=None, fields=fields)
            self.connections[identity] = (replace(
                connection, id=f"connection-record-{owner}-{client}", workspace=None, grant_id=grant_id,
            ),)
            self.pas.authority.memberships[principal.issuer, principal.subject, TRAVEL, None] = (
                principal.owner_id, grant.actor,
            )
            self.travel.owner_acl.add((connection.tenant, ISSUER, principal.subject, principal.owner_id, grant.actor))
            record = self.pas.records[trip]
            if client == ALT_CLIENT:
                record = replace(record, ref="r02")
            key = connection.tenant, principal.owner_id
            self.travel.records.setdefault(key, {})[record.ref] = record
            self.travel.record_acl[key, grant_id, record.ref] = frozenset(fields)
            self.travel.watermarks[key] = "trip-records-v1"

    def _resolve(self, identity, operation):
        resolved = super()._resolve(identity, operation)
        binding = resolved[0]
        if binding.scope.application_id == TRAVEL:
            self.travel.owner(binding, identity)
        return resolved

    async def read(self, identity, binding, selection, budget):
        if binding.scope.application_id != TRAVEL:
            return await super().read(identity, binding, selection, budget)
        operation = "search" if isinstance(selection, str) else "fetch"
        current, _, _, _, _, install = self._resolve(identity, operation)
        if current != binding:
            raise ProtocolError("unavailable")
        key = self.travel.owner(binding, identity)
        projected, fields, watermark, dependencies = await self.travel.read(
            identity, binding, install, selection, budget, lambda: self.pas.now,
        )

        def revalidate():
            if self._resolve(identity, operation)[0] != binding or self.travel.watermarks[key] != watermark:
                raise ProtocolError("unavailable")
            for ref, previous in dependencies.items():
                if self.travel.dependency(key, binding, install, ref, fields, self.pas.now) != previous:
                    raise ProtocolError("unavailable")

        if self.before_release is not None:
            await self.before_release()
        return AuthorizedRead(projected, revalidate)

    def app(self, **kwargs):
        return super().app(**({"workspace_less_sources": TRAVEL_INSTALLATIONS} | kwargs))
