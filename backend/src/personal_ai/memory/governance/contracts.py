"""Closed, content-free memory governance wire contracts. None establish identity."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from personal_ai.auth.scope import ApplicationScope
from personal_ai.memory.knowledge import Strict, digest

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$")]
Epoch = Annotated[int, Field(strict=True, ge=0)]
Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Outcome = Literal["committed", "uncertain", "replayed", "conflict", "denied", "unavailable"]


class Closed(Strict):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")


class MemoryScope(Closed):
    owner: Identifier
    agent: Identifier
    application: ApplicationScope
    project: Identifier


class SourceReference(Closed):
    scope: MemoryScope
    record: UUID
    version: Identifier


class ShareIntent(Closed):
    schema_version: Literal["memory-share-intent-v1"] = "memory-share-intent-v1"
    operation_id: UUID
    operation: Literal["grant", "revoke"]
    grant_id: UUID
    expected_revision: Epoch
    source: SourceReference
    destination: MemoryScope
    purpose: Literal["assist_response"] = "assist_response"
    ceiling: Literal["internal_read"] = "internal_read"
    decision_proof: Identifier
    expires_at: datetime

    def fingerprint(self, actor: str) -> str:
        return digest({"actor": actor, "intent": self.model_dump(mode="json")})


class DependencyEpochs(Closed):
    owner: Epoch
    source: Epoch
    target: Epoch
    generation: Epoch


class GrantRecord(Closed):
    schema_version: Literal["memory-grant-v1"] = "memory-grant-v1"
    intent: ShareIntent
    actor: Identifier
    revision: Epoch
    epochs: DependencyEpochs
    policy: Literal["memory-governance-v1"] = "memory-governance-v1"
    issued_at: datetime
    revoked: bool = False

    @model_validator(mode="after")
    def valid_lifetime(self):
        if self.intent.operation != "grant" or self.issued_at >= self.intent.expires_at:
            raise ValueError("invalid_grant")
        return self


class GrantReceipt(Closed):
    schema_version: Literal["memory-grant-receipt-v1"] = "memory-grant-receipt-v1"
    operation_id: UUID
    fingerprint: Hash
    outcome: Outcome
    revision: Epoch
    grant_id: UUID
    reason: Literal["ok", "policy_denied", "capacity", "conflict", "storage_unavailable"]


class EffectiveGrantDecision(Closed):
    schema_version: Literal["memory-grant-decision-v1"] = "memory-grant-decision-v1"
    allowed: bool
    reason: Literal["ok", "policy_denied", "unavailable", "external_delivery_blocked"]
    epochs: DependencyEpochs | None = None
    grant_fingerprint: Hash | None = None

    @model_validator(mode="after")
    def decision_shape(self):
        if self.allowed != (self.reason == "ok") or self.allowed != (
            self.epochs is not None and self.grant_fingerprint is not None
        ):
            raise ValueError("invalid_decision")
        return self


Store = Literal[
    "canonical",
    "source_edges",
    "indexes",
    "memories",
    "summaries",
    "caches",
    "pending_proposals",
    "episodes",
    "research_artifacts",
    "jobs",
    "backups",
    "external_copies",
]
STORES = (
    "canonical",
    "source_edges",
    "indexes",
    "memories",
    "summaries",
    "caches",
    "pending_proposals",
    "episodes",
    "research_artifacts",
    "jobs",
    "backups",
    "external_copies",
)


class StoreVerification(Closed):
    store: Store
    topology: Literal["synthetic_managed", "inventory_only", "unobserved_external"]
    status: Literal["logical_suppression", "physical_verified", "pending", "unknown"]
    proof: Hash | None = None
    depends_on: tuple[Store, ...] = Field(default=(), max_length=4)

    @model_validator(mode="after")
    def physical_proof(self):
        if self.status == "physical_verified":
            raise ValueError("physical_verification_requires_observed_topology_contract")
        return self


class DeletionPropagationReceipt(Closed):
    schema_version: Literal["memory-deletion-propagation-v1"] = "memory-deletion-propagation-v1"
    operation_id: UUID
    owner_epoch: Epoch
    stores: tuple[StoreVerification, ...] = Field(min_length=12, max_length=12)

    @model_validator(mode="after")
    def complete_inventory(self):
        if {s.store for s in self.stores} != set(STORES):
            raise ValueError("incomplete_store_inventory")
        dependencies = {s.store: s.depends_on for s in self.stores}
        visited = set()

        def visit(store, active):
            if store in active:
                raise ValueError("cyclic_deletion_dependencies")
            if store in visited:
                return
            for dependency in dependencies[store]:
                visit(dependency, active | {store})
            visited.add(store)

        for store in dependencies:
            visit(store, set())
        return self


class ResourceLimits(Closed):
    grants: int = Field(default=16, strict=True, ge=1, le=128)
    lookup_page: int = Field(default=8, strict=True, ge=1, le=32)
    fan_out: int = Field(default=2, strict=True, ge=1, le=8)
    source_fences: int = Field(default=32, strict=True, ge=1, le=1024)
    maintenance_backlog: int = Field(default=32, strict=True, ge=1, le=128)
    retries: int = Field(default=2, strict=True, ge=0, le=4)
    export_bytes: int = Field(default=8192, strict=True, ge=1, le=8192)
    index_bytes: int = Field(default=65536, strict=True, ge=1, le=65536)


class QuotaSnapshot(Closed):
    schema_version: Literal["memory-governance-quota-v1"] = "memory-governance-quota-v1"
    limits: ResourceLimits
    grants: Epoch
    original_keys: Epoch
    tombstones: Epoch
    source_fences: Epoch
    maintenance_backlog: Epoch
    serialized_bytes: Epoch
    # Each accepted grant reserves one permanent revoke key. No safety eviction.
    reserved_revoke_keys: Epoch
