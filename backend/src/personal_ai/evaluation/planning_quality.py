"""Phase 22 task-quality adapter for outputs bound to assembled planning context."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from personal_ai.evaluation.provider_matrix import score_output
from personal_ai.evaluation.provider_matrix_contracts import EvaluationFixture


class PlanningAnswerQualityEvidence(BaseModel):
    """Compact quality observation; prompts, answers, and source IDs are not retained."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "planning-answer-quality-v1"
    strategy_version: str = Field(
        min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._:/@+_-]{1,100}$"
    )
    configuration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_suite_id: str = Field(min_length=1, max_length=200)
    evaluation_suite_version: int = Field(ge=1)
    fixture_id_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_profile_id: str = Field(min_length=1, max_length=200)
    task_profile_version: int = Field(ge=1)
    scoring_policy_id: str = Field(min_length=1, max_length=200)
    scoring_policy_version: int = Field(ge=1)
    provider_id: str = Field(
        min_length=1, max_length=200, pattern=r"^[A-Za-z0-9@][A-Za-z0-9._:/@+_-]{0,199}$"
    )
    model_id: str = Field(
        min_length=1, max_length=200, pattern=r"^[A-Za-z0-9@][A-Za-z0-9._:/@+_-]{0,199}$"
    )
    evaluation_evidence_identity: str = Field(
        min_length=1, max_length=200,
        pattern=r"^[A-Za-z0-9@][A-Za-z0-9._:/@+_-]{0,199}$",
    )
    evidence_kind: Literal["phase22_observed"] = "phase22_observed"
    tested_revision: str = Field(
        min_length=7, max_length=100,
        pattern=r"^[0-9a-f]{7,64}(-working-tree-[0-9a-f]{12})?$",
    )
    counter_identity: str = Field(
        min_length=1, max_length=200, pattern=r"^[A-Za-z0-9@][A-Za-z0-9._:/@+_-]{0,199}$"
    )
    assembled_context_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    assembled_source_dependencies_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    supported_answer_rate: float = Field(ge=0, le=1)
    hard_boundaries_passed: bool

    @field_validator("schema_version")
    @classmethod
    def schema_version_is_current(cls, value):
        if value != "planning-answer-quality-v1":
            raise ValueError("planning_answer_quality_schema_unsupported")
        return value


def measure_planning_answer(
    assembled,
    fixture: EvaluationFixture,
    output_text: str,
    *,
    source_bindings: Mapping[str, str],
    strategy_version: str,
    configuration_digest: str,
    provider_id: str,
    model_id: str,
    evaluation_evidence_identity: str,
    tested_revision: str,
    counter_identity: str,
) -> PlanningAnswerQualityEvidence:
    """Score an observed answer against only evidence injected in this assembled input.

    ``source_bindings`` is request-local and maps Phase 22 fixture source IDs to
    transient source-reference IDs. Neither side of that mapping is retained.
    """
    if assembled.manifest is None or assembled.manifest.actual_build is not True:
        raise ValueError("planning_quality_requires_actual_context_build")
    injected = {
        (item.provider_id, item.item_id)
        for item in assembled.manifest.items
        if item.injected
    }
    available_reference_ids = {
        reference.reference_id
        for item in assembled.source_items
        if (item.provider_id, item.item_id) in injected
        for reference in item.source_refs
    }
    available_fixture_sources = tuple(
        source_id
        for source_id in fixture.source_ids
        if source_bindings.get(source_id) in available_reference_ids
    )
    # Expected claims remain complete. A claim whose source was not assembled
    # cannot receive support credit, even if the output names that hidden source.
    bound_fixture = fixture.model_copy(update={"source_ids": available_fixture_sources})
    metrics = score_output(bound_fixture, output_text)
    context_digest = assembled_context_digest(assembled)
    output_digest = hashlib.sha256(output_text.encode()).hexdigest()
    case_digest = fixture.case_identity_sha256
    source_dependencies_digest = hashlib.sha256(json.dumps(
        sorted(hashlib.sha256(source_id.encode()).hexdigest() for source_id in available_fixture_sources),
        separators=(",", ":"),
    ).encode()).hexdigest()
    identity_payload = {
        "suite": [fixture.evaluation_suite_id, fixture.evaluation_suite_version],
        "fixture_digest": case_digest,
        "task": [fixture.task_profile_id, fixture.task_profile_version],
        "scoring": [fixture.scoring_policy_id, fixture.scoring_policy_version],
        "strategy": strategy_version,
        "configuration_digest": configuration_digest,
        "provider": provider_id,
        "model": model_id,
        "evaluation_evidence_identity": evaluation_evidence_identity,
        "tested_revision": tested_revision,
        "counter_identity": counter_identity,
        "context_digest": context_digest,
        "source_dependencies_digest": source_dependencies_digest,
        "output_digest": output_digest,
    }
    evidence_identity = hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return PlanningAnswerQualityEvidence(
        strategy_version=strategy_version,
        configuration_digest=configuration_digest,
        evaluation_suite_id=fixture.evaluation_suite_id,
        evaluation_suite_version=fixture.evaluation_suite_version,
        fixture_id_digest=hashlib.sha256(fixture.fixture_id.encode()).hexdigest(),
        task_profile_id=fixture.task_profile_id,
        task_profile_version=fixture.task_profile_version,
        scoring_policy_id=fixture.scoring_policy_id,
        scoring_policy_version=fixture.scoring_policy_version,
        provider_id=provider_id,
        model_id=model_id,
        evaluation_evidence_identity=evaluation_evidence_identity,
        evidence_kind="phase22_observed",
        tested_revision=tested_revision,
        counter_identity=counter_identity,
        assembled_context_digest=context_digest,
        assembled_source_dependencies_digest=source_dependencies_digest,
        output_digest=output_digest,
        evidence_identity=evidence_identity,
        supported_answer_rate=metrics.answer_support,
        hard_boundaries_passed=metrics.hard_boundaries_passed,
    )


def assembled_context_digest(assembled) -> str:
    """Content-address the exact assembled input without retaining its content."""
    context_payload = [
        {
            "role": getattr(message.role, "value", message.role),
            "content": message.content,
        }
        for message in assembled.messages
    ]
    return hashlib.sha256(
        json.dumps(context_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        .encode()
    ).hexdigest()
