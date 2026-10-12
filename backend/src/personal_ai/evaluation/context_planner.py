"""Synthetic Phase 13 planner baseline; no domain or model provider is contacted."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from math import ceil
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from pydantic import ConfigDict, create_model

from personal_ai.applications.contracts import (
    ApplicationContextPolicy,
    ApplicationContextRequest,
    ApplicationDefinition,
    CapabilityRegistration,
    ContextFieldPolicy,
    ContextOperationPolicy,
    ContextProviderPolicy,
)
from personal_ai.applications.registry import default_application_registry
from personal_ai.auth.scope import RequestScope, bind_request_scope, reset_request_scope
from personal_ai.context.adapters import (
    BuiltInContextPermissionRevalidator,
    MemoryContextProviderFactory,
)
from personal_ai.context.assembler import ContextAssembler
from personal_ai.context.authorization import authorize_context_selection
from personal_ai.context.contracts import TokenCount
from personal_ai.context.planner import ContextPlanner, ContextPlanningRule
from personal_ai.context.profile import (
    GlobalProfileContextProviderFactory,
    GlobalProfileFieldUpdate,
    GlobalProfileUpdate,
    InMemoryGlobalProfileRepository,
)
from personal_ai.context.providers import (
    ContextEntityReference,
    ContextItem,
    ContextOperationSpec,
    ContextPreparationError,
    ContextProviderCoordinator,
    ContextProviderSpec,
    ContextSelection,
    ContextSourceReference,
    StaticContextProviderFactory,
)
from personal_ai.entities import Message, MessageRole, MessageStatus
from personal_ai.evaluation.output import emit
from personal_ai.evaluation.planning_quality import assembled_context_digest
from personal_ai.memory.contracts import Memory, RetrievalResult, ScoredMemory, normalize
from personal_ai.settings import Settings

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "context" / "context-plan-fixtures.json"
NOW = datetime(2026, 10, 7, 12, tzinfo=UTC)


class _EnvelopeTokenCounter:
    """Conservative offline estimate that counts serialized source envelopes."""

    counter_version = "phase13-envelope-byte-estimate-v1"

    def count(self, messages):
        tokens = 10 + sum(ceil(len(message.content.encode("utf-8")) / 4) + 2 for message in messages)
        return TokenCount(tokens, "estimated")


class _FixtureProvider:
    def __init__(
        self,
        provider_id: str,
        source_class: str,
        operation: ContextOperationSpec,
        *,
        current_source_revision: str = "fixture-record-v1",
        partial_result: bool = False,
    ):
        self.spec = ContextProviderSpec(
            provider_id=provider_id,
            source_class=source_class,
            source_version="phase13-synthetic-v1",
            operations=(operation,),
            maximum_items_per_call=operation.maximum_results,
        )
        self.payload_type = create_model(
            f"{provider_id.replace('.', '_').title()}Payload",
            __config__=ConfigDict(extra="forbid", frozen=True),
            **{field: (str | None, None) for field in operation.allowed_fields},
        )
        self.calls: list[dict] = []
        self.current_source_revision = current_source_revision
        self.partial_result = partial_result

    def validate_selection(self, selection, inputs):
        del inputs
        if selection.provider_id != self.spec.provider_id:
            raise ValueError("fixture_provider_identity_mismatch")

    def fetch(self, selection, scope, *, deadline):
        del deadline
        self.calls.append(selection.model_dump(mode="json", exclude_none=True))
        payload = self.payload_type(
            **{field: f"synthetic {field}" for field in selection.fields}
        )
        return (
            ContextItem(
                source_class=self.spec.source_class,
                provider_id=self.spec.provider_id,
                source_id="synthetic-record-set",
                source_version=self.current_source_revision,
                item_id="fixture-item-1",
                owner_id=scope.owner_id,
                application_id=scope.application_id,
                workspace_id=scope.workspace_id,
                entity_refs=selection.entity_refs,
                authority=(
                    "external" if self.spec.source_class == "external_research" else "authoritative"
                ),
                observed_at=NOW,
                partial_result=self.partial_result,
                sensitivity=(
                    "personal" if self.spec.source_class == "external_research" else "sensitive"
                ),
                source_refs=(ContextSourceReference(kind="record", reference_id="fixture-item-1"),),
                payload=payload,
            ),
        )


class _RecordingProvider:
    def __init__(self, provider, calls):
        self.provider = provider
        self.spec = provider.spec
        self.calls = calls

    def validate_selection(self, selection, inputs):
        return self.provider.validate_selection(selection, inputs)

    def fetch(self, selection, scope, *, deadline):
        self.calls.append(_selection_summary(selection))
        return self.provider.fetch(selection, scope, deadline=deadline)


class _RecordingFactory:
    def __init__(self, factory):
        self.factory = factory
        self.spec = factory.spec
        self.calls = []

    def create(self, inputs):
        return _RecordingProvider(self.factory.create(inputs), self.calls)


def _builtin_memory(scope) -> Memory:
    source_message_id = uuid5(NAMESPACE_URL, "phase13-eval-memory-source-message")
    content = "I prefer an aisle seat when I travel."
    return Memory(
        id=uuid5(NAMESPACE_URL, "phase13-eval-memory"),
        owner_id=scope.owner_id,
        memory_type="preference",
        content=content,
        confidence=0.9,
        source_message_ids=(source_message_id,),
        rationale_code="user_preference",
        normalized_content=normalize(content),
        source_conversation_id=uuid5(NAMESPACE_URL, "phase13-eval-memory-conversation"),
        source_turn_id=uuid5(NAMESPACE_URL, "phase13-eval-memory-turn"),
        source_fingerprint=sha256(str(source_message_id).encode()).hexdigest(),
        observed_at=NOW,
        effective_at=NOW,
        created_at=NOW,
        embedding=(1.0, 0.0),
        embedding_model="phase13-offline-fixture",
        embedding_dimensions=2,
        application_id=scope.application_id,
        workspace_id=scope.workspace_id,
        scope_version=2,
    )


def _builtin_profile_repository(scope, shared_fields) -> InMemoryGlobalProfileRepository:
    values = {
        "preferred_units": "metric",
        "locale": "en-US",
        "response_style": "concise",
        "answer_length": "short",
    }
    repository = InMemoryGlobalProfileRepository(clock=lambda: NOW)
    repository.update(
        scope.owner_id,
        GlobalProfileUpdate(
            fields=tuple(
                GlobalProfileFieldUpdate(
                    field=field,
                    value=values[field],
                    shared_with_applications=("personal_ai",) if field in shared_fields else (),
                )
                for field in values
            )
        ),
    )
    return repository


def _rule(fixture: dict, provider_id: str, category: str | None = None):
    return ContextPlanningRule(
        rule_id=f"fixture.{fixture['name']}.{provider_id.replace('.', '-')}:v1",
        category=category or fixture["category"],
        phrases=(fixture["phrase"],),
        provider_id=provider_id,
        operation=fixture.get("operation", "current"),
        fields=tuple(fixture.get("rule_fields", ())),
        max_results=3,
        max_bytes=4_096,
        max_tokens=fixture.get("max_tokens", 96),
        timeout_seconds=1,
        window_seconds=fixture.get("window_seconds"),
        exclusive_group="domain" if fixture.get("ambiguous") else None,
        use_candidate_entities=fixture.get("use_candidate_entities", False),
        require_candidate_entities=fixture.get("require_candidate_entities", False),
        trigger_on_selected_entities=fixture.get("trigger_on_selected_entities", False),
        candidate_entity_types=tuple(fixture.get("candidate_entity_types", ())),
        application_ids=(fixture["application_id"],),
        explanation=f"Synthetic baseline for {fixture['name']}.",
    )


def _selection_summary(selection) -> dict:
    window_seconds = None
    if selection.window_start is not None:
        window_seconds = int((selection.window_end - selection.window_start).total_seconds())
    return {
        "provider_id": selection.provider_id,
        "operation": selection.operation,
        "fields": sorted(selection.fields),
        "max_results": selection.max_results,
        "max_bytes": selection.max_bytes,
        "max_tokens": selection.max_tokens,
        "timeout_seconds": selection.timeout_seconds,
        "window_seconds": window_seconds,
    }


def _call_summary(call: dict) -> dict:
    window_seconds = None
    if call.get("window_start") is not None:
        start = datetime.fromisoformat(call["window_start"])
        end = datetime.fromisoformat(call["window_end"])
        window_seconds = int((end - start).total_seconds())
    return {
        "provider_id": call["provider_id"],
        "operation": call["operation"],
        "fields": sorted(call.get("fields", ())),
        "max_results": call["max_results"],
        "max_bytes": call["max_bytes"],
        "max_tokens": call["max_tokens"],
        "timeout_seconds": call["timeout_seconds"],
        "window_seconds": window_seconds,
    }


def _item_fields(item) -> set[str]:
    payload = item.payload.model_dump(mode="json", exclude_none=True)
    if item.provider_id == "global_profile":
        return {payload["field"]} if payload.get("value") else set()
    if item.provider_id == "ai_memory":
        return {field for field in ("content", "memory_type", "effective_at") if payload.get(field)}
    return set(payload) - {"record_kind"}


def _policy_with_fixture_operations(
    base: ApplicationContextPolicy,
    operations: dict[str, ContextOperationPolicy],
) -> ApplicationContextPolicy:
    """Extend only the isolated evaluation manifest for undeclared fake providers."""
    providers = {provider.provider_id: provider for provider in base.provider_policies}
    for provider_id, operation in operations.items():
        current = providers.get(provider_id)
        if current is None:
            providers[provider_id] = ContextProviderPolicy(
                provider_id=provider_id,
                operations=(operation,),
            )
        else:
            providers[provider_id] = current.model_copy(
                update={"operations": (*current.operations, operation)}
            )
    return base.model_copy(update={"provider_policies": tuple(providers.values())})


def _run_fixture(fixture: dict, *, counter=None, configured_planner=None, planning_variant=None) -> dict:
    catalog_count = fixture.get("authorized_competing_candidate_count", 0)
    if catalog_count < 0 or catalog_count > ContextProviderCoordinator.MAX_SELECTIONS:
        raise ValueError("planning_fixture_authorized_catalog_size_invalid")
    provider_ids = (
        [f"catalog.candidate-{index:02d}" for index in range(catalog_count)]
        if catalog_count
        else fixture.get("provider_ids", [fixture.get("provider_id")])
    )
    scope = RequestScope(
        owner_id="synthetic-owner",
        request_id=f"evaluation-{fixture['name']}",
        application_id=fixture["application_id"],
        workspace_id=fixture.get("workspace_id", "synthetic-workspace"),
    )
    providers = []
    factories = {}
    capabilities = []
    rules = []
    synthetic_policy_operations: dict[str, ContextOperationPolicy] = {}
    retrieval = None
    profile_repository = None
    registry_definition = default_application_registry().get(fixture["application_id"])
    max_context_tokens = fixture.get("max_context_tokens", 2_048)
    available_context_tokens = max_context_tokens - 100 - 20
    settings = Settings(
        ai_provider="gemini",
        ai_model="synthetic-eval",
        max_context_tokens=max_context_tokens,
        max_response_tokens=100,
        context_safety_margin_tokens=20,
        summary_trigger_tokens=min(1_000, available_context_tokens),
        max_summary_tokens=min(512, available_context_tokens - 1),
        memory_enabled=True,
        memory_embedding_model="phase13-offline-fixture",
        memory_embedding_dimensions=2,
        memory_max_context_tokens=min(
            512, max(1, available_context_tokens)
        ),
        context_profile_max_tokens=min(512, available_context_tokens),
    )

    for provider_id in provider_ids:
        if fixture.get("use_default_rules") and provider_id in {"ai_memory", "global_profile"}:
            if provider_id == "ai_memory":
                recording_factory = _RecordingFactory(MemoryContextProviderFactory(settings))
                factories[provider_id] = recording_factory
                providers.append(recording_factory)
                retrieval = RetrievalResult(
                    selected=(ScoredMemory(_builtin_memory(scope), 0.95),)
                )
                capabilities.append(
                    CapabilityRegistration(
                        capability_id=provider_id,
                        kind="context_provider",
                        available=True,
                        feature_gate="memory_enabled",
                    )
                )
            elif provider_id == "global_profile":
                shared = fixture.get("shared_profile_fields", fixture["expected_fields"])
                profile_repository = _builtin_profile_repository(scope, set(shared))
                recording_factory = _RecordingFactory(
                    GlobalProfileContextProviderFactory(profile_repository)
                )
                factories[provider_id] = recording_factory
                providers.append(recording_factory)
                capabilities.append(
                    CapabilityRegistration(
                        capability_id=provider_id,
                        kind="context_provider",
                        available=True,
                    )
                )
            else:
                raise ValueError("phase13_builtin_fixture_provider_unsupported")
            continue

        if fixture.get("ambiguous"):
            source_class = "domain_history" if "health" in provider_id else "domain_current"
            fields = ("medication_name",) if "health" in provider_id else ("city",)
            operation = "history" if "health" in provider_id else "current"
            category = "health" if "health" in provider_id else "travel"
            fixture_rule = {
                **fixture,
                "category": category,
                "operation": operation,
                "phrase": "travel health records",
                "rule_fields": fields,
            }
        else:
            source_class = fixture["source_class"]
            fields = tuple(fixture["allowed_fields"])
            operation = fixture["operation"]
            category = fixture.get("category")
            fixture_rule = fixture
        operation_spec = ContextOperationSpec(
            operation=operation,
            allowed_fields=fields,
            accepts_entity_refs=fixture.get("use_candidate_entities", False),
            requires_time_window=(operation == "history"),
            maximum_window_seconds=fixture.get("max_window_seconds", 365 * 86_400),
            maximum_results=8,
            maximum_bytes=8_192,
            maximum_timeout_seconds=2,
        )
        if registry_definition.context_policy.operation(provider_id, operation) is None:
            synthetic_policy_operations[provider_id] = ContextOperationPolicy(
                operation=operation,
                fields=tuple(
                    ContextFieldPolicy(field=field, sensitivity="sensitive")
                    for field in fields
                ),
                sensitivity="sensitive",
            )
        if not fixture.get("provider_unavailable"):
            provider = _FixtureProvider(
                provider_id,
                source_class,
                operation_spec,
                current_source_revision=fixture.get("current_source_revision", "fixture-record-v1"),
                partial_result=fixture.get("source_partial", False),
            )
            providers.append(provider)
            factories[provider_id] = StaticContextProviderFactory(provider)
        capabilities.append(
            CapabilityRegistration(
                capability_id=provider_id,
                kind="context_provider",
                available=True,
            )
        )
        if fixture.get("ambiguous"):
            rules.append(_rule(fixture_rule, provider_id, category))
        else:
            rules.append(_rule(fixture_rule, provider_id))

    definition = ApplicationDefinition(
        application_id=fixture["application_id"],
        display_name=fixture["application_id"].title(),
        memory_namespace=fixture["application_id"],
        context_provider_ids=tuple(provider_ids),
        context_policy=_policy_with_fixture_operations(
            registry_definition.context_policy,
            synthetic_policy_operations,
        ),
    )
    context = ApplicationContextRequest(
        definition=definition,
        scope=scope,
        context_provider_capabilities=tuple(capabilities),
    )
    if catalog_count and configured_planner is not None:
        planner = ContextPlanner(
            (*configured_planner.rules, *rules),
            include_default_rules=False,
            max_total_tokens=configured_planner.max_total_tokens,
        )
    else:
        planner = configured_planner or ContextPlanner(
            rules or None, include_default_rules=fixture.get("use_default_rules", False)
        )
    coordinator = ContextProviderCoordinator(factories, feature_flags={"memory_enabled": True})
    authorized_candidate_ids = []
    if catalog_count:
        for provider_id in provider_ids:
            spec = factories[provider_id].spec
            operation_spec = spec.operation(fixture.get("operation", "current"))
            selection = ContextSelection(
                provider_id=provider_id,
                operation=fixture.get("operation", "current"),
                fields=tuple(fixture.get("rule_fields", ())),
                max_results=3,
                max_bytes=4_096,
                max_tokens=fixture.get("max_tokens", 256),
            )
            if operation_spec is None:
                continue
            try:
                authorize_context_selection(context, selection)
                coordinator.validate_operation_bounds(selection, spec, operation_spec)
                coordinator.authorize_boundaries((selection,), context.scope)
            except ContextPreparationError:
                continue
            authorized_candidate_ids.append(provider_id)
    assembler = ContextAssembler(
        settings,
        counter or _EnvelopeTokenCounter(),
        context_provider_coordinator=coordinator,
        context_planner=planner,
        permission_revalidator=BuiltInContextPermissionRevalidator(settings, profile_repository),
    )
    user = Message(
        id=uuid5(NAMESPACE_URL, f"{fixture['name']}:pending"),
        conversation_id=uuid5(NAMESPACE_URL, f"{fixture['name']}:conversation"),
        owner_id=scope.owner_id,
        application_id=scope.application_id,
        workspace_id=scope.workspace_id,
        scope_version=2,
        role=MessageRole.USER,
        content=fixture["intent"],
        status=MessageStatus.COMPLETED,
        created_at=NOW,
    )

    started = time.perf_counter()
    candidate_entities = tuple(
        ContextEntityReference(
            entity_type=item["entity_type"],
            entity_id=item["entity_id"],
            application_id=fixture["application_id"],
            workspace_id=scope.workspace_id,
        )
        for item in fixture.get("candidate_entities", ())
    )
    plan = assembler.plan_context(
        fixture["intent"], context, candidate_entities=candidate_entities, now=NOW
    )
    if planning_variant is not None:
        envelope = assembler.planning_envelope(plan, context, deadline=NOW + timedelta(seconds=1))
        proposal = planning_variant(envelope.request)
        plan = assembler.validate_context_proposal(envelope, proposal, context, now=NOW)
    planning_latency_ms = (time.perf_counter() - started) * 1000
    scope_token = bind_request_scope(scope)
    try:
        assembled = assembler.assemble(
            (), user, retrieval=retrieval, application_context=context,
            context_plan=plan, refresh=False,
        )
    finally:
        reset_request_scope(scope_token)
    latency_ms = (time.perf_counter() - started) * 1000

    selected_fields = sorted({field for selection in plan.selections for field in selection.fields})
    selected_entity_references = sorted(
        (reference.entity_type, reference.entity_id)
        for selection in plan.selections
        for reference in selection.entity_refs
    )
    expected_entity_references = sorted(
        (item["entity_type"], item["entity_id"])
        for item in fixture.get("expected_candidate_entities", ())
    )
    expected_fields = set(fixture["expected_fields"])
    excluded_fields = set(fixture["excluded_fields"])
    returned = list(assembled.source_items)
    response_bytes = sum(len(item.model_dump_json().encode("utf-8")) for item in returned)
    reasons = [decision.reason for decision in plan.decisions if decision.disposition == "omitted"]
    expected_reason = fixture.get("expected_omission_reason")
    planned_support = set().union(*(set(item.fields) for item in plan.selections)) if plan.selections else set()
    retrieved_support = set().union(*(_item_fields(item) for item in returned)) if returned else set()
    injected_keys = {
        (report.provider_id, report.item_id)
        for report in assembled.manifest.items
        if report.injected
    }
    injected_items = [
        item for item in returned if (item.provider_id, item.item_id) in injected_keys
    ]
    injected_support = set().union(*(_item_fields(item) for item in injected_items)) if injected_items else set()
    answer_needs = set(fixture["answer_support_needs"])
    expected_retrieved = set(fixture.get("expected_retrieved_fields", expected_fields))
    expected_injected = set(fixture.get("expected_injected_fields", expected_fields))
    actual_selections = sorted(
        (_selection_summary(item) for item in plan.selections),
        key=lambda item: (item["provider_id"], item["operation"]),
    )
    expected_selections = sorted(
        fixture.get("expected_selections", []),
        key=lambda item: (item["provider_id"], item["operation"]),
    )
    if catalog_count:
        selected_catalog_count = sum(
            item["provider_id"].startswith("catalog.candidate-") for item in actual_selections
        )
        minimum, maximum = fixture.get("expected_competing_selection_count", [1, 1])
        selections_match_expectation = minimum <= selected_catalog_count <= maximum
        catalog_authorized = (
            len(provider_ids) == catalog_count
            and len(capabilities) == catalog_count
            and len(authorized_candidate_ids) == catalog_count
            and all(item.spec.provider_id in factories for item in providers)
        )
    else:
        selected_catalog_count = 0
        selections_match_expectation = (
            "expected_selections" not in fixture or actual_selections == expected_selections
        )
        catalog_authorized = True
    revision_transition = fixture.get("source_revision_transition")
    returned_by_key = {(item.provider_id, item.item_id): item for item in returned}
    source_revision_observations = []
    for report in assembled.manifest.items:
        source_item = returned_by_key.get((report.provider_id, report.item_id))
        source_revision_observations.append({
            "provider_id": report.provider_id,
            "source_revision": report.source_version,
            "observation_complete": source_item is not None and not source_item.partial_result,
            "injected": report.injected,
            "omission_reason": report.omission_reason,
        })
    source_revision_matches = (
        revision_transition is None
        or bool(source_revision_observations) and all(
            observation["source_revision"] == revision_transition["expected_current_revision"]
            and observation["observation_complete"] is revision_transition["observation_complete"]
            for observation in source_revision_observations
        )
    )
    provider_calls = [call for provider in providers for call in provider.calls]
    normalized_calls = sorted(
        (_call_summary(item) for item in provider_calls),
        key=lambda item: (item["provider_id"], item["operation"]),
    )
    calls_match_plan = (
        len(normalized_calls) == len(actual_selections)
        and normalized_calls == actual_selections
    )
    metadata_valid = all(item.source_refs for item in returned) and all(
        item.permission_dependencies
        for item in returned
        if item.provider_id in {"ai_memory", "global_profile"}
    )
    expected_authority = fixture.get("expected_authority")
    authority_valid = expected_authority is None or all(
        item.authority == expected_authority for item in returned
    )
    source_report = assembled.manifest
    passed = (
        set(selected_fields) == expected_fields
        and not (set(selected_fields) & excluded_fields)
        and (expected_reason is None or expected_reason in reasons)
        and selections_match_expectation
        and catalog_authorized
        and source_revision_matches
        and selected_entity_references == expected_entity_references
        and calls_match_plan
        and retrieved_support == expected_retrieved
        and injected_support == expected_injected
        and answer_needs.issubset(injected_support)
        and metadata_valid
        and authority_valid
        and source_report is not None
        and assembled.budget.selected_total <= assembled.budget.input_budget
    )
    return {
        "fixture": fixture["name"],
        "fixture_version": 2,
        "result": "passed" if passed else "failed",
        "planner_version": plan.planner_version,
        "intent_categories": list(plan.intent_categories),
        "selected_provider_operations": [
            {"provider_id": item.provider_id, "operation": item.operation}
            for item in plan.selections
        ],
        "planned_selections": actual_selections,
        "authorized_competing_candidate_count": len(authorized_candidate_ids),
        "selected_competing_candidate_count": selected_catalog_count,
        "authorized_candidate_pattern": (
            [
                f"{provider_id}.{fixture.get('operation', 'current')}"
                for provider_id in authorized_candidate_ids
            ]
            if catalog_count
            else []
        ),
        "source_revision_transition": revision_transition,
        "source_revision_observations": source_revision_observations,
        "expected_selections": expected_selections,
        "selected_fields": selected_fields,
        "selected_entity_references": [
            {"entity_type": entity_type, "entity_id": entity_id}
            for entity_type, entity_id in selected_entity_references
        ],
        "retrieved_support_fields": sorted(retrieved_support),
        "expected_retrieved_fields": sorted(expected_retrieved),
        "injected_support_fields": sorted(injected_support),
        "expected_injected_fields": sorted(expected_injected),
        "expected_fields": sorted(expected_fields),
        "excluded_fields": sorted(excluded_fields),
        "unrelated_fields_requested": sorted(set(selected_fields) & excluded_fields),
        "overfetch_fields": sorted(set(selected_fields) - expected_fields),
        "omitted_expected_fields": sorted(expected_fields - set(selected_fields)),
        "answer_support_needs": sorted(answer_needs),
        "answer_support_needs_planned": answer_needs.issubset(planned_support),
        "answer_support_needs_injected": answer_needs.issubset(injected_support),
        "omission_reasons": reasons,
        "provider_calls": provider_calls,
        "provider_response_bytes": response_bytes,
        "source_item_authorities": sorted({item.authority for item in returned}),
        "source_reference_counts": [len(item.source_refs) for item in returned],
        "permission_dependency_counts": [len(item.permission_dependencies) for item in returned],
        "selected_source_count": len(plan.selections),
        "selected_item_count": len(injected_items),
        "assembled_bytes": sum(len(message.content.encode("utf-8")) for message in assembled.messages),
        "planner_configuration_digest": planner.configuration_digest,
        "assembled_context_digest": assembled_context_digest(assembled),
        "planning_trace": plan.planning_trace.model_dump(mode="json"),
        "effective_sensitivity": assembled.manifest.effective_sensitivity,
        "planning_latency_ms": round(planning_latency_ms, 3),
        "estimated_input_tokens": assembled.budget.selected_total,
        "planned_source_token_budgets": [
            {"source_class": source, "tokens": tokens}
            for source, tokens in plan.source_token_budgets
        ],
        "latency_ms": round(latency_ms, 3),
        "input_budget_tokens": assembled.budget.input_budget,
        "authorized_candidate_catalog_valid": catalog_authorized,
        "source_revision_transition_valid": source_revision_matches,
    }


def evaluate() -> list[dict]:
    fixtures = json.loads(FIXTURE_PATH.read_text())["fixtures"]
    return [_run_fixture(fixture) for fixture in fixtures]


def main() -> int:
    rows = evaluate()
    emit(rows)
    return 1 if any(row["result"] != "passed" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
