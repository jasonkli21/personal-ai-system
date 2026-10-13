"""Strict verification schema and fail-closed release projections."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
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
    required_profile_identities: dict[str, str] = Field(default_factory=dict, max_length=16)
    maximum_evidence_age_seconds: int = Field(default=2_592_000, ge=1, le=31_536_000)
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


class ExternalEvidenceReceipt(Contract):
    """Auditable result submitted by a separately executed non-offline gate."""

    receipt_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    verification_id: str = Field(pattern=r"^P36-[A-Z0-9-]+$")
    evidence_class: Literal["local", "cloud", "live", "domain", "browser"]
    status: Literal["passed", "failed"]
    authority_ref: str = Field(min_length=1)
    originating_command: str = Field(min_length=1)
    tested_revision: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    matrix_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    environment_configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    profile_identities: dict[str, str] = Field(min_length=1, max_length=16)
    artifact_ref: str = Field(min_length=1, max_length=500)
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recorded_at: datetime
    expires_at: datetime
    operator_provenance: str = Field(min_length=1, max_length=200)
    reviewer_provenance: str | None = Field(default=None, min_length=1, max_length=200)
    supersedes_receipt_id: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
    )

    @model_validator(mode="after")
    def timestamps_are_bounded_and_aware(self):
        if (
            self.recorded_at.tzinfo is None
            or self.recorded_at.utcoffset() is None
            or self.expires_at.tzinfo is None
            or self.expires_at.utcoffset() is None
            or self.expires_at <= self.recorded_at
        ):
            raise ValueError("external_receipt_timestamps_invalid")
        if any(not name or not value for name, value in self.profile_identities.items()):
            raise ValueError("external_receipt_profile_identity_invalid")
        return self


class ExternalEvidenceManifest(Contract):
    schema_version: Literal["phase36-external-evidence-v1"] = "phase36-external-evidence-v1"
    matrix_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipts: tuple[ExternalEvidenceReceipt, ...] = Field(default=(), max_length=256)

    @model_validator(mode="after")
    def receipt_ids_are_unique(self):
        receipt_ids = [item.receipt_id for item in self.receipts]
        if len(receipt_ids) != len(set(receipt_ids)):
            raise ValueError("external_receipt_replay_or_duplicate_id")
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


def merge_external_evidence(
    rows,
    manifest: ExternalEvidenceManifest | None,
    *,
    tested_revision: str,
    source_configuration_sha256: str,
    matrix_sha256: str,
    now: datetime | None = None,
):
    """Merge only current receipts whose class, authority, code and profiles match."""
    if manifest is None:
        return tuple(rows), {"accepted": [], "rejected": []}
    now = now or datetime.now(UTC)
    row_by_id = {row.verification_id: row for row in rows}
    grouped: dict[str, list[ExternalEvidenceReceipt]] = {}
    rejected = []
    for receipt in manifest.receipts:
        row = row_by_id.get(receipt.verification_id)
        if row is None:
            rejected.append({"receipt_id": receipt.receipt_id, "reason": "unknown_verification_id"})
            continue
        grouped.setdefault(receipt.verification_id, []).append(receipt)

    updates = {}
    accepted = []
    for verification_id, receipts in grouped.items():
        roots = [receipt for receipt in receipts if receipt.supersedes_receipt_id is None]
        children: dict[str, list[ExternalEvidenceReceipt]] = {}
        for receipt in receipts:
            if receipt.supersedes_receipt_id is not None:
                children.setdefault(receipt.supersedes_receipt_id, []).append(receipt)
        chain = []
        if len(roots) == 1:
            current = roots[0]
            chain.append(current)
            while len(children.get(current.receipt_id, ())) == 1:
                current = children[current.receipt_id][0]
                chain.append(current)
                if len(chain) > len(receipts):
                    break
        if (
            len(roots) != 1
            or len(chain) != len(receipts)
            or any(len(children.get(receipt.receipt_id, ())) > 1 for receipt in chain)
        ):
            rejected.extend(
                {"receipt_id": receipt.receipt_id, "reason": "receipt_chain_invalid"}
                for receipt in receipts
            )
            continue
        receipt = chain[-1]
        row = row_by_id[verification_id]
        reason = None
        if row.evidence_class == "offline" or receipt.evidence_class != row.evidence_class:
            reason = "evidence_class_mismatch"
        elif receipt.authority_ref != row.authority_ref:
            reason = "authority_mismatch"
        elif receipt.originating_command != row.command:
            reason = "command_mismatch"
        elif receipt.tested_revision != tested_revision:
            reason = "tested_revision_mismatch"
        elif manifest.matrix_sha256 != matrix_sha256 or receipt.matrix_sha256 != matrix_sha256:
            reason = "matrix_digest_mismatch"
        elif receipt.source_configuration_sha256 != source_configuration_sha256:
            reason = "source_configuration_mismatch"
        elif any(
            receipt.profile_identities.get(name) != value
            for name, value in row.required_profile_identities.items()
        ):
            reason = "profile_identity_mismatch"
        elif row.severity in {"critical", "high"} and not receipt.reviewer_provenance:
            reason = "reviewer_provenance_required"
        elif (
            receipt.recorded_at > now
            or receipt.expires_at <= now
            or (now - receipt.recorded_at).total_seconds() > row.maximum_evidence_age_seconds
        ):
            reason = "receipt_stale_or_future"
        if reason:
            rejected.append({"receipt_id": receipt.receipt_id, "reason": reason})
            continue
        receipt_json = receipt.model_dump(mode="json")
        receipt_digest = sha256_json(receipt_json)
        updates[verification_id] = row.model_copy(
            update={
                "status": receipt.status,
                "evidence_ref": (
                    f"external-evidence.json#receipt_id={receipt.receipt_id}"
                    f"&sha256={receipt_digest}"
                ),
                "tested_revision": receipt.tested_revision,
                "configuration_sha256": receipt.source_configuration_sha256,
                "rationale": (
                    "Accepted current external evidence receipt."
                    if receipt.status == "passed"
                    else "Accepted current external receipt records a failed result."
                ),
            }
        )
        accepted.append(receipt.receipt_id)
    return tuple(updates.get(row.verification_id, row) for row in rows), {
        "accepted": accepted,
        "rejected": rejected,
    }


def sha256_json(value) -> str:
    """Hash canonical receipt JSON for stable report references."""
    import json
    from hashlib import sha256

    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


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


def integrated_threshold_gates(measurements, thresholds):
    """Give every active integrated threshold a measured or explicitly open result."""
    combined_metrics = [m for m in measurements if m.get("kind") == "combined-implemented-paths-v1"]
    soak_metrics = [m for m in measurements if m.get("kind") == "bounded-soak-v1"]
    combined = combined_metrics[0] if len(combined_metrics) == 1 else None
    soak = soak_metrics[0] if len(soak_metrics) == 1 else None
    rows = combined.get("rows", []) if combined else []
    candidate_rows = [row for row in rows if row.get("variant") == "combined"]
    baseline_rows = [row for row in rows if row.get("variant") == "baseline"]

    def values(items, key):
        return [item[key] for item in items if isinstance(item.get(key), (int, float))]

    def p95(items):
        observations = sorted(values(items, "latency_ms"))
        return (
            observations[max(0, int(len(observations) * 0.95 + 0.999) - 1)]
            if observations
            else None
        )

    baseline_p95 = p95(baseline_rows)
    candidate_p95 = p95(candidate_rows)
    metrics = {
        "minimum_supported_quality_delta": None,
        "maximum_omission_delta": None,
        "maximum_irrelevance_delta": None,
        "minimum_exact_support": min(
            values(candidate_rows, "post_builder_exact_support"), default=None
        ),
        "maximum_false_stale_superseded_memory": (
            soak.get("revoked_cached_memory_selected") if soak else None
        ),
        "maximum_authority_confusion": max(
            values(candidate_rows, "post_builder_authority_confusion"), default=None
        ),
        "minimum_mutation_correctness": None,
        "minimum_aggregate_resource_saving_fraction": (
            combined.get("aggregate_saving_fraction") if combined else None
        ),
        "maximum_pipeline_p95_latency_increase_ms": (
            candidate_p95 - baseline_p95
            if candidate_p95 is not None and baseline_p95 is not None
            else None
        ),
        "maximum_synthetic_pipeline_ms": max(values(candidate_rows, "latency_ms"), default=None),
        "maximum_logical_calls_per_fixture": max(
            (sum(row.get("logical_calls", {}).values()) for row in candidate_rows), default=None
        ),
        "maximum_context_token_estimate": max(
            values(candidate_rows, "assembled_token_estimate"), default=None
        ),
        "soak_iterations": soak.get("iterations") if soak else None,
        "maximum_derived_views_per_soak_turn": max(
            (
                sample.get("derived_views_created")
                for sample in soak.get("samples", [])
                if isinstance(sample.get("derived_views_created"), (int, float))
            ),
            default=None,
        )
        if soak
        else None,
        "maximum_maintenance_jobs_per_soak_turn": max(
            (
                sample.get("maintenance_jobs_created")
                for sample in soak.get("samples", [])
                if isinstance(sample.get("maintenance_jobs_created"), (int, float))
            ),
            default=None,
        )
        if soak
        else None,
    }
    minimums = {
        "minimum_supported_quality_delta",
        "minimum_exact_support",
        "minimum_mutation_correctness",
        "minimum_aggregate_resource_saving_fraction",
    }
    gates = {}
    for name, threshold in thresholds.items():
        observed = metrics.get(name)
        if observed is None:
            status = "unverified"
        elif name == "soak_iterations":
            status = "passed" if observed == threshold else "failed"
        elif name in minimums:
            status = "passed" if observed >= threshold else "failed"
        else:
            status = "passed" if observed <= threshold else "failed"
        gates[name] = {"status": status, "observed": observed, "threshold": threshold}
    return gates


def integrated_promotion(measurements, thresholds):
    """Synthetic gates are reported explicitly; promotion still needs external evidence."""
    gates = integrated_threshold_gates(measurements, thresholds)
    return {
        "promoted_coverage": [],
        "gates": gates,
        "decision": "not_promoted",
    }
