"""Synthetic physical transport over PAS strict-free routing and attempt accounting."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from time import monotonic

from personal_ai.auth.scope import ApplicationScope, current_request_scope
from personal_ai.context.providers import ContextPreparationError
from personal_ai.llm.client import GenerationEvent, GenerationMetadata, ProviderIdentity
from personal_ai.llm.disclosure import (
    current_disclosure_source_references,
    revalidate_disclosure,
)
from personal_ai.routing import AuthorizationEvidence, EndpointRegistry, PreparationIdentity
from personal_ai.routing.contracts import DataUsePolicy, EndpointCandidateRequirements
from personal_ai.routing.decision_models import RoutingRequestFacts, RoutingTaskProfile
from personal_ai.routing.owner_policy import read_policy
from personal_ai.routing.registry import EndpointRegistryError
from personal_ai.routing.service import RoutingDecisionService, RoutingFinalizationError
from personal_ai.storage.async_io import sync_call
from personal_ai.usage.context import current_usage_context
from personal_ai.usage.contracts import AttemptResult
from tests.test_endpoint_registry import _profile
from tests.test_routing_decision_lifecycle import MemoryRepository, Usage

from .shared import RECIPIENT, hold_worker_slot
from .wire import encode

OPERATION = "bounded_generation"
ANSWER = "Synthetic application answer."
NO_AI = "context_no_ai_route"


def free_profile():
    return _profile(
        RECIPIENT,
        provider_id="synthetic",
        model_id="fixture-model",
        data_use_policy=DataUsePolicy(
            status="approved",
            max_sensitivity="sensitive",
            policy_reference="synthetic-recipient",
        ),
    )


class RecipientAuthority:
    def __init__(self, profile, *, recovery_current=lambda: True, owner_policy=None):
        self.profile = profile
        self.recovery_current = recovery_current
        self.owner_policy = owner_policy or (lambda connection, owner_id: None)
        self.enabled = True

    def authorize(
        self,
        *,
        connection,
        owner_id,
        scope,
        endpoint,
        requirements,
        policy_version,
        source_references,
        now,
    ):
        current = current_request_scope()
        policy, diagnostic = read_policy(self.owner_policy(connection, owner_id))
        if (
            not self.enabled
            or not self.recovery_current()
            or diagnostic
            or not current
            or owner_id != current.owner_id
            or (scope.application_id, scope.workspace_id)
            != (current.application_id, current.workspace_id)
            or endpoint != self.profile.ref
            or "free_api" not in policy.routes
            or requirements.execution_mode != "STRICT_FREE"
            or tuple(source_references) != current_disclosure_source_references()
        ):
            raise ContextPreparationError(NO_AI)
        revalidate_disclosure()
        return AuthorizationEvidence(
            reference="synthetic-recipient:v1",
            checked_at=now,
            valid_until=now + timedelta(seconds=2),
        )


class RoutedGeneration:
    """No credentials, discovery, auxiliary calls, or paid/plan composition."""

    requires_inference_context = False

    def __init__(self, counter, *, routing=None, authority=None, profile=None):
        self.profile = profile or free_profile()
        self.counter = counter
        self.authority = authority or RecipientAuthority(self.profile)
        if routing is None:
            # The existing fake uses a fixed clock for deterministic routing tests.
            class ClockedRepository(MemoryRepository):
                def current_time(self, connection):
                    self.now = datetime.now(UTC)
                    return self.now

            repository = ClockedRepository()
            routing = RoutingDecisionService(
                EndpointRegistry((self.profile,)),
                repository,
                usage=Usage(repository),
                authorization=self.authority,
            )
        self.routing = routing
        self.identity = ProviderIdentity(
            self.profile.provider_id,
            self.profile.model_id,
            self.profile.serializer_id,
        )
        self.sends = []
        self.transport = lambda _: (ANSWER, "success")
        self.before_make_claim = lambda **_: None
        self.after_commit = lambda: None
        self.rejected = 0

    def _execute(self, messages, output, timeout, inference):
        with hold_worker_slot():
            return self._dispatch(messages, output, timeout, inference)

    def _dispatch(self, messages, output, timeout, inference):
        current = current_request_scope()
        invocation_context = current_usage_context()
        if current is None or invocation_context is None or inference is None:
            raise ContextPreparationError(NO_AI)
        references = current_disclosure_source_references()
        scope = ApplicationScope(
            application_id=current.application_id, workspace_id=current.workspace_id
        )
        payload = encode(
            [{"role": message.role, "content": message.content} for message in messages]
        )
        counted = self.counter.count(messages).tokens
        owner_scope = {"owner_id": current.owner_id, "scope": scope}
        deadline = monotonic() + timeout
        request = RoutingRequestFacts(
            request_id=invocation_context.request_id,
            operation=OPERATION,
            requirements=EndpointCandidateRequirements(
                required_capabilities={OPERATION},
                execution_mode="STRICT_FREE",
                automatic=True,
                sensitivity=inference.effective_sensitivity,
                input_tokens=counted,
                output_tokens=output,
            ),
            policy_version=inference.policy_version,
            source_reference_sha256s=references,
        )
        task = RoutingTaskProfile(
            task_id="shared-chat",
            profile_id="shared-chat:v1",
            profile_version=1,
            task_type="chat",
            required_capabilities={OPERATION},
            deadline_ms=max(1, int(timeout * 1000)),
        )
        try:
            decision = self.routing.route(**owner_scope, task=task, request=request)
            if decision.selected != self.profile.ref:
                raise ContextPreparationError(NO_AI)
            digest = sha256(payload).hexdigest()
            permit = self.routing.finalize(
                **owner_scope,
                decision_id=decision.routing_decision_id,
                operation=OPERATION,
                preparation=PreparationIdentity(
                    endpoint=decision.selected,
                    serializer_id=self.profile.serializer_id,
                    input_tokens=counted,
                    count_source="fixture-estimate",
                    count_confidence="estimated",
                    prepared_input_sha256=digest,
                    source_reference_sha256s=references,
                    prepared_at=self.routing.current_time(owner_id=current.owner_id),
                ),
            )

            def send(profile, invocation, attempt):
                self.after_commit()
                # Claim already committed. A denial here leaves conservative
                # accounting; a source-side change after this check cannot recall bytes.
                with self.routing.observations.transaction(owner_id=current.owner_id) as connection:
                    now = self.routing.observations.current_time(connection)
                    self.routing.registry.revalidate_selected(
                        profile.ref,
                        request.requirements,
                        now=now,
                        connection=connection,
                    )
                    self.authority.authorize(
                        connection=connection,
                        owner_id=current.owner_id,
                        scope=scope,
                        endpoint=profile.ref,
                        requirements=request.requirements,
                        policy_version=request.policy_version,
                        source_references=references,
                        now=now,
                    )
                if (
                    monotonic() >= deadline
                    or not self.authority.recovery_current()
                    or profile.ref != self.profile.ref
                    or sha256(payload).hexdigest() != digest
                ):
                    raise ContextPreparationError(NO_AI)
                self.sends.append((RECIPIENT, invocation, attempt, payload))
                text, outcome = self.transport(payload)
                return (text, outcome), AttemptResult(
                    outcome=outcome,
                    completed_at=datetime.now(UTC),
                    latency_ms=0,
                )

            self.before_make_claim(**owner_scope, permit=permit)
            return self.routing.dispatch(
                **owner_scope, permit=permit, operation=OPERATION, send=send
            )
        except (ContextPreparationError, EndpointRegistryError, RoutingFinalizationError):
            self.rejected += 1
            raise ContextPreparationError(NO_AI) from None

    async def stream_events(
        self, messages, *, max_output_tokens, timeout_seconds, inference_context
    ):
        text, outcome = await sync_call(
            self._execute,
            messages,
            max_output_tokens,
            timeout_seconds,
            inference_context,
        )
        if text:
            yield GenerationEvent.text_delta(text)
        if outcome == "success":
            yield GenerationEvent.terminal(
                GenerationMetadata(status="success", identity=self.identity)
            )
