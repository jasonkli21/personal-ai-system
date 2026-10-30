"""Finance's versioned, restricted read projection through shared context seams."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from time import monotonic
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from personal_ai.auth.scope import (
    RequestScope,
    current_verified_user_identity_token,
)
from personal_ai.context.planner import ContextPlanningRule
from personal_ai.context.providers import (
    ContextEntityReference,
    ContextFieldSensitivity,
    ContextItem,
    ContextOperationSpec,
    ContextPermissionDependency,
    ContextPreparationError,
    ContextProviderError,
    ContextProviderInputs,
    ContextProviderSpec,
    ContextSelection,
    ContextSourceReference,
)
from personal_ai.context.runtime import ContextRuntimeContribution
from personal_ai.federation.broker import FederationExportResult
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    ValidationError,
    model_validator,
)

FINANCE_CONTEXT_PATH = "/v1/integrations/personal-ai/context"
FINANCE_CONTEXT_SCHEMA = "finance-context-read-v1"
FINANCE_ACCOUNT_PROVIDER_ID = "finance.account_context"
FINANCE_PORTFOLIO_PROVIDER_ID = "finance.portfolio_context"
FINANCE_RESEARCH_PROVIDER_ID = "finance.research_context"
FINANCE_EVIDENCE_PROVIDER_ID = "finance.research_evidence"
FINANCE_BUDGET_EXPORT_PROVIDER_ID = "federation.finance_budget_to_shopping"

FINANCE_ACCOUNT_FIELDS = ("account_summary", "balance_summary")
FINANCE_PORTFOLIO_FIELDS = (
    *FINANCE_ACCOUNT_FIELDS,
    "security_summary",
    "position_summary",
)
FINANCE_RESEARCH_FIELDS = ("research_thesis",)
FINANCE_EVIDENCE_FIELDS = ("research_fact",)


class FinanceContextEntityReference(BaseModel):
    """Finance wire identity contains no Personal AI owner or workspace authority."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    entity_type: Literal[
        "account",
        "security",
        "position",
        "issuer",
        "research_thesis",
        "research_fact",
        "portfolio",
        "discretionary_budget",
    ]
    entity_id: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def identifier_matches_entity(self) -> FinanceContextEntityReference:
        if self.entity_type == "portfolio":
            if self.entity_id != "all_active":
                raise ValueError("finance_context_portfolio_reference_invalid")
        else:
            try:
                UUID(self.entity_id)
            except (ValueError, TypeError, AttributeError) as error:
                raise ValueError("finance_context_entity_reference_invalid") from error
        return self


class FinanceContextReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["finance-context-read-v1"] = FINANCE_CONTEXT_SCHEMA
    application_id: Literal["finance"] = "finance"
    workspace_id: None = None
    operation: Literal["current", "verify"]
    purpose: Literal["personal_ai_context", "shopping_discretionary_budget"] = "personal_ai_context"
    destination_application_id: Literal["shopping"] | None = None
    entity_refs: tuple[FinanceContextEntityReference, ...] = Field(min_length=1, max_length=16)
    fields: tuple[str, ...] = Field(min_length=1, max_length=16)
    include_broader_context: bool = False
    max_results: int = Field(ge=1, le=32)
    max_bytes: int = Field(ge=512, le=32_768)

    @model_validator(mode="after")
    def enforce_scope_and_fields(self) -> FinanceContextReadRequest:
        available_fields = {
            *FINANCE_ACCOUNT_FIELDS,
            *FINANCE_PORTFOLIO_FIELDS,
            *FINANCE_RESEARCH_FIELDS,
            *FINANCE_EVIDENCE_FIELDS,
            "permission_version",
            "amount",
            "currency",
            "period",
        }
        if len(set(self.entity_refs)) != len(self.entity_refs):
            raise ValueError("finance_context_entity_references_not_unique")
        if len(set(self.fields)) != len(self.fields) or not set(self.fields) <= available_fields:
            raise ValueError("finance_context_fields_invalid")
        portfolio_refs = [
            reference for reference in self.entity_refs if reference.entity_type == "portfolio"
        ]
        budget_refs = [
            reference
            for reference in self.entity_refs
            if reference.entity_type == "discretionary_budget"
        ]
        budget_fields = {"amount", "currency", "period"}
        if budget_refs or set(self.fields) & budget_fields:
            expected_fields = (
                ("permission_version",)
                if self.operation == "verify"
                else ("amount", "currency", "period")
            )
            if (
                len(budget_refs) != 1
                or len(self.entity_refs) != 1
                or self.fields != expected_fields
                or self.purpose != "shopping_discretionary_budget"
                or self.destination_application_id != "shopping"
                or self.include_broader_context
            ):
                raise ValueError("finance_context_budget_export_scope_invalid")
        elif self.purpose != "personal_ai_context" or self.destination_application_id is not None:
            raise ValueError("finance_context_destination_scope_invalid")
        if self.include_broader_context != bool(portfolio_refs):
            raise ValueError("finance_context_broader_scope_requires_explicit_selection")
        if self.operation == "verify" and self.fields != ("permission_version",):
            raise ValueError("finance_context_verify_projection_invalid")
        if self.operation == "current" and "permission_version" in self.fields:
            raise ValueError("finance_context_permission_field_reserved")
        if self.operation == "verify":
            if self.include_broader_context or any(
                reference.entity_type == "portfolio" for reference in self.entity_refs
            ):
                raise ValueError("finance_context_verify_broad_scope_invalid")
        else:
            reference_types = {reference.entity_type for reference in self.entity_refs}
            if "portfolio" in reference_types:
                if reference_types != {"portfolio"} or set(self.fields) - {
                    "account_summary",
                    "balance_summary",
                    "security_summary",
                    "position_summary",
                }:
                    raise ValueError("finance_context_broad_scope_invalid")
            else:
                expected_types: set[str] = set()
                if set(self.fields) & budget_fields:
                    expected_types.add("discretionary_budget")
                if set(self.fields) & {"account_summary", "balance_summary"}:
                    expected_types.add("account")
                if "security_summary" in self.fields:
                    expected_types.add("security")
                if "position_summary" in self.fields:
                    expected_types.update({"account", "security"})
                if "research_thesis" in self.fields:
                    expected_types.add("issuer")
                if "research_fact" in self.fields:
                    expected_types.add("research_fact")
                if reference_types != expected_types:
                    raise ValueError("finance_context_selection_scope_invalid")
        return self


class FinanceContextSemanticValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    semantic_class: Literal["observed", "calculated", "assumed", "ai_interpreted"]
    value: JsonValue
    state: Literal["known", "unknown", "conflict"]
    unit: str | None = None
    currency: str | None = None
    as_of: str | None = None
    source_identity: str
    source_version: str
    evidence_refs: tuple[str, ...] = ()
    calculation_version: str | None = None
    quality: str
    uncertainty: str | None = None
    authority: Literal["authoritative", "user_asserted", "derived", "external", "unknown"]
    sensitivity: Literal["personal", "sensitive", "restricted"]


class FinanceContextRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    entity_type: Literal[
        "account",
        "security",
        "position",
        "research_thesis",
        "research_fact",
        "discretionary_budget",
    ]
    entity_id: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=200)
    source_version: str = Field(min_length=1, max_length=120)
    source_class: Literal["domain_current", "external_research"]
    authority: Literal["authoritative", "user_asserted", "derived", "external"]
    observed_at: datetime | None = None
    effective_at: datetime | date | None = None
    sensitivity: Literal["personal", "sensitive", "restricted"]
    payload: dict[str, dict[str, FinanceContextSemanticValue]] = Field(
        default_factory=dict, max_length=16
    )
    source_refs: tuple[ContextSourceReference, ...] = Field(min_length=1, max_length=8)
    permission_dependencies: tuple[ContextPermissionDependency, ...] = Field(
        min_length=1, max_length=8
    )
    field_sensitivity: tuple[ContextFieldSensitivity, ...] = Field(default=(), max_length=16)


class FinanceContextReadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["finance-context-read-v1"] = FINANCE_CONTEXT_SCHEMA
    application_id: Literal["finance"] = "finance"
    workspace_id: None = None
    items: tuple[FinanceContextRecord, ...] = Field(default=(), max_length=32)


class FinanceContextHTTPClient:
    """Bounded transport with separate service and current-user identities."""

    def __init__(
        self,
        *,
        base_url: str,
        auth_mode: str,
        service_audience: str = "",
        service_account: str = "",
        timeout_seconds: float = 3.0,
        service_token_fetcher: Callable[..., str] | None = None,
        transport: httpx.BaseTransport | None = None,
        delegated_client=None,
    ) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("finance_context_base_url_invalid")
        self.base_url = base_url.rstrip("/")
        self.auth_mode = auth_mode
        self.service_audience = service_audience
        self.service_account = service_account
        self.timeout_seconds = min(max(timeout_seconds, 0.1), 10.0)
        self.service_token_fetcher = service_token_fetcher
        self.transport = transport
        self.delegated_client = delegated_client

    def read(
        self, request: FinanceContextReadRequest, *, deadline: float
    ) -> FinanceContextReadResponse:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError
        user_token = current_verified_user_identity_token()
        if (
            not user_token
            and self.delegated_client is not None
            and request.purpose == "shopping_discretionary_budget"
            and request.destination_application_id == "shopping"
        ):
            try:
                raw = self.delegated_client.post(
                    FINANCE_CONTEXT_PATH,
                    request.model_dump(mode="json"),
                    maximum_bytes=request.max_bytes,
                    deadline=deadline,
                )
                result = FinanceContextReadResponse.model_validate_json(raw)
                if result.application_id != "finance" or result.workspace_id is not None:
                    raise ContextProviderError("finance_context_scope_invalid")
                return result
            except Exception as error:
                raise ContextProviderError("finance_context_unavailable") from error
        if not user_token or len(user_token) > 8192:
            raise ContextProviderError("finance_context_user_identity_unavailable")
        fetcher = self.service_token_fetcher
        if self.auth_mode != "google_oidc" or fetcher is None:
            raise ContextProviderError("finance_context_service_identity_unavailable")
        try:
            service_token = fetcher(
                audience=self.service_audience,
                service_account=self.service_account,
                deadline=deadline,
            )
        except Exception as error:
            raise ContextProviderError("finance_context_service_identity_unavailable") from error
        if not service_token or len(service_token) > 8192:
            raise ContextProviderError("finance_context_service_identity_unavailable")

        remaining = deadline - monotonic()
        if remaining <= 0:
            raise ContextProviderError("finance_context_unavailable")
        timeout = min(remaining, self.timeout_seconds)
        try:
            with (
                httpx.Client(
                    timeout=httpx.Timeout(timeout),
                    follow_redirects=False,
                    trust_env=False,
                    transport=self.transport,
                ) as client,
                client.stream(
                    "POST",
                    f"{self.base_url}{FINANCE_CONTEXT_PATH}",
                    json=request.model_dump(mode="json"),
                    headers={
                        "Authorization": f"Bearer {service_token}",
                        "X-User-ID-Token": user_token,
                    },
                ) as response,
            ):
                response.raise_for_status()
                encoded = bytearray()
                for chunk in response.iter_bytes(4096):
                    encoded.extend(chunk)
                    if len(encoded) > request.max_bytes:
                        raise ContextProviderError("finance_context_response_too_large")
                try:
                    result = FinanceContextReadResponse.model_validate_json(encoded)
                except (ValueError, TypeError, ValidationError, RecursionError):
                    raise ContextProviderError("finance_context_response_invalid") from None
        except ContextProviderError:
            raise
        except (httpx.HTTPError, OSError, TimeoutError) as error:
            raise ContextProviderError("finance_context_unavailable") from error
        if result.schema_version != FINANCE_CONTEXT_SCHEMA:
            raise ContextProviderError("finance_context_contract_unsupported")
        if result.application_id != "finance" or result.workspace_id is not None:
            raise ContextProviderError("finance_context_scope_invalid")
        return result


class FinanceContextProvider:
    """One registered Finance context capability with an exact field allowlist."""

    def __init__(self, client: FinanceContextHTTPClient, provider_id: str) -> None:
        self.client = client
        self.provider_id = provider_id
        provider_contracts = {
            FINANCE_ACCOUNT_PROVIDER_ID: (FINANCE_ACCOUNT_FIELDS, "domain_current"),
            FINANCE_PORTFOLIO_PROVIDER_ID: (FINANCE_PORTFOLIO_FIELDS, "domain_current"),
            FINANCE_RESEARCH_PROVIDER_ID: (FINANCE_RESEARCH_FIELDS, "domain_current"),
            FINANCE_EVIDENCE_PROVIDER_ID: (FINANCE_EVIDENCE_FIELDS, "external_research"),
        }
        try:
            self.allowed_fields, source_class = provider_contracts[provider_id]
        except KeyError as error:
            raise ValueError("finance_context_provider_unknown") from error
        self.spec = ContextProviderSpec(
            provider_id=provider_id,
            source_class=source_class,
            source_version=FINANCE_CONTEXT_SCHEMA,
            operations=(
                ContextOperationSpec(
                    operation="current",
                    allowed_fields=self.allowed_fields,
                    accepts_entity_refs=True,
                    maximum_results=32,
                    maximum_bytes=32_768,
                    maximum_timeout_seconds=5,
                ),
            ),
            maximum_items_per_call=32,
        )

    def validate_selection(
        self, selection: ContextSelection, inputs: ContextProviderInputs
    ) -> None:
        if inputs.scope.application_id != "finance" or inputs.scope.workspace_id is not None:
            raise ContextPreparationError("finance_context_application_scope_required")
        if not selection.entity_refs:
            raise ContextPreparationError("finance_context_entity_reference_required")
        if any(
            reference.application_id != "finance" or reference.workspace_id is not None
            for reference in selection.entity_refs
        ):
            raise ContextPreparationError("finance_context_entity_scope_invalid")
        if not set(selection.fields) <= set(self.allowed_fields):
            raise ContextPreparationError("finance_context_field_not_supported")
        if any(reference.entity_type == "portfolio" for reference in selection.entity_refs):
            if self.provider_id != FINANCE_PORTFOLIO_PROVIDER_ID:
                raise ContextPreparationError("finance_context_broad_scope_unsupported")
            if selection.entity_refs != tuple(
                reference
                for reference in selection.entity_refs
                if reference.entity_type == "portfolio"
            ):
                raise ContextPreparationError("finance_context_broad_scope_must_be_explicit")
            if not set(selection.fields) <= set(FINANCE_PORTFOLIO_FIELDS):
                raise ContextPreparationError("finance_context_broad_field_not_supported")
            return
        expected_types: set[str] = set()
        if self.provider_id == FINANCE_ACCOUNT_PROVIDER_ID:
            if set(selection.fields) & set(FINANCE_ACCOUNT_FIELDS):
                expected_types.add("account")
        elif self.provider_id == FINANCE_PORTFOLIO_PROVIDER_ID:
            if set(selection.fields) & set(FINANCE_ACCOUNT_FIELDS):
                raise ContextPreparationError(
                    "finance_context_account_expansion_requires_broad_scope"
                )
            if "security_summary" in selection.fields:
                expected_types.add("security")
            if "position_summary" in selection.fields:
                expected_types.update({"account", "security"})
        elif self.provider_id == FINANCE_RESEARCH_PROVIDER_ID:
            if "research_thesis" in selection.fields:
                expected_types.add("issuer")
        elif (
            self.provider_id == FINANCE_EVIDENCE_PROVIDER_ID and "research_fact" in selection.fields
        ):
            expected_types.add("research_fact")
        if {reference.entity_type for reference in selection.entity_refs} != expected_types:
            raise ContextPreparationError("finance_context_selection_scope_invalid")

    def fetch(
        self, selection: ContextSelection, scope: RequestScope, *, deadline: float
    ) -> tuple[ContextItem, ...]:
        broad = any(reference.entity_type == "portfolio" for reference in selection.entity_refs)
        response = self.client.read(
            FinanceContextReadRequest(
                operation="current",
                entity_refs=tuple(
                    FinanceContextEntityReference(
                        entity_type=reference.entity_type,
                        entity_id=reference.entity_id,
                    )
                    for reference in selection.entity_refs
                ),
                fields=selection.fields,
                include_broader_context=broad,
                max_results=selection.max_results,
                max_bytes=selection.max_bytes,
            ),
            deadline=deadline,
        )
        if len(response.items) > selection.max_results:
            raise ContextPreparationError("finance_context_result_limit_exceeded")
        requested_ids = {reference.entity_id for reference in selection.entity_refs}
        requested_types = {reference.entity_type for reference in selection.entity_refs}
        selected_account_ids = {
            reference.entity_id
            for reference in selection.entity_refs
            if reference.entity_type == "account"
        }
        selected_security_ids = {
            reference.entity_id
            for reference in selection.entity_refs
            if reference.entity_type == "security"
        }
        items: list[ContextItem] = []
        for record in response.items:
            if record.source_class != self.spec.source_class:
                raise ContextPreparationError("finance_context_source_class_mismatch")
            if not broad and record.entity_type not in requested_types:
                if record.entity_type == "position" and requested_types <= {
                    "account",
                    "security",
                }:
                    source_ids = {reference.reference_id for reference in record.source_refs}
                    if (
                        not selected_account_ids
                        or not selected_security_ids
                        or not (selected_account_ids & source_ids)
                        or not (selected_security_ids & source_ids)
                    ):
                        raise ContextPreparationError("finance_context_unselected_position")
                elif record.entity_type == "research_thesis" and requested_types == {"issuer"}:
                    source_ids = {reference.reference_id for reference in record.source_refs}
                    if not any(
                        reference.entity_id in source_ids for reference in selection.entity_refs
                    ):
                        raise ContextPreparationError("finance_context_unselected_research")
                else:
                    raise ContextPreparationError("finance_context_unselected_entity")
            elif not broad and record.entity_type == "research_thesis":
                source_ids = {reference.reference_id for reference in record.source_refs}
                if not any(
                    reference.entity_type == "issuer" and reference.entity_id in source_ids
                    for reference in selection.entity_refs
                ):
                    raise ContextPreparationError("finance_context_unselected_research")
            elif not broad and record.entity_id not in requested_ids:
                raise ContextPreparationError("finance_context_unselected_entity")
            payload_fields = set(record.payload)
            if payload_fields - set(selection.fields):
                raise ContextPreparationError("finance_context_projection_violation")
            payload = FinanceContextPayload.model_validate(record.payload)
            source_ids = {reference.reference_id for reference in record.source_refs}
            item_entity_refs = tuple(
                reference
                for reference in selection.entity_refs
                if reference.entity_id in source_ids
                or (reference.entity_type == "portfolio" and broad)
            )
            if not item_entity_refs:
                raise ContextPreparationError("finance_context_source_scope_missing")
            identity = f"{record.entity_type}\0{record.entity_id}"
            opaque = sha256(identity.encode()).hexdigest()
            observed_at = record.observed_at
            effective_at = (
                record.effective_at if isinstance(record.effective_at, datetime) else None
            )
            if observed_at is not None and observed_at.tzinfo is None:
                observed_at = observed_at.replace(tzinfo=UTC)
            if effective_at is not None and effective_at.tzinfo is None:
                effective_at = effective_at.replace(tzinfo=UTC)
            items.append(
                ContextItem(
                    source_class=record.source_class,
                    provider_id=self.provider_id,
                    source_id=f"finance:{sha256(record.source_id.encode()).hexdigest()}",
                    source_version=record.source_version,
                    item_id=f"finance:{record.entity_type}:{opaque[:32]}",
                    owner_id=scope.owner_id,
                    application_id="finance",
                    workspace_id=None,
                    entity_refs=item_entity_refs,
                    authority=record.authority,
                    observed_at=observed_at,
                    effective_at=effective_at,
                    sensitivity=record.sensitivity,
                    source_refs=record.source_refs,
                    permission_dependencies=record.permission_dependencies,
                    selected_operation="current",
                    field_sensitivity=record.field_sensitivity,
                    payload=payload,
                )
            )
        return tuple(items)


class FinanceContextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    account_summary: dict[str, FinanceContextSemanticValue] | None = None
    balance_summary: dict[str, FinanceContextSemanticValue] | None = None
    security_summary: dict[str, FinanceContextSemanticValue] | None = None
    position_summary: dict[str, FinanceContextSemanticValue] | None = None
    research_thesis: dict[str, FinanceContextSemanticValue] | None = None
    research_fact: dict[str, FinanceContextSemanticValue] | None = None


class FinanceContextProviderFactory:
    def __init__(self, client: FinanceContextHTTPClient, provider_id: str) -> None:
        self.client = client
        self.spec = FinanceContextProvider(client, provider_id).spec
        self.provider_id = provider_id

    def create(self, inputs: ContextProviderInputs) -> FinanceContextProvider:
        del inputs
        return FinanceContextProvider(self.client, self.provider_id)


class FinanceBudgetFederationAdapter:
    """Finance-owned monthly budget export through the narrow source contract."""

    purpose = "shopping_discretionary_budget"

    def __init__(self, client: FinanceContextHTTPClient) -> None:
        self.client = client

    @staticmethod
    def _single_budget(entities) -> ContextEntityReference:
        if (
            len(entities) != 1
            or entities[0].application_id != "finance"
            or entities[0].workspace_id is not None
            or entities[0].entity_type != "discretionary_budget"
        ):
            raise ContextPreparationError("finance_budget_export_scope_invalid")
        return entities[0]

    @staticmethod
    def _request(entity, *, operation: str, fields: tuple[str, ...]) -> FinanceContextReadRequest:
        return FinanceContextReadRequest(
            operation=operation,
            purpose=FinanceBudgetFederationAdapter.purpose,
            destination_application_id="shopping",
            entity_refs=(
                FinanceContextEntityReference(
                    entity_type="discretionary_budget", entity_id=entity.entity_id
                ),
            ),
            fields=fields,
            max_results=1,
            max_bytes=4096,
        )

    @staticmethod
    def _dependency(
        record,
        scope,
        entity,
        *,
        owner_id: str,
        acting_user_id: str,
    ) -> ContextPermissionDependency:
        expected_permission_id = f"finance_context_read:discretionary_budget:{entity.entity_id}"
        expected_source_id = f"finance:monthly_discretionary_budget:{entity.entity_id}"
        if (
            record.entity_type != "discretionary_budget"
            or record.entity_id != entity.entity_id
            or record.source_id != expected_source_id
            or len(record.permission_dependencies) != 1
            or len(record.source_refs) != 1
            or record.source_refs[0].kind != "record"
            or record.source_refs[0].reference_id != entity.entity_id
            or record.source_refs[0].fingerprint is None
        ):
            raise ContextPreparationError("finance_budget_export_policy_invalid")
        source_dependency = record.permission_dependencies[0]
        if (
            source_dependency.permission_id != expected_permission_id
            or source_dependency.purpose != FinanceBudgetFederationAdapter.purpose
            or source_dependency.version != record.source_version
        ):
            raise ContextPreparationError("finance_budget_export_policy_invalid")
        return ContextPermissionDependency(
            permission_id=source_dependency.permission_id,
            version=source_dependency.version,
            purpose=FinanceBudgetFederationAdapter.purpose,
            source_scope=scope,
            entity_ref=entity,
            source_revision=record.source_version,
            owner_id=owner_id,
            acting_user_id=acting_user_id,
        )

    def resolve_source_policy(self, intent, *, deadline: float) -> ContextPermissionDependency:
        if (
            intent.source.application_id != "finance"
            or intent.source.workspace_id is not None
            or intent.destination.application_id != "shopping"
            or intent.destination.workspace_id is not None
            or intent.category != "discretionary_budget"
            or intent.purpose != self.purpose
            or tuple(intent.fields) != ("amount", "currency", "period")
        ):
            raise ContextPreparationError("finance_budget_export_scope_invalid")
        entity = self._single_budget(intent.entities)
        response = self.client.read(
            self._request(entity, operation="verify", fields=("permission_version",)),
            deadline=deadline,
        )
        if len(response.items) != 1:
            raise ContextPreparationError("finance_budget_export_policy_unavailable")
        return self._dependency(
            response.items[0],
            intent.source,
            entity,
            owner_id=intent.owner_id,
            acting_user_id=intent.acting_user_id,
        )

    def authorize_export(self, grant, selection, scope, *, deadline: float) -> bool:
        if (
            grant.source.application_id != "finance"
            or grant.source.workspace_id is not None
            or grant.destination.application_id != "shopping"
            or grant.destination.workspace_id is not None
            or grant.category != "discretionary_budget"
            or grant.purpose != self.purpose
            or tuple(grant.fields) != ("amount", "currency", "period")
            or selection.fields != grant.fields
        ):
            return False
        entity = self._single_budget(selection.federation.entities)
        response = self.client.read(
            self._request(entity, operation="verify", fields=("permission_version",)),
            deadline=deadline,
        )
        return (
            len(response.items) == 1
            and self._dependency(
                response.items[0],
                grant.source,
                entity,
                owner_id=grant.owner_id,
                acting_user_id=grant.acting_user_id,
            )
            == grant.source_policy
            and scope.owner_id == grant.owner_id
            and scope.acting_user_id == grant.acting_user_id
        )

    def fetch(self, grant, selection, scope, *, deadline: float) -> FederationExportResult:
        if (
            grant.source.application_id != "finance"
            or grant.source.workspace_id is not None
            or grant.destination.application_id != "shopping"
            or grant.destination.workspace_id is not None
            or grant.category != "discretionary_budget"
            or grant.purpose != self.purpose
            or grant.fields != ("amount", "currency", "period")
            or selection.fields != grant.fields
            or scope.application_id != "shopping"
            or scope.workspace_id is not None
            or scope.owner_id != grant.owner_id
            or scope.acting_user_id != grant.acting_user_id
        ):
            raise ContextPreparationError("finance_budget_export_scope_invalid")
        entity = self._single_budget(selection.federation.entities)
        response = self.client.read(
            self._request(entity, operation="current", fields=selection.fields),
            deadline=deadline,
        )
        if len(response.items) != 1:
            raise ContextPreparationError("finance_budget_export_incomplete")
        record = response.items[0]
        try:
            if (
                set(record.payload) != {"discretionary_budget"}
                or {item.field for item in record.field_sensitivity}
                != {"amount", "currency", "period"}
                or len(record.field_sensitivity) != 3
            ):
                raise ContextPreparationError("finance_budget_export_contract_invalid")
            values = record.payload["discretionary_budget"]
            payload = FinanceBudgetExportPayload.model_validate(values)
            if any(
                value.source_version != record.source_version
                or entity.entity_id not in value.evidence_refs
                for value in (payload.amount, payload.currency, payload.period)
            ):
                raise ContextPreparationError("finance_budget_export_contract_invalid")
            source_dependency = self._dependency(
                record,
                grant.source,
                entity,
                owner_id=grant.owner_id,
                acting_user_id=grant.acting_user_id,
            )
            source_refs = tuple(
                ContextSourceReference(
                    kind=reference.kind,
                    reference_id=reference.reference_id,
                    fingerprint=reference.fingerprint,
                )
                for reference in record.source_refs
            )
            field_sensitivity = tuple(
                ContextFieldSensitivity(field=field.field, sensitivity=field.sensitivity)
                for field in record.field_sensitivity
            )
        except (KeyError, ValueError, TypeError) as error:
            raise ContextPreparationError("finance_budget_export_contract_invalid") from error
        item = ContextItem(
            source_class="domain_current",
            provider_id=FINANCE_BUDGET_EXPORT_PROVIDER_ID,
            source_id=record.source_id,
            source_version=record.source_version,
            item_id=f"finance-budget:{sha256(record.entity_id.encode()).hexdigest()[:32]}",
            owner_id=scope.owner_id,
            application_id="finance",
            workspace_id=None,
            entity_refs=(entity,),
            authority="user_asserted",
            observed_at=record.observed_at,
            # A calendar month/day remains exact in semantic as_of/period fields;
            # it cannot establish a timezone-aware effective instant.
            effective_at=(
                record.effective_at if isinstance(record.effective_at, datetime) else None
            ),
            expires_at=min(grant.expires_at, datetime.now(UTC) + timedelta(minutes=5)),
            sensitivity="restricted",
            source_refs=source_refs,
            permission_dependencies=(source_dependency,),
            selected_operation="entity",
            field_sensitivity=field_sensitivity,
            payload=payload,
        )
        return FederationExportResult(items=(item,), complete=True)


class FinanceBudgetExportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    amount: FinanceContextSemanticValue
    currency: FinanceContextSemanticValue
    period: FinanceContextSemanticValue


class FinanceContextPermissionRevalidator:
    """Ask Finance to recheck selected records before context reuse."""

    permission_prefix = "finance_context_read:"
    permission_namespaces = (permission_prefix,)

    def __init__(self, client: FinanceContextHTTPClient) -> None:
        self.client = client

    def supports(self, dependency: ContextPermissionDependency) -> bool:
        return dependency.permission_id.startswith(self.permission_prefix)

    def is_current(self, dependency: ContextPermissionDependency) -> bool:
        if not self.supports(dependency):
            return False
        try:
            _, entity_type, entity_id = dependency.permission_id.split(":", 2)
            reference = ContextEntityReference(
                entity_type=entity_type,
                entity_id=entity_id,
                application_id="finance",
                workspace_id=None,
            )
            response = self.client.read(
                FinanceContextReadRequest(
                    operation="verify",
                    purpose=(
                        "shopping_discretionary_budget"
                        if entity_type == "discretionary_budget"
                        else "personal_ai_context"
                    ),
                    destination_application_id=(
                        "shopping" if entity_type == "discretionary_budget" else None
                    ),
                    entity_refs=(
                        FinanceContextEntityReference(
                            entity_type=reference.entity_type,
                            entity_id=reference.entity_id,
                        ),
                    ),
                    fields=("permission_version",),
                    max_results=1,
                    max_bytes=4096,
                ),
                deadline=monotonic() + 0.75,
            )
        except Exception:  # noqa: BLE001 - current owner authority fails closed
            return False
        return any(record.source_version == dependency.version for record in response.items)


def finance_context_planning_rules() -> tuple[ContextPlanningRule, ...]:
    """Rules require host-selected Finance entities; broad scope is separately explicit."""
    return (
        ContextPlanningRule(
            rule_id="finance.selected-account:v1",
            category="finance_selected_account",
            phrases=("this finance account", "selected account context"),
            provider_id=FINANCE_ACCOUNT_PROVIDER_ID,
            operation="current",
            fields=FINANCE_ACCOUNT_FIELDS,
            max_results=4,
            max_bytes=12_288,
            max_tokens=512,
            timeout_seconds=3,
            use_candidate_entities=True,
            require_candidate_entities=True,
            trigger_on_selected_entities=True,
            candidate_entity_types=("account",),
            required=True,
            priority=20,
            application_ids=("finance",),
            explanation="Read only the Finance account explicitly selected by the host.",
        ),
        ContextPlanningRule(
            rule_id="finance.selected-security:v1",
            category="finance_selected_security",
            phrases=("this security", "selected security context"),
            provider_id=FINANCE_PORTFOLIO_PROVIDER_ID,
            operation="current",
            fields=("security_summary",),
            max_results=4,
            max_bytes=12_288,
            max_tokens=512,
            timeout_seconds=3,
            use_candidate_entities=True,
            require_candidate_entities=True,
            trigger_on_selected_entities=True,
            candidate_entity_types=("security",),
            required=True,
            priority=22,
            application_ids=("finance",),
            explanation="Read only the Finance security explicitly selected by the host.",
        ),
        ContextPlanningRule(
            rule_id="finance.selected-position:v1",
            category="finance_selected_position",
            phrases=("this position", "my position in this account"),
            provider_id=FINANCE_PORTFOLIO_PROVIDER_ID,
            operation="current",
            fields=("position_summary",),
            max_results=8,
            max_bytes=16_384,
            max_tokens=768,
            timeout_seconds=3,
            use_candidate_entities=True,
            require_candidate_entities=True,
            # A position is a relationship; one selected account or security
            # alone is not enough to trigger a read.
            trigger_on_selected_entities=False,
            candidate_entity_types=("account", "security"),
            required=True,
            priority=24,
            application_ids=("finance",),
            explanation="Read only the selected account/security position pair.",
        ),
        ContextPlanningRule(
            rule_id="finance.explicit-broader-portfolio:v1",
            category="finance_explicit_broader_portfolio",
            phrases=("include my whole portfolio", "include broader portfolio context"),
            provider_id=FINANCE_PORTFOLIO_PROVIDER_ID,
            operation="current",
            fields=("position_summary",),
            max_results=32,
            max_bytes=24_576,
            max_tokens=1024,
            timeout_seconds=3,
            use_candidate_entities=True,
            require_candidate_entities=True,
            trigger_on_selected_entities=True,
            candidate_entity_types=("portfolio",),
            priority=60,
            application_ids=("finance",),
            explanation="Read broader Finance positions only after the host selects the whole-portfolio scope.",
        ),
        ContextPlanningRule(
            rule_id="finance.selected-thesis:v1",
            category="finance_selected_thesis",
            phrases=("selected finance thesis", "this thesis note"),
            provider_id=FINANCE_RESEARCH_PROVIDER_ID,
            operation="current",
            fields=FINANCE_RESEARCH_FIELDS,
            max_results=4,
            max_bytes=16_384,
            max_tokens=768,
            timeout_seconds=3,
            use_candidate_entities=True,
            require_candidate_entities=True,
            trigger_on_selected_entities=True,
            candidate_entity_types=("issuer",),
            priority=32,
            application_ids=("finance",),
            explanation="Read only the thesis note for a host-selected Finance issuer.",
        ),
        ContextPlanningRule(
            rule_id="finance.selected-research-evidence:v1",
            category="finance_selected_research_evidence",
            phrases=("selected finance research", "this research fact"),
            provider_id=FINANCE_EVIDENCE_PROVIDER_ID,
            operation="current",
            fields=FINANCE_EVIDENCE_FIELDS,
            max_results=4,
            max_bytes=16_384,
            max_tokens=768,
            timeout_seconds=3,
            use_candidate_entities=True,
            require_candidate_entities=True,
            trigger_on_selected_entities=True,
            candidate_entity_types=("research_fact",),
            priority=33,
            application_ids=("finance",),
            explanation="Read only the registered evidence fact selected by the Finance host.",
        ),
    )


def configured_finance_context_contribution(settings) -> ContextRuntimeContribution:
    """Install the Finance adapter only behind independent auth and data-use gates."""
    if not settings.finance_context_enabled:
        return ContextRuntimeContribution(provider_factories={})
    from personal_ai.auth.service_tokens import fetch_google_service_token
    from personal_ai.mutations.deployment import domain_client

    client = FinanceContextHTTPClient(
        base_url=str(settings.finance_context_base_url),
        auth_mode=settings.auth_mode,
        service_audience=settings.finance_context_service_audience,
        service_account=settings.finance_context_service_account,
        timeout_seconds=settings.finance_context_timeout_seconds,
        service_token_fetcher=fetch_google_service_token,
        delegated_client=(
            domain_client(
                settings,
                str(settings.finance_context_base_url),
                settings.finance_context_service_audience,
            )
            if settings.task_delegation_enabled and settings.task_domain_service_account
            else None
        ),
    )
    return ContextRuntimeContribution(
        provider_factories={
            FINANCE_ACCOUNT_PROVIDER_ID: FinanceContextProviderFactory(
                client, FINANCE_ACCOUNT_PROVIDER_ID
            ),
            FINANCE_PORTFOLIO_PROVIDER_ID: FinanceContextProviderFactory(
                client, FINANCE_PORTFOLIO_PROVIDER_ID
            ),
            FINANCE_RESEARCH_PROVIDER_ID: FinanceContextProviderFactory(
                client, FINANCE_RESEARCH_PROVIDER_ID
            ),
            FINANCE_EVIDENCE_PROVIDER_ID: FinanceContextProviderFactory(
                client, FINANCE_EVIDENCE_PROVIDER_ID
            ),
        },
        export_adapters={
            FINANCE_BUDGET_EXPORT_PROVIDER_ID: FinanceBudgetFederationAdapter(client),
        },
        planning_rules=finance_context_planning_rules(),
        permission_revalidators=(FinanceContextPermissionRevalidator(client),),
    )
