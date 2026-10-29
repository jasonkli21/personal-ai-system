"""Synthetic authority adapter around existing memory/context components.

Diagnostic sources are NOT runtime Memory records or deployed grant evidence.
"""

import json
import math
import re
from contextlib import contextmanager
from datetime import timedelta
from functools import cache
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from personal_ai.auth.scope import RequestScope, bind_request_scope, reset_request_scope
from personal_ai.context import ContextAssembler
from personal_ai.context.contracts import fingerprint
from personal_ai.context.tokens import FakeTokenCounter
from personal_ai.contracts.context_references import ContextPermissionDependency
from personal_ai.entities import Conversation, Message, MessageStatus
from personal_ai.evaluation.memory_task_contracts import Case, Fact, Record, Source
from personal_ai.memory.contracts import Memory, MemoryCandidate, identity, normalize
from personal_ai.memory.dependencies import MemoryPermissionRevalidator
from personal_ai.memory.fake import FakeEmbedder
from personal_ai.memory.lifecycle.policy import make_event
from personal_ai.memory.lifecycle.repositories import InMemoryMemoryLifecycleRepository
from personal_ai.memory.lifecycle.transition import transition
from personal_ai.memory.policy import RATIONALES, candidate_reason
from personal_ai.memory.repositories import InMemoryMemoryRepository
from personal_ai.settings import Settings
from personal_ai.storage.fake import InMemoryConversationRepository, InMemoryMessageRepository


class VisibleEvidence(Record):
    source_id: str
    content: str
    fact: Fact | None
    authority: str
    effective_at: str
    revision: str
    current: bool
    receipt: dict | None


class OfflineSettings(Settings):
    """Ignore ambient credentials, provider flags and user environment configuration."""

    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
    ):
        return (init_settings,)


def assertion_fact(content):
    """Deliberately narrow grammar, shared by all arms, independent of fixture IDs."""
    match = re.fullmatch(r"(?:Correction: I now prefer|I prefer) (.+)\.", content)
    return Fact(subject="response_format", value=match[1]) if match else None


def visible_source(source: Source):
    return VisibleEvidence(
        source_id=source.source_id,
        content=source.content,
        fact=assertion_fact(source.content) if source.fixed_type else source.fact,
        authority=source.authority,
        effective_at=source.effective_at.isoformat(),
        revision=source.revision,
        current=source.current,
        receipt=source.receipt.model_dump(mode="json") if source.receipt else None,
    )


class Environment:
    def __init__(self, case: Case, *, include_memories=True):
        self.case = case
        self.sources = {s.source_id: s for s in case.sources}
        self.invalid = set()
        self.epochs = {s.source_id: s.permission_epoch for s in case.sources}
        self.records = {}
        self.by_memory_id = {}
        self.conversations = InMemoryConversationRepository()
        self.messages = InMemoryMessageRepository(self.conversations)
        self.memories = InMemoryMemoryRepository(self.messages)
        self.settings = OfflineSettings(
            _env_file=None,
            ai_provider="gemini",
            ai_model="fake-chat",
            memory_enabled=True,
            memory_experiment_variant="fixed",
            memory_embedding_model="mem0-fake-v1",
            memory_embedding_dimensions=3,
            memory_max_context_tokens=case.history_tokens,
            max_context_tokens=case.maximum_context_tokens + 64,
            max_response_tokens=64,
            context_safety_margin_tokens=0,
            max_summary_tokens=64,
            summary_trigger_tokens=128,
            context_profile_max_tokens=64,
            context_domain_max_tokens=64,
            context_tool_max_tokens=64,
            context_client_max_tokens=64,
        )
        self.lifecycle = InMemoryMemoryLifecycleRepository(
            self.memories, self.messages, clock=lambda: case.clock_utc
        )
        self.embedder = FakeEmbedder(
            {case.task.instruction: (1.0, 0.0, 0.0)},
            provider="google_genai",
            model="mem0-fake-v1",
        )
        self.memory_validator = MemoryPermissionRevalidator(
            self.settings,
            self.memories,
            self.messages,
            self.lifecycle,
            clock=lambda: case.clock_utc,
        )
        for source in case.sources:
            if include_memories and source.fixed_type:
                self._create_original(source)
        with self.request():
            target = self.conversations.create(
                Conversation(
                    id=self.uid("target"),
                    owner_id=case.scope.owner_id,
                    title="Synthetic target",
                    created_at=case.clock_utc,
                    updated_at=case.clock_utc,
                )
            )
            current = [visible_source(s).model_dump(mode="json") for s in case.sources if s.current]
            # This same mandatory current evidence appears in every arm, including none.
            self.pending = Message(
                id=self.uid("pending"),
                owner_id=case.scope.owner_id,
                conversation_id=target.id,
                role="user",
                status="completed",
                content=json.dumps(
                    {"task": case.task.model_dump(mode="json"), "current": current}, sort_keys=True
                ),
                created_at=case.clock_utc,
            )
        self.counter = FakeTokenCounter()
        self.assembler = ContextAssembler(self.settings, self.counter, permission_revalidator=self)

    def uid(self, key):
        return uuid5(NAMESPACE_URL, "mem0:" + self.case.case_id + ":" + key)

    @contextmanager
    def request(self, scope=None):
        scope = scope or self.case.scope
        token = bind_request_scope(
            RequestScope(
                owner_id=scope.owner_id,
                application_id=scope.application_id,
                workspace_id=scope.workspace_id,
                request_id="mem0-synthetic",
            )
        )
        try:
            yield
        finally:
            reset_request_scope(token)

    def _create_original(self, source):
        with self.request(source.scope):
            conversation = self.conversations.create(
                Conversation(
                    id=self.uid(source.source_id + ":conversation"),
                    owner_id=source.scope.owner_id,
                    title="Synthetic source",
                    created_at=source.observed_at,
                    updated_at=source.observed_at,
                )
            )
            user = self.messages.create(
                Message(
                    id=self.uid(source.source_id + ":user"),
                    owner_id=source.scope.owner_id,
                    conversation_id=conversation.id,
                    role="user",
                    status="completed",
                    content=source.content,
                    created_at=source.observed_at,
                )
            )
            assistant = self.messages.create(
                Message(
                    id=self.uid(source.source_id + ":assistant"),
                    owner_id=source.scope.owner_id,
                    conversation_id=conversation.id,
                    role="assistant",
                    status="completed",
                    content="Acknowledged.",
                    parent_message_id=user.id,
                    created_at=source.observed_at + timedelta(seconds=1),
                )
            )
            candidate = MemoryCandidate(
                memory_type=source.fixed_type,
                content=source.content,
                confidence=0.95,
                source_message_ids=(user.id,),
                rationale_code=RATIONALES[source.fixed_type],
            )
            reason = candidate_reason(candidate, [user], self.settings)
            if reason:
                raise ValueError("inadmissible_fixed_fixture:" + reason)
            source_hash = fingerprint([user])
            record = Memory(
                **candidate.model_dump(exclude={"effective_at"}),
                id=identity(source.scope.owner_id, source_hash, candidate),
                owner_id=source.scope.owner_id,
                normalized_content=normalize(source.content),
                source_conversation_id=conversation.id,
                source_turn_id=assistant.id,
                source_fingerprint=source_hash,
                observed_at=source.observed_at,
                effective_at=source.observed_at,
                created_at=source.observed_at,
                embedding=(source.similarity, math.sqrt(1 - source.similarity**2), 0.0),
                embedding_model="mem0-fake-v1",
                embedding_dimensions=3,
            )
            record, _ = self.memories.create(record)
            self.records[source.source_id] = record
            self.by_memory_id[str(record.id)] = source.source_id

    def eligible(self, key, *, history=True):
        # Per-read memoization bounds diamond-shaped provenance graphs. Never
        # retain the cache across source/epoch transitions.
        @cache
        def check(source_key):
            source = self.sources[source_key]
            return (
                source.scope == self.case.scope
                and source.granted
                and source_key not in self.invalid
                and source.privacy == "synthetic_public"
                and source.observed_at <= self.case.clock_utc
                and source.effective_at <= self.case.task.as_of
                and (source.expires_at is None or source.expires_at > self.case.clock_utc)
                and (not history or not source.current and self.case.task.use_memory)
                and all(check(k) for k in source.support_ids)
            )

        return check(key)

    def eligibility_reason(self, key):
        source = self.sources[key]
        if source.current:
            return "current_context"
        if source.scope != self.case.scope:
            return "scope_or_branch_mismatch"
        if not source.granted or key in self.invalid:
            return "source_revoked_or_invalidated"
        if source.privacy != "synthetic_public":
            return "sensitive"
        if source.observed_at > self.case.clock_utc or source.effective_at > self.case.task.as_of:
            return "future_or_outside_as_of"
        if source.expires_at is not None and source.expires_at <= self.case.clock_utc:
            return "expired"
        if not self.case.task.use_memory:
            return "explicit_memory_exclusion"
        if not all(self.eligible(k) for k in source.support_ids):
            return "support_invalidated"
        return "eligible"

    def dependency(self, key):
        return ContextPermissionDependency(
            permission_id="mem0_synthetic_source",
            version=self.version(key),
            purpose="synthetic benchmark source reuse",
            owner_id=self.case.scope.owner_id,
        )

    def version(self, key):
        source = self.sources[key]
        return sha256((source.model_dump_json() + str(self.epochs[key])).encode()).hexdigest()

    def is_current(self, dependency):
        if dependency.permission_id == "mem0_synthetic_source":
            return any(
                self.eligible(key) and self.version(key) == dependency.version
                for key in self.sources
            )
        ref = dependency.entity_ref
        key = self.by_memory_id.get(ref.entity_id) if ref else None
        return bool(key and self.eligible(key) and self.memory_validator.is_current(dependency))

    def apply(self, stage):
        for change in self.case.changes:
            if change.stage != stage:
                continue
            key = change.source_id
            self.invalid.add(key)
            self.epochs[key] += 1
            record = self.records.get(key)
            if record is None:
                continue
            with self.request(self.sources[key].scope):
                if change.kind == "branch":
                    user = self.messages._messages[record.source_message_ids[0]]
                    self.messages._messages[user.id] = user.model_copy(
                        update={"status": MessageStatus.SUPERSEDED}
                    )
                else:
                    state = self.lifecycle.get_state(owner_id=record.owner_id, memory_id=record.id)
                    event = make_event(
                        owner_id=record.owner_id,
                        memory_id=record.id,
                        event_type="forgotten",
                        reason_code="mem0_synthetic_source_transition",
                        policy_version="mem0-v1",
                        idempotency_key=f"{key}:{stage}:{change.kind}",
                        expected_state_version=state.state_version,
                        occurred_at=self.case.clock_utc,
                    )
                    # Exercise canonical transition for explicit user-forget simulation;
                    # automatic forgetting intentionally protects stable preferences.
                    self.lifecycle.states[(record.owner_id, record.id)] = transition(state, event)

    def fixed_visible(self, key):
        record = self.records[key]
        return VisibleEvidence(
            source_id=key,
            content=record.content,
            fact=assertion_fact(record.content),
            authority="user_asserted",
            effective_at=record.effective_at.isoformat(),
            revision="user-statement",
            current=False,
            receipt=None,
        )
