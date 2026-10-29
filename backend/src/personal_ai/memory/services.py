"""Bounded extraction and advisory semantic retrieval; no lifecycle mutations."""

import logging
import math
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from time import monotonic

from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.context.authorization import authorize_memory_disclosure
from personal_ai.context.contracts import complete_turns, fingerprint
from personal_ai.context.history import (
    manual_import_is_reusable,
    memory_extraction_context_reason,
    message_context_authority,
)
from personal_ai.context.providers import ContextPreparationError
from personal_ai.llm.client import EmbeddingResult
from personal_ai.memory.contracts import (
    DerivedMemory,
    ExtractionResult,
    Memory,
    MemoryCandidateTrace,
    MemoryQuery,
    MemoryRetrievalTrace,
    RetrievalResult,
    embedding_space_for,
    identity,
    normalize,
    vector,
)
from personal_ai.memory.policy import candidate_reason, content_reason
from personal_ai.storage.errors import ResourceNotFoundError

logger = logging.getLogger(__name__)


def source_messages(memory, messages, *, timeout=5):
    active = messages.list_active(
        owner_id=memory.owner_id, conversation_id=memory.source_conversation_id, timeout=timeout
    )
    source = [m for m in active if m.id in memory.source_message_ids]
    if (
        tuple(m.id for m in source) != memory.source_message_ids
        or not all(m.role.value == "user" and m.status.value == "completed" for m in source)
        or fingerprint(source) != memory.source_fingerprint
    ):
        return None
    completed_users = {u.id for u, a in complete_turns(active)}
    return source if set(memory.source_message_ids) <= completed_users else None


def source_turn_reuse_reason(
    memory,
    messages,
    application_context,
    *,
    timeout=5,
    permission_revalidator=None,
    now=None,
):
    """Revalidate source authority and manual-import reuse for a memory's source turn."""
    active = messages.list_active(
        owner_id=memory.owner_id,
        conversation_id=memory.source_conversation_id,
        timeout=timeout,
    )
    turn = next(
        (pair for pair in complete_turns(active) if pair[1].id == memory.source_turn_id),
        None,
    )
    if turn is None:
        return "branch_mismatch"
    context_reason = memory_extraction_context_reason(turn[1])
    if context_reason is not None:
        return context_reason
    dependencies, expires_at, _sensitivity, _source_classes = message_context_authority(turn[1])
    checked_at = (now or datetime.now(UTC)).astimezone(UTC)
    if expires_at is not None and expires_at <= checked_at:
        return "source_expired"
    if dependencies and permission_revalidator is None:
        return "source_permission_unverified"
    try:
        permissions_current = all(
            permission_revalidator.is_current(dependency) for dependency in dependencies
        )
    except Exception:  # noqa: BLE001 - source authority fails closed
        permissions_current = False
    if not permissions_current:
        return "source_permission_revoked"
    if application_context is None:
        return None
    policy = application_context.definition.context_policy.sidecar.manual_import_reuse
    return None if manual_import_is_reusable(turn[1], policy) else "source_policy_denied"


def _validate_embedding_result(result, settings, *, task):
    if not isinstance(result, EmbeddingResult) or result.task != task:
        raise ValueError("embedding_invalid")
    space = result.space
    if (
        space.model_id != settings.memory_embedding_model
        or space.dimensions != settings.memory_embedding_dimensions
        or space.normalization != "l2"
        or space.document_task != "RETRIEVAL_DOCUMENT"
        or space.query_task != "RETRIEVAL_QUERY"
        or space.version != "v1"
    ):
        raise ValueError("embedding_space_mismatch")
    vector(result.values, space.dimensions)
    return tuple(result.values), space


class MemoryExtractionService:
    def __init__(self, settings, repository, messages, extractor, embedder, *, clock=None):
        self.settings, self.repository, self.messages = settings, repository, messages
        self.extractor, self.embedder = extractor, embedder
        self.clock = clock or (lambda: datetime.now(UTC))

    def run(
        self,
        completed,
        *,
        application_context: ApplicationContextRequest | None = None,
    ):
        if not self.settings.memory_enabled or not self.settings.memory_extraction_enabled:
            return ExtractionResult(reasons=("disabled",))
        inference_context = None
        if application_context is not None:
            scope = application_context.scope
            if (
                scope.owner_id != completed.owner_id
                or scope.application_id != completed.application_id
                or scope.workspace_id != completed.workspace_id
            ):
                return ExtractionResult(reasons=("policy_denied",))
            try:
                inference_context = authorize_memory_disclosure(application_context)
            except ContextPreparationError:
                return ExtractionResult(reasons=("policy_denied",))
            if not manual_import_is_reusable(
                completed,
                application_context.definition.context_policy.sidecar.manual_import_reuse,
            ):
                return ExtractionResult(reasons=("source_policy_denied",))
        elif any(
            getattr(component, "requires_inference_context", False)
            for component in (self.extractor, self.embedder)
        ):
            return ExtractionResult(reasons=("policy_denied",))
        deadline = monotonic() + self.settings.memory_timeout_seconds
        created, skipped, reasons = [], [], []
        attributions = []
        stage = "storage"

        def remaining():
            left = deadline - monotonic()
            if left <= 0:
                raise TimeoutError("memory_timeout")
            return left

        try:
            active = self.messages.list_active(
                owner_id=completed.owner_id,
                conversation_id=completed.conversation_id,
                timeout=remaining(),
            )
            turn = next((t for t in complete_turns(active) if t[1].id == completed.id), None)
            if turn is None:
                return ExtractionResult(reasons=("branch_mismatch",))
            context_reason = memory_extraction_context_reason(turn[1])
            if context_reason is not None:
                return ExtractionResult(reasons=(context_reason,))
            if any(
                content_reason(m.content, self.settings) for m in turn if m.role.value == "user"
            ):
                return ExtractionResult(reasons=("sensitive_or_external",))
            stage = "extraction"
            if getattr(self.extractor, "requires_inference_context", False):
                extraction = self.extractor.extract(
                    turn, timeout=remaining(), inference_context=inference_context
                )
            else:
                extraction = self.extractor.extract(turn, timeout=remaining())
            candidates = getattr(extraction, "candidates", extraction)
            attribution = getattr(extraction, "attribution", None)
            if attribution is not None:
                attributions.append(attribution)
            for candidate in candidates[: self.settings.memory_max_candidates_per_turn]:
                remaining()
                reason = candidate_reason(candidate, turn, self.settings)
                if reason:
                    reasons.append(reason)
                    continue
                source = [m for m in turn if m.id in candidate.source_message_ids]
                source_hash = fingerprint(source)
                memory_id = identity(completed.owner_id, source_hash, candidate)
                from personal_ai.storage.errors import ResourceNotFoundError

                stage = "storage"
                try:
                    self.repository.get(
                        owner_id=completed.owner_id, memory_id=memory_id, timeout=remaining()
                    )
                    skipped.append(memory_id)
                    continue
                except ResourceNotFoundError:
                    pass
                stage = "embedding"
                if getattr(self.embedder, "requires_inference_context", False):
                    embeddings = self.embedder.embed(
                        [candidate.content],
                        timeout=remaining(),
                        inference_context=inference_context,
                    )
                else:
                    embeddings = self.embedder.embed(
                        [candidate.content], timeout=remaining()
                    )
                if len(embeddings) != 1:
                    raise ValueError("embedding_invalid")
                embedding_values, embedding_space = _validate_embedding_result(
                    embeddings[0], self.settings, task="document"
                )
                memory = Memory(
                    **candidate.model_dump(exclude={"effective_at"}),
                    id=memory_id,
                    owner_id=completed.owner_id,
                    application_id=completed.application_id,
                    workspace_id=completed.workspace_id,
                    scope_version=2,
                    normalized_content=normalize(candidate.content),
                    source_conversation_id=completed.conversation_id,
                    source_turn_id=completed.id,
                    source_fingerprint=source_hash,
                    observed_at=source[-1].created_at,
                    effective_at=candidate.effective_at or source[-1].created_at,
                    created_at=self.clock(),
                    embedding=embedding_values,
                    embedding_provider=embedding_space.provider_id,
                    embedding_model=embedding_space.model_id,
                    embedding_dimensions=embedding_space.dimensions,
                    embedding_normalization=embedding_space.normalization,
                    embedding_document_task=embedding_space.document_task,
                    embedding_query_task=embedding_space.query_task,
                    embedding_space_version=embedding_space.version,
                )
                remaining()
                stage = "storage"
                if source_messages(memory, self.messages, timeout=remaining()) is None:
                    reasons.append("branch_mismatch")
                    continue
                _, fresh = self.repository.create(memory, timeout=remaining())
                (created if fresh else skipped).append(memory.id)
        except Exception as error:  # noqa: BLE001 - optional work must never affect chat
            reasons.append("timeout" if isinstance(error, TimeoutError) else stage + "_failed")
        result = ExtractionResult(
            tuple(created), tuple(skipped), tuple(reasons), tuple(attributions)
        )
        logger.info(
            "Memory extraction created=%s skipped=%s reasons=%s",
            len(created),
            len(skipped),
            result.reasons,
        )
        return result


class MemoryRetriever:
    def __init__(
        self,
        settings,
        repository,
        messages,
        embedder,
        lifecycle_repository=None,
        *,
        permission_revalidator=None,
        knowledge_service=None,
        clock=None,
    ):
        self.settings, self.repository, self.messages = settings, repository, messages
        self.embedder = embedder
        self.lifecycle = lifecycle_repository
        self.permission_revalidator = permission_revalidator
        self.knowledge_service = knowledge_service
        self.clock = clock or (lambda: datetime.now(UTC))

    def retrieve_knowledge(self, query: MemoryQuery):
        """Explicit server-only schema-3 selection; legacy retrieve is unchanged."""
        if self.knowledge_service is None:
            return RetrievalResult(diagnostics=("knowledge_source_unsupported",))
        return self.knowledge_service.select(query)

    def _state(self, owner_id, memory_id):
        from personal_ai.memory.lifecycle import MemoryLifecycleState

        if self.lifecycle is None:
            return MemoryLifecycleState(owner_id=owner_id, memory_id=memory_id)
        return self.lifecycle.get_state(owner_id=owner_id, memory_id=memory_id)

    def _valid_derived(self, record, owner_id, deadline, application_context):
        if not isinstance(record, DerivedMemory) or record.owner_id != owner_id:
            return False, "malformed_record"
        if (
            record.embedding_model != self.settings.memory_embedding_model
            or record.embedding_dimensions != self.settings.memory_embedding_dimensions
        ):
            return False, "incompatible_embedding"
        if content_reason(record.content, self.settings):
            return False, "sensitive_or_external"
        try:
            DerivedMemory.model_validate(record.model_dump())
        except (ValueError, TypeError):
            return False, "malformed_record"
        for source in record.sources:
            if monotonic() >= deadline:
                raise TimeoutError("memory_timeout")
            try:
                memory = self.repository.get(
                    owner_id=owner_id,
                    memory_id=source.memory_id,
                    timeout=max(0.001, deadline - monotonic()),
                )
            except ResourceNotFoundError:
                return False, "source_unavailable"
            if (
                memory.source_fingerprint != source.source_fingerprint
                or memory.source_conversation_id != source.source_conversation_id
                or memory.source_turn_id != source.source_turn_id
                or memory.source_message_ids != source.source_message_ids
                or embedding_space_for(memory) != embedding_space_for(record)
                or memory.memory_type not in ("preference", "episodic_observation")
                or content_reason(memory.content, self.settings)
            ):
                return False, "source_mismatch"
            from personal_ai.memory.dependencies import dependency_version

            state = self._state(owner_id, memory.id)
            if (
                source.dependency_version is None
                and state.validity_epoch > 0
                or source.dependency_version is not None
                and source.dependency_version != dependency_version(memory, state)
            ):
                return False, "source_revision_changed"
            from personal_ai.memory.dependencies import original_reason

            reuse_reason = original_reason(
                memory,
                self.settings,
                self.messages,
                self.lifecycle,
                application_context=application_context,
                timeout=max(0.001, deadline - monotonic()),
                permission_revalidator=self.permission_revalidator,
                now=self.clock(),
            )
            if reuse_reason is not None:
                return False, reuse_reason
            state = self._state(owner_id, memory.id)
            if state.retrieval_status != "active":
                return False, "source_inactive"
            if (
                source.excerpt != memory.content
                or source_messages(
                    memory, self.messages, timeout=max(0.001, deadline - monotonic())
                )
                is None
            ):
                return False, "branch_mismatch"
        return True, None

    def retrieve(
        self,
        owner_id,
        query,
        active_messages,
        *,
        timeout=None,
        application_context: ApplicationContextRequest | None = None,
    ):
        from personal_ai.memory.deadlines import lifecycle_deadline

        with lifecycle_deadline(timeout or self.settings.memory_timeout_seconds):
            return self._retrieve(
                owner_id,
                query,
                active_messages,
                timeout=timeout,
                application_context=application_context,
            )

    def _retrieve(
        self,
        owner_id,
        query,
        active_messages,
        *,
        timeout=None,
        application_context: ApplicationContextRequest | None = None,
    ):
        if not self.settings.memory_enabled:
            return RetrievalResult(diagnostics=("disabled",))
        deadline = monotonic() + min(
            timeout or self.settings.memory_timeout_seconds, self.settings.memory_timeout_seconds
        )
        started = monotonic()
        requested = self.settings.memory_experiment_variant
        try:
            from personal_ai.auth.scope import current_request_scope

            bound_scope = current_request_scope()
            if bound_scope is not None and bound_scope.owner_id != owner_id:
                return RetrievalResult(diagnostics=("policy_denied",))
            inference_context = None
            if application_context is not None:
                scope = application_context.scope
                if scope.owner_id != owner_id or any(
                    message.owner_id != scope.owner_id
                    or message.application_id != scope.application_id
                    or message.workspace_id != scope.workspace_id
                    for message in active_messages
                ):
                    return RetrievalResult(diagnostics=("policy_denied",))
                try:
                    inference_context = authorize_memory_disclosure(application_context)
                except ContextPreparationError:
                    return RetrievalResult(diagnostics=("policy_denied",))
            elif getattr(self.embedder, "requires_inference_context", False):
                return RetrievalResult(diagnostics=("policy_denied",))
            # Sensitive queries are not sent to an embedding provider either.
            if content_reason(query, self.settings):
                return RetrievalResult(diagnostics=("query_policy",))
            if getattr(self.embedder, "requires_inference_context", False):
                embeddings = self.embedder.embed(
                    [query],
                    query=True,
                    timeout=max(0.001, deadline - monotonic()),
                    inference_context=inference_context,
                )
            else:
                embeddings = self.embedder.embed(
                    [query], query=True, timeout=max(0.001, deadline - monotonic())
                )
            if len(embeddings) != 1:
                raise ValueError("embedding_invalid")
            embedding, embedding_space = _validate_embedding_result(
                embeddings[0], self.settings, task="query"
            )
            from personal_ai.auth.scope import RequestScope, current_application_scope
            from personal_ai.memory.dependencies import (
                original_reason,
                record_dependencies,
            )
            from personal_ai.memory.freshness import freshness

            scope = (
                application_context.scope
                if application_context
                else bound_scope
                if bound_scope is not None
                else RequestScope(
                    owner_id=owner_id,
                    request_id="memory-local",
                    **current_application_scope().model_dump(),
                )
            )
            contract = MemoryQuery(
                scope=scope,
                max_items=min(100, self.settings.memory_retrieval_limit),
                max_tokens=self.settings.memory_max_context_tokens,
                candidate_limit=self.settings.memory_retrieval_candidate_limit,
                embedding_space=embedding_space,
                strategy=requested,
                deadline=deadline,
                as_of=self.clock(),
                query_fingerprint=sha256(query.encode()).hexdigest(),
                time_budget_seconds=min(
                    timeout or self.settings.memory_timeout_seconds,
                    self.settings.memory_timeout_seconds,
                ),
                dependency_versions=(
                    (application_context.definition.context_policy.version,)
                    if application_context
                    else ()
                ),
            )
            preexcluded = []
            hard_exclusion_count = 0

            def eligible(record):
                nonlocal hard_exclusion_count
                if monotonic() >= deadline:
                    raise TimeoutError("memory_timeout")
                if (record.owner_id, record.application_id, record.workspace_id) != (
                    scope.owner_id,
                    scope.application_id,
                    scope.workspace_id,
                ):
                    reason = "scope_mismatch"
                elif isinstance(record, DerivedMemory):
                    reason = self._valid_derived(record, owner_id, deadline, application_context)[1]
                else:
                    reason = original_reason(
                        record,
                        self.settings,
                        self.messages,
                        self.lifecycle,
                        timeout=max(0.001, deadline - monotonic()),
                        application_context=application_context,
                        permission_revalidator=self.permission_revalidator,
                        now=self.clock(),
                    )
                if reason:
                    hard_exclusion_count += 1
                    if len(preexcluded) < contract.candidate_limit:
                        preexcluded.append((record, reason))
                return reason is None

            originals = tuple(
                self.repository.search(
                    owner_id=owner_id,
                    eligible=eligible,
                    embedding=embedding,
                    model=embedding_space.model_id,
                    dimensions=embedding_space.dimensions,
                    provider=embedding_space.provider_id,
                    normalization=embedding_space.normalization,
                    document_task=embedding_space.document_task,
                    query_task=embedding_space.query_task,
                    embedding_space_version=embedding_space.version,
                    limit=self.settings.memory_retrieval_candidate_limit,
                    timeout=max(0.001, deadline - monotonic()),
                )
            )[: self.settings.memory_retrieval_candidate_limit]
            candidates = list(originals)
            if requested == "consolidated" and hasattr(self.repository, "search_derived"):
                candidates.extend(
                    self.repository.search_derived(
                        owner_id=owner_id,
                        eligible=eligible,
                        embedding=embedding,
                        model=embedding_space.model_id,
                        dimensions=embedding_space.dimensions,
                        provider=embedding_space.provider_id,
                        normalization=embedding_space.normalization,
                        document_task=embedding_space.document_task,
                        query_task=embedding_space.query_task,
                        embedding_space_version=embedding_space.version,
                        limit=self.settings.memory_retrieval_candidate_limit,
                        timeout=max(0.001, deadline - monotonic()),
                    )
                )
            candidates = tuple(
                sorted(candidates, key=lambda s: (-s.similarity, str(s.memory.id)))[
                    : self.settings.memory_retrieval_candidate_limit
                    * (2 if requested == "consolidated" else 1)
                ]
            )
            valid, excluded = [], [(r.id, reason) for r, reason in preexcluded]
            states = {}
            for scored in candidates:
                if monotonic() >= deadline:
                    raise TimeoutError("memory_timeout")
                m, reason = scored.memory, None
                if m.owner_id != owner_id:
                    reason = "owner_mismatch"
                elif (m.application_id, m.workspace_id) != (
                    scope.application_id,
                    scope.workspace_id,
                ):
                    reason = "scope_mismatch"
                elif getattr(m, "status", "active") != "active":
                    reason = "inactive"
                elif embedding_space_for(m) != embedding_space:
                    reason = "incompatible_embedding"
                elif (
                    not math.isfinite(scored.similarity)
                    or scored.similarity < self.settings.memory_min_similarity
                ):
                    reason = "low_similarity"
                elif isinstance(m, DerivedMemory):
                    if requested != "consolidated":
                        reason = "variant_excludes_derived"
                    else:
                        reason = self._valid_derived(m, owner_id, deadline, application_context)[1]
                else:
                    try:
                        Memory.model_validate(m.model_dump())
                        vector(m.embedding, self.settings.memory_embedding_dimensions)
                    except (ValueError, TypeError):
                        excluded.append((m.id, "malformed_record"))
                        continue
                    source = source_messages(
                        m, self.messages, timeout=max(0.001, deadline - monotonic())
                    )
                    reason = (
                        "branch_mismatch"
                        if source is None
                        else source_turn_reuse_reason(
                            m,
                            self.messages,
                            application_context,
                            timeout=max(0.001, deadline - monotonic()),
                            permission_revalidator=self.permission_revalidator,
                            now=self.clock(),
                        )
                    )
                    if reason is None:
                        reason = candidate_reason(
                            m.model_copy(
                                update={
                                    "effective_at": (
                                        m.effective_at if m.effective_at != m.observed_at else None
                                    )
                                }
                            ),
                            source,
                            self.settings,
                        )
                if reason is None:
                    state = self._state(owner_id, m.id)
                    states[m.id] = state
                    if state.retrieval_status != "active":
                        reason = state.retrieval_status
                if reason:
                    excluded.append((m.id, reason))
                else:
                    valid.append(scored)
            # Fixed ordering exactly preserves Phase 3's similarity-band policy.
            valid.sort(
                key=lambda s: (
                    -math.floor(s.similarity / 0.05 + 1e-8),
                    s.memory.memory_type != "explicit_correction",
                    -s.memory.effective_at.timestamp(),
                    -s.similarity,
                    str(s.memory.id),
                )
            )
            fixed_order = tuple(valid)
            policy_version = self.settings.memory_scoring_policy_version
            policy_identity = None
            scores = ()
            applied = requested
            if requested in ("scored", "consolidated"):
                try:
                    from personal_ai.memory.lifecycle import ScorePolicy, score_memory

                    policy = ScorePolicy(
                        version=self.settings.memory_scoring_policy_version,
                        similarity_weight=self.settings.memory_score_similarity_weight,
                        importance_weight=self.settings.memory_score_importance_weight,
                        recency_weight=self.settings.memory_score_recency_weight,
                        frequency_weight=self.settings.memory_score_frequency_weight,
                        confidence_weight=self.settings.memory_score_confidence_weight,
                        half_life_days=self.settings.memory_recency_half_life_days,
                    )
                    policy_identity = policy.identity
                    score_rows = [
                        score_memory(item, states[item.memory.id], policy, now=self.clock())
                        for item in valid
                    ]
                    bad_ids = {row.memory_id for row in score_rows if row.score is None}
                    excluded.extend(
                        (row.memory_id, row.reason) for row in score_rows if row.score is None
                    )
                    valid = [item for item in valid if item.memory.id not in bad_ids]
                    by_id = {row.memory_id: row for row in score_rows}
                    if requested == "scored":
                        valid.sort(
                            key=lambda item: (-by_id[item.memory.id].score, str(item.memory.id))
                        )
                    else:
                        valid.sort(
                            key=lambda item: (
                                0
                                if item.memory.memory_type == "explicit_correction"
                                else 1
                                if isinstance(item.memory, DerivedMemory)
                                else 2,
                                -by_id[item.memory.id].score,
                                str(item.memory.id),
                            )
                        )
                    scores = tuple(by_id[item.memory.id] for item in valid)
                except Exception as error:  # noqa: BLE001 - fixed fallback stays provenance-checked
                    logger.info("Memory scoring fallback error_class=%s", type(error).__name__)
                    valid = [
                        item for item in fixed_order if not isinstance(item.memory, DerivedMemory)
                    ]
                    applied = "fixed"
            if requested == "compact":
                # No semantic merge: only exact repeated user wording is redundant.
                # Prefer originals; every omitted duplicate retains its durable identity.
                seen = set()
                compact = []
                for item in valid:
                    if any(
                        item.memory.normalized_content in normalize(message.content)
                        for message in active_messages
                        if message.role.value == "user"
                    ):
                        excluded.append((item.memory.id, "conversation_sufficient"))
                        continue
                    key = (item.memory.memory_type, item.memory.normalized_content)
                    if key in seen:
                        excluded.append((item.memory.id, "exact_redundancy"))
                    else:
                        seen.add(key)
                        compact.append(item)
                valid = compact

            # Present exact repeated originals as one retrieval assertion while
            # retaining their canonical records. In the consolidated experiment,
            # the derived view sorts ahead of its one original fallback so the
            # shared builder can omit the view if its complete support will not fit.
            support_groups = {}
            for item in valid:
                if isinstance(item.memory, Memory):
                    key = (item.memory.memory_type, item.memory.normalized_content)
                    support_groups.setdefault(key, []).append(item)
            exact_representatives = {}
            exact_representative_ids = set()
            for group in support_groups.values():
                representative = group[0]
                support_ids = tuple(sorted((item.memory.id for item in group), key=str))
                exact_representatives[representative.memory.id] = replace(
                    representative, support_memory_ids=support_ids
                )
                exact_representative_ids.add(representative.memory.id)
                for item in group[1:]:
                    excluded.append((item.memory.id, "exact_duplicate_support"))
            valid = [
                exact_representatives.get(item.memory.id, item)
                if isinstance(item.memory, Memory)
                else item
                for item in valid
                if not isinstance(item.memory, Memory)
                or item.memory.id in exact_representative_ids
            ]

            # Keep bounded backup sources available if a derived record cannot fit.
            selected = (
                valid
                if applied == "consolidated"
                else valid[: self.settings.memory_retrieval_limit]
            )
            excluded.extend(
                (s.memory.id, "retrieval_limit")
                for s in (
                    []
                    if applied == "consolidated"
                    else valid[self.settings.memory_retrieval_limit :]
                )
            )
            if monotonic() > deadline:
                raise TimeoutError("memory_timeout")
            dependencies = tuple(
                (item.memory.id, record_dependencies(item.memory, self.repository, self.lifecycle))
                for item in selected
            )
            selected_ids = {item.memory.id for item in selected}
            reasons = dict(excluded)
            trace_candidates = []
            support_ids_by_id = {
                item.memory.id: item.support_memory_ids
                for item in selected
                if item.support_memory_ids
            }
            for record, similarity, origins in [
                (item.memory, item.similarity, item.origins) for item in candidates
            ] + [(record, None, ("exact_vector",)) for record, _ in preexcluded]:
                trace_candidates.append(
                    MemoryCandidateTrace(
                        memory_id=record.id,
                        original_ids=(
                            record.source_memory_ids
                            if isinstance(record, DerivedMemory)
                            else support_ids_by_id.get(record.id, (record.id,))
                        ),
                        origins=origins,
                        similarity=similarity,
                        disposition="selected"
                        if record.id in selected_ids
                        else reasons.get(record.id, "candidate_limit"),
                        lifecycle=self._state(owner_id, record.id).retrieval_status,
                        provenance_state="ineligible"
                        if any(r.id == record.id for r, _ in preexcluded)
                        else "eligible",
                        refresh_state="refresh_required"
                        if isinstance(record, DerivedMemory)
                        and any(r.id == record.id for r, _ in preexcluded)
                        else "active",
                        source_identity=(
                            record.source_set_identity
                            if isinstance(record, DerivedMemory)
                            else record.source_fingerprint
                        ),
                        unresolved_conflict=self._state(owner_id, record.id).unresolved_conflict,
                        freshness=freshness(record),
                        authority="derived"
                        if isinstance(record, DerivedMemory)
                        else "user_asserted",
                        dependencies=dict(dependencies).get(record.id, ()),
                        estimated_tokens=(len(record.content) + 3) // 4
                        if record.id in selected_ids
                        else 0,
                    )
                )
            return RetrievalResult(
                tuple(candidates),
                tuple(selected),
                tuple(excluded),
                diagnostics=(
                    ("scorer_failed_fixed_fallback",)
                    if applied == "fixed" and requested != "fixed"
                    else ()
                ),
                requested_variant=requested,
                applied_variant=applied,
                policy_version=policy_version,
                scores=scores,
                policy_identity=policy_identity,
                permission_dependencies=dependencies,
                trace=MemoryRetrievalTrace(
                    query=contract,
                    ranker_version=policy_identity or "fixed-v1",
                    packing_version="exact-redundancy-v1" if requested == "compact" else "whole-v1",
                    candidates=tuple(trace_candidates),
                    complete=(
                        len(originals) < contract.candidate_limit
                        and len(candidates) < contract.candidate_limit
                        and hard_exclusion_count <= len(preexcluded)
                    ),
                    hard_exclusion_count=hard_exclusion_count,
                    elapsed_ms=(monotonic() - started) * 1000,
                ),
            )
        except Exception as error:  # noqa: BLE001 - retrieval is advisory
            logger.info("Memory retrieval failed error_class=%s", type(error).__name__)
            return RetrievalResult(
                diagnostics=("retrieval_failed",),
                requested_variant=requested,
                applied_variant="empty",
                policy_version=self.settings.memory_scoring_policy_version,
            )
