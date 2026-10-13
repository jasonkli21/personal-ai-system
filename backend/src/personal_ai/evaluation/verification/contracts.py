"""Strict verification schema and fail-closed release projections."""

from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Status = Literal["passed", "failed", "blocked", "unverified", "not-applicable"]
EvidenceClass = Literal["offline", "local", "cloud", "live", "domain", "browser"]
NORMATIVE_BOUNDARIES = frozenset(
    {
        "isolation",
        "federation",
        "context-quality",
        "planner-optimization",
        "search-optimization",
        "memory-optimization",
        "adaptive-routing",
        "combined-resources",
        "strict-free",
        "sensitivity",
        "cascades",
        "mutations",
        "provider-transport",
        "artifacts",
        "export-deletion",
        "persistence",
        "storage-ownership",
        "endpoint-churn",
        "chatgpt",
        "client-actions",
        "app-conformance",
        "provider-conformance",
        "soak",
        "verification",
        "cross-cloud",
        "identity",
        "operations",
    }
)
FAULT_IDS = frozenset(
    {
        "timeout",
        "cancellation",
        "stale-version",
        "quota-exhaustion",
        "malformed-provider",
        "partial-persistence",
        "uncertain-outcome",
        "boundary-revocation",
        "artifact-outage",
        "database-outage",
        "network-outage",
        "revoked-cache",
        "endpoint-churn",
    }
)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class VerificationRow(Contract):
    verification_id: str = Field(pattern=r"^P36-[A-Z0-9-]+$")
    boundary: str = Field(min_length=1)
    capability: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    preconditions: tuple[str, ...] = Field(min_length=1)
    evidence_class: EvidenceClass
    fixtures_environment: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    severity: Literal["critical", "high", "quality", "resource", "informational"]
    mandatory: bool = True
    test_refs: tuple[str, ...] = ()
    command: str = Field(min_length=1)
    authority_ref: str = Field(min_length=1)
    evidence_ref: str | None = None
    tested_revision: str | None = None
    configuration_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    status: Status = "unverified"
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def reference_and_evidence(self):
        if self.evidence_class == "offline" and not self.test_refs:
            raise ValueError("offline_row_requires_executable_reference")
        if any(not ref.startswith("tests/") or ".." in ref or " " in ref for ref in self.test_refs):
            raise ValueError("invalid_test_reference")
        if self.status == "passed" and not all(
            (
                self.evidence_ref,
                self.tested_revision,
                self.configuration_sha256,
            )
        ):
            raise ValueError("pass_requires_bound_evidence")
        return self


class VerificationMatrix(Contract):
    schema_version: Literal["phase36-matrix-v1"] = "phase36-matrix-v1"
    normative_boundaries: tuple[str, ...] = Field(min_length=1)
    strategy_coverage: dict[str, str]
    thresholds: dict[str, float]
    fault_scenarios: tuple[FaultScenario, ...] = Field(min_length=13, max_length=32)
    rows: tuple[VerificationRow, ...] = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def coverage(self):
        ids = [row.verification_id for row in self.rows]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_verification_id")
        if set(self.normative_boundaries) != {row.boundary for row in self.rows}:
            raise ValueError("normative_boundary_without_evidence_or_blocker")
        if set(self.normative_boundaries) != NORMATIVE_BOUNDARIES:
            raise ValueError("normative_contract_coverage_changed")
        if {fault.fault_id for fault in self.fault_scenarios} != FAULT_IDS:
            raise ValueError("fault_contract_coverage_changed")
        if len({fault.fault_id for fault in self.fault_scenarios}) != len(self.fault_scenarios):
            raise ValueError("duplicate_fault_id")
        by_id = {r.verification_id: r for r in self.rows}
        for fault in self.fault_scenarios:
            row = by_id.get(fault.verification_id)
            if (
                row is None
                or row.evidence_class != "offline"
                or any(
                    not any(
                        ref == parent or ref.startswith(parent + "::") for parent in row.test_refs
                    )
                    for ref in fault.test_refs
                )
            ):
                raise ValueError("fault_requires_offline_executable_row")
        return self


class FaultScenario(Contract):
    fault_id: str
    verification_id: str
    injection_point: str = Field(min_length=1)
    test_refs: tuple[str, ...] = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    safety_constraint: Literal["synthetic-only-no-external-effects"]


def execution_status(refs, cases):
    """Every referenced parametrization must execute; failure dominates absence."""
    outcomes = []
    missing = False
    for ref in refs:
        matching = [
            c
            for c in cases
            if c["nodeid"] == ref
            or c["nodeid"].startswith(ref + "[")
            or c["nodeid"].startswith(ref + "::")
        ]
        missing |= not matching
        outcomes.extend(c["status"] for c in matching)
    if "failed" in outcomes:
        return "failed"
    if missing or not outcomes or any(s != "passed" for s in outcomes):
        return "unverified"
    return "passed"


def release_projection(rows):
    """Availability is a reporting projection, never permission to enable a gate."""
    capabilities = {}
    for row in rows:
        capability = capabilities.setdefault(row.capability, {"blockers": [], "passed": []})
        if row.status == "passed":
            capability["passed"].append(row.verification_id)
        elif row.mandatory and row.status != "not-applicable":
            capability["blockers"].append(
                {
                    "verification_id": row.verification_id,
                    "status": row.status,
                    "severity": row.severity,
                    "evidence_class": row.evidence_class,
                    "authority_ref": row.authority_ref,
                    "rationale": row.rationale,
                }
            )
    for capability in capabilities.values():
        capability["release_status"] = (
            "unavailable" if capability["blockers"] else "evidence_complete_for_declared_scope"
        )
    return {
        "status_counts": dict(Counter(row.status for row in rows)),
        "capabilities": capabilities,
        "release_ready": not any(c["blockers"] for c in capabilities.values()),
    }


def integrated_promotion(measurements, thresholds):
    """Synthetic resource benefit is necessary, never sufficient for live promotion."""
    combined = [m for m in measurements if m.get("kind") == "combined-implemented-paths-v1"]
    saving = combined[0].get("aggregate_saving_fraction") if len(combined) == 1 else None
    minimum = thresholds["minimum_aggregate_resource_saving_fraction"]
    return {
        "promoted_coverage": [],
        "gates": {
            "synthetic_aggregate_resource_saving": {
                "status": "unverified"
                if saving is None
                else "passed"
                if saving >= minimum
                else "failed",
                "observed": saving,
                "threshold": minimum,
            },
            **{
                name: {"status": "unverified", "observed": None}
                for name in (
                    "supported_live_answer_quality",
                    "whole_workflow_p95_latency",
                    "complete_physical_attempt_quota_lineage",
                    "native_store_operations_storage_headroom",
                    "assisted_planner_implementation",
                )
            },
        },
        "decision": "not_promoted",
    }
