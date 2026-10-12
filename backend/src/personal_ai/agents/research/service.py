"""One fenced, deadline-bounded research pass; no chat or memory writes."""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import uuid4, uuid5

import anyio

from personal_ai.agents.research.contracts import ResearchError, ResearchSession, evolve
from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.context.authority import permission_dependencies_current
from personal_ai.context.authorization import (
    authorize_base_disclosure,
    authorize_context_selection,
)
from personal_ai.context.providers import ContextPreparationError, ContextSelection
from personal_ai.evidence.contracts import AdapterAttempt, SearchQuery
from personal_ai.evidence.pipeline import extract_evidence, select_evidence, validate_synthesis
from personal_ai.llm.attribution import log_generation_attribution
from personal_ai.llm.preparation import require_matching_endpoint
from personal_ai.search.authority import ResearchSourceRightsRevalidator, observation_dependencies
from personal_ai.search.contracts import (
    SearchDispatch,
    SearchResult,
    normalize_rights_authorization,
)
from personal_ai.search.planning import make_query_plan, make_search_operation
from personal_ai.search.policy import SnippetExtractor, configured_query_planner
from personal_ai.storage.async_io import io_call
from personal_ai.usage.context import bind_usage_task

logger = logging.getLogger(__name__)


def event(name, **data):
    return (
        f"event: research.{name}\ndata: {json.dumps({'schema_version': 'research-v1', **data})}\n\n"
    )


class ResearchService:
    def __init__(
        self,
        settings,
        repository,
        adapter,
        context,
        llm,
        *,
        owner_id="local",
        application_context: ApplicationContextRequest | None = None,
        clock=None,
        planner=None,
        extractor=None,
        reranker=None,
    ):
        self.settings, self.repository, self.adapter = settings, repository, adapter
        self.context, self.llm, self.owner_id = context, llm, owner_id
        self.context.permission_revalidator = ResearchSourceRightsRevalidator(
            settings, adapter=adapter, delegate=context.permission_revalidator
        )
        self.application_context = application_context
        self.clock = clock or (lambda: datetime.now(UTC))
        self.planner = planner or configured_query_planner(settings)
        self.extractor = extractor or SnippetExtractor()
        self.reranker = reranker

    async def create(self, request):
        self._authorize_research_context()
        now = self.clock()
        session = ResearchSession(
            id=uuid4(),
            owner_id=self.owner_id,
            request=request,
            request_fingerprint=request.fingerprint(),
            state="pending",
            created_at=now,
            updated_at=now,
            expires_at=now + timedelta(hours=24),
            application_id=self.application_context.scope.application_id,
            workspace_id=self.application_context.scope.workspace_id,
        )
        return self.view(await io_call(self.repository.create, session))

    def view(self, session):
        now = self.clock()
        if session.state == "running" and session.execution_deadline <= now:
            return evolve(
                session,
                state="failed",
                failure_code="execution_abandoned",
                answer=None,
                citations=(),
            )
        if session.state in {"completed", "pending", "insufficient", "failed"} and session.expires_at <= now:
            return evolve(session, state="expired", answer=None, citations=())
        return session

    async def detail(self, session_id):
        self._authorize_research_context()
        session = await io_call(self.repository.get, self.owner_id, session_id)
        if not permission_dependencies_current(
            observation_dependencies(tuple(s for s in session.observations if s.status == "accepted")),
            self.context.permission_revalidator,
        ):
            raise ResearchError("research_source_rights_revoked", 403)
        return self.view(session)

    async def prepare_run(self, session_id):
        session = await self.detail(session_id)
        if session.iterative_run_id is not None:
            raise ResearchError("research_session_owned_by_iterative_run", 409)
        if session.state not in {"pending", "running"}:
            return session
        now = self.clock()
        return await io_call(
            self.repository.claim,
            self.owner_id,
            session_id,
            uuid4(),
            now,
            now + timedelta(seconds=self.settings.research_timeout_seconds),
        )

    async def stream(self, session):
        if session.state != "running":
            yield event(
                "terminal",
                session_id=str(session.id),
                state=session.state,
                failure_code=session.failure_code,
            )
            return
        current = session
        terminal = False
        results, successful, successful_rights = [], {}, {}
        seconds = max(0, (session.execution_deadline - self.clock()).total_seconds())
        deadline = monotonic() + seconds

        async def save(**changes):
            nonlocal current
            candidate = evolve(
                current, updated_at=self.clock(), revision=current.revision + 1, **changes
            )
            current = await io_call(self.repository.save, candidate)
            return current

        try:
            async with asyncio.timeout(seconds):
                self._authorize_research_context()
                yield event("started", session_id=str(current.id), state="running")
                query_plan = await io_call(
                    make_query_plan,
                    self.planner,
                    current.request,
                    self.settings,
                )
                queries = tuple(
                    SearchQuery(
                        id=uuid4(),
                        session_id=current.id,
                        owner_id=current.owner_id,
                        normalized_query=q,
                        sequence=i,
                        created_at=self.clock(),
                    )
                    for i, q in enumerate(query_plan.queries)
                )
                await save(queries=queries, query_plan=query_plan)
                yield event("planned", session_id=str(current.id), query_count=len(queries))
                for query in queries:
                    if len(results) >= self.settings.research_max_sources:
                        break
                    for number in range(1, self.settings.research_attempt_limit + 1):
                        started, error_code, retryable = self.clock(), None, False
                        operation = make_search_operation(
                            current.request,
                            query,
                            query_id=query.id,
                            max_results=self.settings.research_max_sources - len(results),
                            deadline_at=current.execution_deadline,
                            plan=query_plan,
                        )
                        begun = AdapterAttempt(
                            id=uuid4(),
                            session_id=current.id,
                            query_id=query.id,
                            owner_id=current.owner_id,
                            adapter=self.adapter.name,
                            idempotency_key=f"{query.id}:{number}:start",
                            attempt_number=number,
                            status="started",
                            started_at=started,
                            operation_identity=operation.identity,
                            strategy_id=operation.strategy_id,
                            strategy_version=operation.strategy_version,
                            strategy_reason=operation.strategy_reason,
                        )
                        await save(attempts=(*current.attempts, begun))
                        usage_invocation_id = usage_attempt_id = None
                        try:
                            rights_reference = normalize_rights_authorization(
                                self.adapter.authorize_snippets(), self.adapter.name
                            )
                            if rights_reference is None:
                                raise ResearchError("research_configuration_invalid")
                            with bind_usage_task(
                                "web_research_search",
                                run_id=str(current.id),
                                invocation_id=uuid5(query.id, "provider-usage-search"),
                                send_number=number,
                            ):
                                dispatch = await self.adapter.search(operation)
                            if not isinstance(dispatch, SearchDispatch):
                                raise ResearchError("search_invalid_response")
                            fetched = dispatch.results
                            usage_invocation_id = dispatch.usage_invocation_id
                            usage_attempt_id = dispatch.usage_attempt_id
                            if not isinstance(fetched, (list, tuple)) or len(fetched) > (
                                self.settings.research_max_sources - len(results)
                            ) or any(
                                not isinstance(r, SearchResult) for r in fetched
                            ):
                                raise ResearchError("search_invalid_response")
                        except ResearchError as error:
                            allowed = {
                                "search_quota",
                                "search_timeout",
                                "search_unavailable",
                                "search_rejected",
                                "search_invalid_response",
                                "search_response_oversized",
                                "research_configuration_invalid",
                                "search_constraint_unsupported",
                                "search_source_scope_empty",
                            }
                            error_code = error.code if error.code in allowed else "search_failed"
                            retryable = bool(getattr(error, "retryable", False))
                            usage_invocation_id = getattr(error, "usage_invocation_id", None)
                            usage_attempt_id = getattr(error, "usage_attempt_id", None)
                            fetched = ()
                        except Exception:  # noqa: BLE001 - record unexpected adapter failure safely
                            error_code, fetched = "search_failed", ()
                        attempt = AdapterAttempt(
                            id=uuid4(),
                            session_id=current.id,
                            query_id=query.id,
                            owner_id=current.owner_id,
                            adapter=self.adapter.name,
                            idempotency_key=f"{query.id}:{number}:result",
                            parent_attempt_id=begun.id,
                            attempt_number=number,
                            status="failed" if error_code else "completed",
                            started_at=started,
                            completed_at=self.clock(),
                            error_code=error_code,
                            usage_invocation_id=usage_invocation_id,
                            usage_attempt_id=usage_attempt_id,
                            operation_identity=operation.identity,
                            strategy_id=operation.strategy_id,
                            strategy_version=operation.strategy_version,
                            strategy_reason=operation.strategy_reason,
                        )
                        await save(attempts=(*current.attempts, attempt))
                        yield event(
                            "attempt",
                            session_id=str(current.id),
                            query_id=str(query.id),
                            attempt_id=str(attempt.id),
                            state=attempt.status,
                        )
                        if not error_code:
                            limit = self.settings.research_max_sources - len(results)
                            results.extend((query.id, r) for r in fetched[:limit])
                            successful[query.id] = attempt
                            successful_rights[query.id] = rights_reference
                            break
                        if not retryable or number == self.settings.research_attempt_limit:
                            await save(
                                queries=tuple(
                                    q.model_copy(
                                        update={"state": "failed", "executed_at": self.clock()}
                                    )
                                    if q.id == query.id
                                    else q
                                    for q in current.queries
                                )
                            )
                            raise ResearchError(error_code)
                    updated_queries = tuple(
                        q.model_copy(update={"state": "completed", "executed_at": self.clock()})
                        if q.id == query.id
                        else q
                        for q in current.queries
                    )
                    await save(queries=updated_queries)
                observations, evidence = await io_call(
                    extract_evidence,
                    current,
                    results,
                    successful,
                    self.extractor,
                    self.clock(),
                    self.settings,
                    rights_reference=successful_rights,
                    source_origin=self.adapter.source_origin,
                )
                await save(observations=observations, evidence=evidence)
                yield event(
                    "evidence",
                    session_id=str(current.id),
                    source_count=len(observations),
                    evidence_count=len(evidence),
                )
                selection, messages, inference_context = await io_call(
                    select_evidence,
                    current,
                    self.context,
                    self.clock(),
                    deadline,
                    self.reranker,
                    clock=self.clock,
                    packing_strategy=(self.settings.research_packing_strategy
                                      if self.settings.research_retrieval_experiments_enabled
                                      else "literal-extractive-v1"),
                    application_context=self.application_context,
                    expected_counter_identity=(
                        self.llm.identity
                        if getattr(self.llm, "requires_inference_context", False)
                        else None
                    ),
                )
                await save(selection=selection)
                yield event(
                    "selected",
                    session_id=str(current.id),
                    evidence_count=len(selection.evidence_ids),
                )
                # Conservatively refuse to silently omit potentially conflicting eligible records.
                if not selection.evidence_ids or "budget" in selection.excluded.values():
                    code = (
                        "empty_plan"
                        if not queries
                        else "no_results"
                        if not results
                        else "source_denied"
                        if not evidence and any(s.status == "source_denied" for s in observations)
                        else "extraction_no_evidence"
                        if not evidence
                        else "insufficient_evidence"
                    )
                    await save(state="insufficient", failure_code=code)
                else:
                    # Rights may have changed while searching/counting; the exact
                    # server preflight reference must still bind every passage.
                    reference = normalize_rights_authorization(
                        self.adapter.authorize_snippets(), self.adapter.name
                    )
                    if reference is None or any(
                        s.rights_authority_id != reference.authority_id
                        or s.rights_epoch != reference.epoch
                        or s.rights_reference != reference.reference
                        for s in current.observations if s.status == "accepted"
                    ):
                        raise ResearchError("research_configuration_invalid")
                    output = ""
                    bounded = getattr(self.llm, "stream_bounded", None)
                    stream = (
                        bounded(
                            messages,
                            max_output_tokens=self.context.settings.max_response_tokens,
                            timeout_seconds=max(0.01, min(
                                self.context.settings.request_timeout_seconds,
                                deadline - monotonic(),
                            )),
                            inference_context=inference_context,
                        )
                        if bounded is not None
                        else self.llm.stream(messages, inference_context=inference_context)
                    )
                    try:
                        with bind_usage_task(
                            "web_research_synthesis", run_id=str(current.id)
                        ):
                            async for delta in stream:
                                if not isinstance(delta, str) or len(output) + len(delta) > 20000:
                                    raise ResearchError("synthesis_oversized")
                                output += delta
                    finally:
                        close = getattr(stream, "aclose", None)
                        if close is not None:
                            try:
                                await close()
                            except (Exception, asyncio.CancelledError):  # noqa: BLE001
                                logger.info("Research synthesis stream cleanup failed")
                        log_generation_attribution(
                            logger,
                            "research_synthesis",
                            getattr(stream, "metadata", None),
                            fallback_identity=getattr(self.llm, "identity", None),
                        )
                    try:
                        answer, citations = validate_synthesis(current, output)
                    except ResearchError:
                        await save(state="insufficient", failure_code="invalid_citations")
                    else:
                        selected = set(selection.evidence_ids)
                        expiry = min(e.expires_at for e in current.evidence if e.id in selected)
                        if expiry <= self.clock():
                            await save(state="insufficient", failure_code="evidence_expired")
                        else:
                            await save(
                                state="completed",
                                answer=answer,
                                citations=citations,
                                expires_at=expiry,
                            )
                terminal = True
                yield event(
                    "terminal",
                    session_id=str(current.id),
                    state=current.state,
                    failure_code=current.failure_code,
                )
        except (asyncio.CancelledError, GeneratorExit):
            raise
        except Exception as error:  # noqa: BLE001 - no provider details reach clients
            code = "research_timeout" if isinstance(error, TimeoutError) else "research_failed"
            if isinstance(error, ResearchError):
                code = error.code if error.code.startswith("search_") else "research_failed"
            with anyio.CancelScope(shield=True):
                try:
                    # Persist known completed observations on partial execution;
                    # an uncertain/failed call contributes no fabricated result.
                    if results and not current.observations:
                        observations, evidence = extract_evidence(
                            current, results, successful, self.extractor,
                            self.clock(), self.settings, rights_reference=successful_rights,
                            source_origin=self.adapter.source_origin,
                        )
                        await save(observations=observations, evidence=evidence)
                    await save(state="failed", failure_code=code)
                except Exception:  # noqa: BLE001 - deadline-derived failure survives storage outage
                    code = "storage_unavailable"
            terminal = True
            yield event("terminal", session_id=str(current.id), state="failed", failure_code=code)
        finally:
            if not terminal:
                with anyio.CancelScope(shield=True):
                    try:
                        current = await io_call(self.repository.get, self.owner_id, session.id)
                        if current.state == "running":
                            await save(state="failed", failure_code="research_cancelled")
                    except Exception:  # noqa: BLE001 - durable execution deadline remains visible
                        logging.getLogger(__name__).info("Research cancellation persistence failed")

    def _authorize_research_context(self):
        if self.application_context is None:
            raise ContextPreparationError("application_context_required")
        authorize_base_disclosure(self.application_context)
        require_matching_endpoint(self.llm, self.context.counter)
        authorize_context_selection(
            self.application_context,
            ContextSelection(
                provider_id="external_research",
                operation="search",
                fields=("evidence_record",),
            ),
        )
