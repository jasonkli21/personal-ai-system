"""Shopping budget operation over the domain-owned command and receipt host."""

from datetime import timedelta

from pydantic import BaseModel, ConfigDict, Field

from personal_ai.contracts.delegated_tasks import (
    TARGET_CHOICES_CONTRACT_FINGERPRINT,
    TARGET_CONTRACT_FINGERPRINT,
    DelegatedTargetChoicesRequest,
    DelegatedTargetChoicesResult,
    DelegatedTargetRequest,
    DelegatedTaskResult,
)
from personal_ai.mutations.contracts import (
    AuthoritativePostState,
    DomainOutcome,
    DomainValidation,
    MutationCandidateNotApplicableError,
    MutationError,
)
from personal_ai.mutations.task_transport import task_for_proposal


class BudgetAllocation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    amount: str = Field(pattern=r"^(0|[1-9][0-9]{0,11})\.[0-9]{2}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class SharedContextNote(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    content: str = Field(min_length=1, max_length=1000)


class ShoppingTaskAdapter:
    """No domain SQL or copied validation rules; Shopping remains authoritative."""

    def __init__(self, client, declaration, payload_model, *, clock):
        self.client, self.clock = client, clock
        self.declaration, self.payload_model = declaration, payload_model

    def candidate_from_output(self, scope, message):
        raise MutationCandidateNotApplicableError()

    def authorize(self, scope, target, *, action):
        if target.application_id != "shopping" or target.workspace_id is not None:
            return False
        import json

        body = DelegatedTargetRequest(
            destination_application_id="shopping",
            workspace_id=None,
            target_entity_type=target.entity_type,
            target_entity_id=target.entity_id,
            permission_action="execute" if action == "confirm" else action,
        )
        try:
            raw = self.client.post(
                "/v1/integrations/personal-ai/tasks/target-authority",
                body.model_dump(mode="json"),
                maximum_bytes=4096,
                contract_fingerprint=TARGET_CONTRACT_FINGERPRINT,
            )
        except MutationError as error:
            if error.code == "task_domain_identity_denied":
                return False
            raise
        result = json.loads(raw)
        if (
            not isinstance(result, dict)
            or set(result) != {"allowed"}
            or type(result["allowed"]) is not bool
        ):
            raise ValueError("task_authority_response_invalid")
        return result["allowed"]

    def target_choices(self):
        """Ask Shopping for a minimal owner-scoped read-only picker response."""
        request = DelegatedTargetChoicesRequest()
        raw = self.client.post(
            "/v1/integrations/personal-ai/tasks/target-choices",
            request.model_dump(mode="json"),
            maximum_bytes=32_768,
            contract_fingerprint=TARGET_CHOICES_CONTRACT_FINGERPRINT,
        )
        result = DelegatedTargetChoicesResult.model_validate_json(raw)
        project_ids = [item.project_id for item in result.choices]
        if len(project_ids) != len(set(project_ids)):
            raise ValueError("task_target_choices_duplicate")
        return result

    def _send(self, proposal, action):
        task = task_for_proposal(proposal, action)
        result = DelegatedTaskResult.model_validate_json(
            self.client.post("/v1/integrations/personal-ai/tasks", task.model_dump(mode="json"))
        )
        if result.execution_key != task.execution_key or result.intent_digest != task.intent_digest:
            raise ValueError("task_result_binding_invalid")
        return result

    def validate(self, scope, proposal):
        result = self._send(proposal, "validate")
        if result.state not in {"validated", "rejected"}:
            raise ValueError("task_validation_result_invalid")
        if (
            result.state == "validated"
            and result.domain_version != proposal.intent.expected_domain_version
        ):
            raise ValueError("task_validation_domain_version_invalid")
        return DomainValidation(
            intent_digest=proposal.intent_digest(),
            validation_id=str(proposal.domain_operation_key),
            version="suite-task-result-v1",
            expected_domain_version=proposal.intent.expected_domain_version,
            valid=result.state == "validated",
            code=result.code,
            preview=result.preview,
            # Source/grant dependencies are already checked by the controller;
            # target permission is checked through authorize on every operation.
            permission_dependencies=tuple(
                dep for source in proposal.intent.sources for dep in source.permission_dependencies
            ),
            expires_at=min(proposal.intent.expires_at, self.clock() + timedelta(minutes=5)),
        )

    def _outcome(self, proposal, action):
        result = self._send(proposal, action)
        if result.state not in {"applied", "rejected", "uncertain"}:
            raise ValueError("task_effect_result_invalid")
        return DomainOutcome(
            domain_operation_key=proposal.domain_operation_key,
            state=result.state,
            code=result.code,
            post_state=AuthoritativePostState(
                target=proposal.intent.target,
                domain_version=result.domain_version,
                reference_id=result.reference_id,
            )
            if result.state == "applied"
            else None,
        )

    def execute(self, scope, proposal):
        return self._outcome(proposal, "execute")

    def reconcile(self, scope, proposal):
        return self._outcome(proposal, "reconcile")
