"""Synthetic operation adapter. WorkflowService owns all lifecycle transitions."""

from contextlib import aclosing
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Annotated
from uuid import uuid5

from pydantic import Field

from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.context import ContextAssembler
from personal_ai.context.authorization import authorize_base_disclosure
from personal_ai.contracts.delegated_tasks import canonical_bytes
from personal_ai.contracts.execution import ContinuationRequest, continuation_message_id
from personal_ai.entities import Conversation
from personal_ai.llm.client import ProviderIdentity
from personal_ai.llm.disclosure import bind_disclosure_guard
from personal_ai.llm.execution import compose_pair
from personal_ai.llm.synthetic_reasoning import offline_profile
from personal_ai.llm.workflow_fixture import bind_fixture_attempt
from personal_ai.reasoning.orchestration import (
    INPUT_BYTES,
    OUTPUT_BYTES,
    STEP_MS,
    Checkpoint,
    ReasoningRecord,
    ScopeCeilings,
    Stop,
    decode,
    digest,
    effective_effort,
    effective_limits,
    verify,
)
from personal_ai.reasoning.policy import EFFORTS
from personal_ai.reasoning.proposed_request import Budget, ReasoningRequest
from personal_ai.services.chat.events import TurnCompleted
from personal_ai.services.chat.service import ChatTurnService
from personal_ai.storage import InMemoryConversationRepository, InMemoryMessageRepository

IDENTITY = ProviderIdentity("offline_fake", "offline_fake-v1", "pi3-local-json-bytes-v1")
ENDPOINT_DIGEST = digest(offline_profile(IDENTITY).model_dump(mode="json"))
SOURCE_DIGEST = digest({"sources": []})

FixtureText = Annotated[str, Field(min_length=1, max_length=OUTPUT_BYTES)]


class Fixture(ReasoningRecord):
    """Operator-owned scripted response data; only typed results may leave the adapter."""

    answer: FixtureText
    subanswers: tuple[FixtureText, ...] = Field(default=(), max_length=3)
    synthesis: FixtureText = '{"values":[]}'
    revision: FixtureText = '{"values":[]}'

    def response(self, step):
        if step.role == "subanswer":
            return self.subanswers[step.slot] if step.slot < len(self.subanswers) else '{"values":[]}'
        return getattr(self, step.role)


@dataclass(frozen=True, slots=True)
class ReasoningHost:
    context: ApplicationContextRequest
    ceilings: ScopeCeilings
    fixture: Fixture

    @property
    def fixture_digest(self):
        return digest(self.fixture.model_dump(mode="json"))

    def check(self, settings, scope):
        if (
            scope is not self.context.scope
            or settings.app_environment not in {"local", "test"}
            or settings.inference_profile != "offline_fake"
            or settings.inference_cost_mode != "offline_fake"
            or settings.max_response_tokens < OUTPUT_BYTES
            or settings.request_timeout_seconds * 1000 < STEP_MS
            or settings.max_context_tokens < INPUT_BYTES + OUTPUT_BYTES + settings.context_safety_margin_tokens
        ):
            raise Stop("policy_denied")
        authorize_base_disclosure(self.context)

    def check_plan(self, plan):
        if (
            plan.fixture_digest != self.fixture_digest
            or plan.endpoint_digest != ENDPOINT_DIGEST
            or effective_limits(self.ceilings, plan.limits) != plan.limits
            or EFFORTS.index(plan.effort) > EFFORTS.index(
                effective_effort(self.ceilings, plan.requested_effort)
            )
            or plan.selection == "trusted_direct_pin" and not self.ceilings.allow_direct_pin
        ):
            raise Stop("policy_denied")

    def continuation(self, run_id, plan, step, checkpoints):
        child_key = uuid5(run_id, step.name)
        requirements = plan.task.requirements
        if step.slot is not None:
            requirements = (requirements[step.slot],)
        body = {
            "operation": step.role,
            "requirements": [item.model_dump(mode="json") for item in requirements],
            "prior": [checkpoints[name].model_dump(mode="json") for name in step.dependencies],
            "response_schema": step.output_schema,
        }
        request = ContinuationRequest(
            idempotency_key=child_key,
            content=canonical_bytes(body).decode(),
            reasoning=ReasoningRequest(
                schema_version="reasoning-request-v1", effort="low",
                budget=Budget(
                    max_model_calls=1, max_concurrency=1,
                    max_elapsed_seconds=step.timeout_ms // 1000, max_input_tokens=step.input_bytes,
                    max_output_tokens=step.output_bytes,
                ),
            ),
        )
        return request, continuation_message_id(
            run_id, self.context.scope.owner_id, self.context.scope, child_key,
        )

    async def infer(self, run_id, step, settings, request, expected_message_id, attempt, guard, slots):
        # A fresh, isolated canonical continuation has no conversation, source or
        # memory history to inherit. Workflow receipts retain its canonical key.
        fixture_text = self.fixture.response(step)
        if len(fixture_text.encode()) > step.result_bytes:
            raise Stop("budget_exhausted")
        text, actual = await infer_fixture(
            run_id, self.context, settings, request, expected_message_id, attempt, guard,
            input_bytes=step.input_bytes, output_bytes=step.result_bytes, fixture_text=fixture_text,
        )
        return Checkpoint(step=step.name, values=decode(text, slots)), {**actual, "physical_attempts": 1}


async def infer_fixture(
    run_id, context, settings, request, expected_message_id, attempt, guard, *,
    input_bytes, output_bytes, fixture_text=None, selection=None, coordinator=None, revalidator=None,
):
    """Execute the same isolated canonical continuation for both fixture profiles."""
    settings = settings.model_copy(update={"reasoning_enabled": True})
    pair = compose_pair(settings, profile="offline_fake")
    attempt.require_endpoint(pair.generator.identity)
    if digest(pair.generator.delegate.endpoint_profile.model_dump(mode="json")) != ENDPOINT_DIGEST:
        raise Stop("policy_denied")
    if fixture_text is not None:
        pair.generator.delegate.deltas = (fixture_text,)
    conversations = InMemoryConversationRepository()
    scope = context.scope
    now = datetime.now(UTC)
    conversations.create(Conversation(
        id=run_id, owner_id=scope.owner_id, application_id=scope.application_id,
        workspace_id=scope.workspace_id, scope_version=2, title="Synthetic workflow", created_at=now, updated_at=now,
    ))
    chat = ChatTurnService(
        conversations, InMemoryMessageRepository(conversations), pair.generator,
        owner_id=scope.owner_id, application_context=context, model=IDENTITY.model_id,
        context_assembler=ContextAssembler(
            settings, pair.counter, context_provider_coordinator=coordinator,
            permission_revalidator=revalidator,
        ),
    )
    completed = None
    with bind_disclosure_guard(guard), bind_fixture_attempt(attempt):
        guard()
        async with aclosing(chat.continue_turn(run_id, request, _fixture_selection=selection)) as events:
            async for event in events:
                if isinstance(event, TurnCompleted):
                    completed = event
        guard()
    metadata = attempt.metadata
    if (
        completed is None or completed.reasoning is None
        or completed.reasoning.status != "complete"
        or completed.message.id != expected_message_id
        or completed.message.continuation_digest != request.intent_digest
        or metadata is None
        or metadata.usage is None or metadata.usage.confidence != "reported"
        or not 0 < metadata.usage.input_tokens <= input_bytes
        or metadata.usage.output_tokens != len(completed.message.content.encode())
        or metadata.usage.output_tokens > output_bytes
    ):
        raise Stop("provider_unavailable")
    return completed.message.content, {
        "input_bytes": metadata.usage.input_tokens,
        "output_bytes": metadata.usage.output_tokens,
    }


def run_check(step, plan, checkpoints):
    candidate = checkpoints[step.dependencies[0]]
    return verify(step, plan.task, candidate.values)


def supported(checkpoint):
    return tuple(
        (slot, value) for slot, value in enumerate(checkpoint.values) if slot not in checkpoint.defects
    )


def remaining_ms(deadline):
    return max(0, int((deadline - monotonic()) * 1000))
