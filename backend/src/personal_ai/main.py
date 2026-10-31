"""FastAPI application entry point and Cloud Run health endpoints."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from personal_ai.agents.research.contracts import ResearchError
from personal_ai.api.account import router as account_router
from personal_ai.api.artifacts import router as artifacts_router
from personal_ai.api.decisions import router as decisions_router
from personal_ai.api.external_turns import router as external_turns_router
from personal_ai.api.federation import router as federation_router
from personal_ai.api.iterative_research import router as iterative_research_router
from personal_ai.api.memory_control import router as memory_control_router
from personal_ai.api.mutations import router as mutations_router
from personal_ai.api.profile import router as profile_router
from personal_ai.api.provider_usage import router as provider_usage_router
from personal_ai.api.research import router as research_router
from personal_ai.api.routes import router as conversations_router
from personal_ai.applications.http import attach_contribution_routes
from personal_ai.applications.registry import (
    ApplicationContributionCatalog,
    default_application_registry,
)
from personal_ai.auth.account_data import AccountDataUnavailable
from personal_ai.auth.middleware import AuthenticationMiddleware
from personal_ai.context import ContextError
from personal_ai.context.deployment import configured_context_runtime
from personal_ai.context.providers import ContextPreparationError
from personal_ai.decisions.repositories import DecisionError
from personal_ai.llm.errors import LLMError
from personal_ai.persistence.factory import close_persistence_clients
from personal_ai.services import ExternalHistoryDisclosureDenied, InvalidRetryTargetError
from personal_ai.settings import (
    ContextBudgetInvalidError,
    get_settings,
    validate_startup_configuration,
)
from personal_ai.storage import ConversationConflictError, ResourceNotFoundError, StorageError


@asynccontextmanager
async def lifespan(application: FastAPI):
    validate_startup_configuration()
    try:
        settings_provider = application.dependency_overrides.get(get_settings, get_settings)
        if getattr(application.state, "selection_from_environment", False):
            configured_names = tuple(sorted(settings_provider().application_contributions))
            if configured_names != application.state.contribution_selection:
                raise ValueError("contribution_selection_requires_process_environment")
        contribution_catalog = getattr(application.state, "context_runtime_catalog", None)
        application.state.context_runtime_registry = configured_context_runtime(
            settings_provider(), catalog=contribution_catalog
        )
        from personal_ai.federation.deployment import reconcile_federation_runtime_metadata

        application.state.application_registry = reconcile_federation_runtime_metadata(
            application.state.application_registry, application.state.context_runtime_registry
        )
        from personal_ai.mutations.deployment import install_task_metadata

        application.state.application_registry = install_task_metadata(
            application.state.application_registry,
            settings_provider(),
            application.state.context_runtime_registry,
        )
        # Old confirmation/effect bindings remain inspectable until their owning
        # proposal metadata is purged. Refuse a deployment that drops their resolver.
        from personal_ai.mutations.compatibility import require_reconciliation_compatibility
        from personal_ai.persistence.factory import persistence_factory

        mutation_repository = persistence_factory(settings_provider()).mutation_repository()
        require_reconciliation_compatibility(
            mutation_repository, application.state.context_runtime_registry
        )
        yield
    finally:
        close_persistence_clients()


def create_app(
    *,
    application_catalog: ApplicationContributionCatalog | None = None,
    context_runtime_catalog=None,
    selected_contributions=None,
) -> FastAPI:
    """Build the production API with registered application and context contributions."""
    from personal_ai.applications.selection import selected_contribution_names, validate_selection

    selection_from_environment = (
        selected_contributions is None
        and application_catalog is None
        and context_runtime_catalog is None
    )
    names = (
        selected_contribution_names()
        if selected_contributions is None
        else validate_selection(selected_contributions)
    )
    if application_catalog is None:
        application_catalog = ApplicationContributionCatalog.from_entry_points(selected=names)
    if context_runtime_catalog is None:
        from personal_ai.context.deployment import default_context_runtime_catalog

        context_runtime_catalog = default_context_runtime_catalog(names)
    application = FastAPI(title="Personal AI System", version="0.1.0", lifespan=lifespan)
    application.state.selection_from_environment = selection_from_environment
    application.state.contribution_selection = names
    application.state.application_registry = default_application_registry(
        contribution_catalog=application_catalog
    )
    if context_runtime_catalog is not None:
        application.state.context_runtime_catalog = context_runtime_catalog
    application.add_middleware(AuthenticationMiddleware)
    for router in (
        federation_router,
        mutations_router,
        memory_control_router,
        external_turns_router,
        conversations_router,
        research_router,
        iterative_research_router,
        decisions_router,
        account_router,
        artifacts_router,
        profile_router,
        provider_usage_router,
    ):
        application.include_router(router)
    application.add_api_route("/health", health, methods=["GET"])
    for error_type, handler in CORE_EXCEPTION_HANDLERS:
        application.add_exception_handler(error_type, handler)
    attach_contribution_routes(application, application_catalog.contributions())
    return application


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Return the common safe JSON error envelope."""
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


async def request_validation_error(_: Request, __: RequestValidationError) -> JSONResponse:
    """Avoid exposing framework validation internals to API clients."""
    return _error_response(422, "validation_error", "Request validation failed.")


async def http_exception(_: Request, error: HTTPException) -> JSONResponse:
    code = error.detail if isinstance(error.detail, str) else "request_rejected"
    message = {
        "authentication_required": "Sign in to continue.",
        "reauthentication_required": "Sign in again before this account action.",
        "feature_disabled": "This account action is not available.",
        "profile_update_conflict": "The profile changed while this update was being saved. Please retry.",
    }.get(code, "The request could not be completed.")
    headers = error.headers or {}
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": code, "message": message}},
        headers=headers,
    )


async def resource_not_found(_: Request, __: ResourceNotFoundError) -> JSONResponse:
    """Map missing or foreign owner-scoped records to a safe 404."""
    return _error_response(404, "not_found", "The requested resource was not found.")


async def conversation_conflict(_: Request, error: ConversationConflictError) -> JSONResponse:
    """Report concurrent conversation mutations without exposing store details."""
    if str(error) == "idempotency_input_changed":
        return _error_response(
            409,
            "conversation_conflict",
            "The idempotency key was already used for different conversation input.",
        )
    return _error_response(
        409, "conversation_busy", "A response is already in progress. Please retry."
    )


async def storage_error(_: Request, __: StorageError) -> JSONResponse:
    """Map storage failures without disclosing provider-specific details."""
    return _error_response(503, "storage_unavailable", "Storage is temporarily unavailable.")


async def account_data_unavailable(_: Request, __: AccountDataUnavailable) -> JSONResponse:
    return _error_response(
        503, "account_data_unavailable", "Account data is temporarily unavailable."
    )


async def invalid_retry_target(_: Request, __: InvalidRetryTargetError) -> JSONResponse:
    return _error_response(422, "invalid_retry_target", "This message cannot be retried.")


async def external_history_disclosure_denied(
    _: Request, __: ExternalHistoryDisclosureDenied
) -> JSONResponse:
    return _error_response(
        409,
        "conversation_source_authority_changed",
        "Current source permission could not be confirmed for this conversation.",
    )


async def health() -> dict[str, str]:
    """Minimal readiness endpoint used by Cloud Run and deployment checks."""
    return {"status": "ok", "service": "api"}


async def context_error(_: Request, error: ContextError) -> JSONResponse:
    if error.code == "context_message_too_large":
        return _error_response(
            422,
            error.code,
            "This message exceeds the context budget. Edit it to a shorter message and retry.",
        )
    if error.code == "context_budget_invalid":
        return _error_response(503, error.code, "The context budget is invalid.")
    return _error_response(422, error.code, "Required context could not be prepared.")


async def context_preparation_error(_: Request, error: ContextPreparationError) -> JSONResponse:
    status = (
        422
        if error.code.startswith("context_")
        or error.code
        in {
            "continuation_source_policy_denied",
            "continuation_source_not_active_completed",
        }
        else 503
    )
    return _error_response(status, error.code, "Context preparation could not complete.")


async def preparation_provider_error(_: Request, error: LLMError) -> JSONResponse:
    return _error_response(503, error.code, "Context preparation is unavailable. Please retry.")


async def context_configuration_error(_: Request, __: ContextBudgetInvalidError) -> JSONResponse:
    return _error_response(503, "context_budget_invalid", "The context budget is invalid.")


async def research_error(_: Request, error: ResearchError) -> JSONResponse:
    return _error_response(
        error.status,
        error.code,
        "Research could not proceed. Check the session or start a new request.",
    )


async def decision_error(_: Request, error: DecisionError) -> JSONResponse:
    return _error_response(
        error.status,
        error.code,
        "The decision could not be completed. Check its evidence and constraints.",
    )


CORE_EXCEPTION_HANDLERS = (
    (RequestValidationError, request_validation_error),
    (HTTPException, http_exception),
    (ResourceNotFoundError, resource_not_found),
    (ConversationConflictError, conversation_conflict),
    (ExternalHistoryDisclosureDenied, external_history_disclosure_denied),
    (StorageError, storage_error),
    (AccountDataUnavailable, account_data_unavailable),
    (InvalidRetryTargetError, invalid_retry_target),
    (ContextError, context_error),
    (ContextPreparationError, context_preparation_error),
    (LLMError, preparation_provider_error),
    (ContextBudgetInvalidError, context_configuration_error),
    (ResearchError, research_error),
    (DecisionError, decision_error),
)


app = create_app()
