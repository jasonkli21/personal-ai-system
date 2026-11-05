"""Inert capability previews, bounded work admission and operator proposals."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from personal_ai.memory.governance.contracts import (
    STORES,
    Closed,
    DeletionPropagationReceipt,
    GrantRecord,
    ResourceLimits,
    StoreVerification,
)


class WorkRequest(Closed):
    lookup_page: int = Field(strict=True, ge=0)
    fan_out: int = Field(strict=True, ge=0)
    source_fences: int = Field(strict=True, ge=0)
    maintenance_backlog: int = Field(strict=True, ge=0)
    retries: int = Field(strict=True, ge=0)
    export_bytes: int = Field(strict=True, ge=0)
    index_bytes: int = Field(strict=True, ge=0)


def admit_work(work: WorkRequest, limits: ResourceLimits):
    """No job starts here; callers must not truncate or evict safety state."""
    work = WorkRequest.model_validate(work.model_dump())
    return all(getattr(work, key) <= getattr(limits, key) for key in WorkRequest.model_fields)


def retention_inventory(operation_id: UUID, owner_epoch: int, *, suppressed: bool):
    """E1 inventory, never evidence of physical purge on any real topology."""
    dependencies = {
        "canonical": (),
        "source_edges": ("canonical",),
        "memories": ("canonical", "source_edges"),
        "indexes": ("memories",),
        "summaries": ("memories",),
        "caches": ("indexes", "summaries"),
        "pending_proposals": ("source_edges",),
        "episodes": ("source_edges",),
        "research_artifacts": ("memories",),
        "jobs": ("memories", "pending_proposals"),
        "backups": ("canonical", "memories", "jobs"),
        "external_copies": ("memories",),
    }
    return DeletionPropagationReceipt(
        operation_id=operation_id,
        owner_epoch=owner_epoch,
        stores=tuple(
            StoreVerification(
                store=store,
                depends_on=dependencies[store],
                topology=(
                    "unobserved_external"
                    if store in {"backups", "external_copies"}
                    else "inventory_only"
                    if store in {"episodes", "research_artifacts"}
                    else "synthetic_managed"
                ),
                status=(
                    "unknown"
                    if store in {"backups", "external_copies", "episodes", "research_artifacts"}
                    else "logical_suppression"
                    if suppressed
                    else "pending"
                ),
            )
            for store in STORES
        ),
    )


def owner_preview(record: GrantRecord):
    """Host-private rendering helper; no route, no content, no export/import commit."""
    return {
        "status": "preview_only",
        "destination": record.intent.destination.model_dump(mode="json"),
        "purpose": record.intent.purpose,
        "expires_at": record.intent.expires_at.isoformat(),
        "retention": "source expiry and lifecycle may shorten grant lifetime",
        "knowledge_export": False,
        "episode_export": False,
        "import_commit": False,
        "external_delivery": False,
        "warning": "External copies cannot be recalled. Revoke fences future managed reads only.",
    }


class OperatorRequest(Closed):
    schema_version: Literal["memory-governance-plan-request-v1"] = (
        "memory-governance-plan-request-v1"
    )
    operation: Literal["canary", "rollback"]
    profile: Literal["synthetic_only"] = "synthetic_only"
    evidence_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


def operator_plan(request: OperatorRequest):
    request = OperatorRequest.model_validate(request.model_dump())
    return {
        "schema_version": "memory-governance-operator-plan-v1",
        "operation": request.operation,
        "evidence_digest": request.evidence_digest,
        "executable": False,
        "production": "NO_GO",
        "status": "proposal_only",
        "stages": (
            "synthetic_preflight",
            "independent_review",
            "separately_authorized_native_drill",
        ),
        "stop_conditions": (
            "unauthorized_read",
            "stale_epoch",
            "unknown_cost",
            "missing_authority",
        ),
        "rollback": "stop new reads/sends; preserve receipts; reconcile surviving authority",
    }
