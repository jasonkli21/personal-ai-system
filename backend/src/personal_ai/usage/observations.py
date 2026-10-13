"""Read-only resource projection of canonical physical-attempt observations."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PipelineMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["p19-resource-projection-v1"] = "p19-resource-projection-v1"
    complete: bool
    settled: bool
    # A retained P19 snapshot does not by itself prove that prior invocations
    # have not expired. Complete root lineage/end-to-end measurements are a
    # separate evidence requirement, not inferred from bounded case metrics.
    lineage_complete: Literal[False] = False
    end_to_end_latency_ms: None = None
    physical_attempts: int = Field(ge=0, le=512)
    reserved_attempts: int = Field(ge=0, le=512)
    auxiliary_attempts: int = Field(ge=0, le=512)
    retry_attempts: int = Field(ge=0, le=512)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    provider_latency_ms: int | None = Field(default=None, ge=0)
    conservative_reserved_tokens: int = Field(ge=0)
    conservative_quota_reservations: tuple[tuple[str, int], ...] = Field(max_length=128)
    endpoint_distribution: dict[str, int] = Field(max_length=32)


def pipeline_metrics(attempts, *, complete):
    """Do not impute unknown consumption or count reservations as physical sends.

    Each input row is a canonical P19 invocation/attempt join. Quota reservations
    are reported separately from known actual token consumption. Claims with an
    uncertain external outcome remain physical dispatch attempts, never successes.
    """
    sent = [r for r in attempts if r["dispatch_claimed_at"] is not None]
    settled = complete and all(
        r["status"] not in {"pending", "unknown", "timeout"} for r in attempts
    )

    def total(field):
        return sum(r[field] for r in sent) if all(r[field] is not None for r in sent) else None

    quota = {}
    for row in attempts:
        for bucket, units in row["reservations"]:
            quota[bucket] = quota.get(bucket, 0) + units
    return PipelineMetrics.model_validate(
        {
            "complete": complete,
            "settled": settled,
            "physical_attempts": len(sent),
            "reserved_attempts": len(attempts),
            "auxiliary_attempts": sum(r["operation"] == "token_counting" for r in sent),
            "retry_attempts": sum(r["parent_attempt_id"] is not None for r in sent),
            "input_tokens": total("input_tokens"),
            "output_tokens": total("output_tokens"),
            "provider_latency_ms": total("latency_ms"),
            "conservative_reserved_tokens": sum(r["reserved_tokens"] for r in attempts),
            "conservative_quota_reservations": sorted(quota.items()),
            "endpoint_distribution": {
                endpoint: sum(r["endpoint_profile_id"] == endpoint for r in sent)
                for endpoint in sorted({r["endpoint_profile_id"] for r in sent})
            },
        }
    ).model_dump()
