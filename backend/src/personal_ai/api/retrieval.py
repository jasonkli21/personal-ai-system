"""Exact authenticated standalone retrieval and selected read-only tool routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from personal_ai.api.dependencies import get_request_scope
from personal_ai.applications.registry import application_registry_for
from personal_ai.auth.scope import RequestScope
from personal_ai.persistence.factory import persistence_factory
from personal_ai.retrieval.contracts import RetrievalOutcome, RetrievalQuery
from personal_ai.retrieval.journal import IntentConflict
from personal_ai.retrieval.service import RetrievalService
from personal_ai.retrieval.tools import ToolOutcome, require_tool
from personal_ai.settings import Settings, get_settings

router = APIRouter(tags=["retrieval-v1"])


def retrieval_service(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    scope: Annotated[RequestScope, Depends(get_request_scope)],
):
    if not settings.retrieval_enabled:
        raise HTTPException(404, "not_found")
    return RetrievalService(
        settings,
        scope,
        lambda: persistence_factory(settings).provider_usage_accounting(settings),
        current_settings=request.app.dependency_overrides.get(get_settings, get_settings),
        request_authority=lambda: request.state.source_authority(),
    )


@router.post("/v1/retrieval/query", response_model=RetrievalOutcome)
async def query_retrieval(
    body: RetrievalQuery,
    service: Annotated[RetrievalService, Depends(retrieval_service)],
):
    try:
        return await service.query(body)
    except IntentConflict:
        raise HTTPException(409, "retrieval_intent_conflict") from None


@router.post("/v1/tools/retrieval.query.v1/invoke", response_model=ToolOutcome)
async def invoke_retrieval(
    body: RetrievalQuery,
    request: Request,
    service: Annotated[RetrievalService, Depends(retrieval_service)],
):
    def guard():
        return require_tool(application_registry_for(request), service.scope.application_id)

    try:
        return await guard()(service, body, guard)
    except IntentConflict:
        raise HTTPException(409, "retrieval_intent_conflict") from None
    except Exception:  # noqa: BLE001 - metadata errors never expose registry internals
        raise HTTPException(404, "tool_unavailable") from None
