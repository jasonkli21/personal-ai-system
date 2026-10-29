"""Default-off authenticated user controls; no agent invocation HTTP endpoint."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from personal_ai.api.dependencies import get_request_scope, require_recent_auth
from personal_ai.auth.scope import RequestScope
from personal_ai.memory.control_contracts import MutationInput, ReviewInput, SearchInput
from personal_ai.memory.control_service import MemoryControlService
from personal_ai.memory.knowledge_service import KnowledgeService
from personal_ai.persistence.factory import persistence_factory
from personal_ai.persistence.postgres.control import PostgresControlRepository
from personal_ai.settings import Settings, get_settings

router = APIRouter(prefix="/v1/memory/control", tags=["memory-control"])


def get_memory_control_service(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    scope: Annotated[RequestScope, Depends(get_request_scope)],
):
    if not (
        settings.memory_enabled
        and settings.memory_knowledge_selection_enabled
        and settings.memory_user_management_enabled
    ):
        raise HTTPException(status_code=404, detail="not_found")
    # Explicit installed host only: no production source/project registration exists.
    host = getattr(request.app.state, "memory_control_host", None)
    if host is None:
        raise HTTPException(status_code=503, detail="memory_control_authority_unavailable")
    try:
        factory = persistence_factory(settings)
        memories, messages = factory.memory_repository(), factory.message_repository()
        lifecycle = factory.memory_lifecycle_repository(memories, messages)
        knowledge = KnowledgeService(settings, memories, lifecycle, host.resolver)
        return MemoryControlService(
            knowledge, PostgresControlRepository(memories, lifecycle), scope, host.project_id(scope)
        )
    except Exception:  # noqa: BLE001 - never return configuration/source details
        raise HTTPException(status_code=503, detail="memory_control_unavailable") from None


Service = Annotated[MemoryControlService, Depends(get_memory_control_service)]
RecentUser = Annotated[object, Depends(require_recent_auth)]


@router.get("/knowledge")
def search(service: Service, query: str = "", limit: int = 8):
    if len(query) > 200 or not 1 <= limit <= 8:
        raise HTTPException(status_code=422, detail="memory_query_invalid")
    return service.read(SearchInput(query=query, limit=limit))


@router.get("/topics")
def topics(service: Service):
    return service.read(SearchInput(), topics=True)


@router.get("/knowledge/{memory_id}")
def fetch(memory_id: UUID, service: Service):
    return service.read(SearchInput(), memory_id=memory_id)


@router.get("/proposals")
def proposals(service: Service):
    return service.proposals()


@router.post("/proposals/{proposal_id}/decision")
def review(proposal_id: UUID, body: ReviewInput, service: Service, _user: RecentUser):
    return service.mutate(body.decision, proposal_id, body)


@router.post("/knowledge/{memory_id}/forget")
def forget(memory_id: UUID, body: MutationInput, service: Service, _user: RecentUser):
    return service.mutate("forget", memory_id, body)


@router.post("/knowledge/{memory_id}/revise")
def revise(memory_id: UUID, body: MutationInput, service: Service, _user: RecentUser):
    return service.mutate("revise", memory_id, body)
