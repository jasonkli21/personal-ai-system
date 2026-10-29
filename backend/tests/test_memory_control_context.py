"""Committed user forget traverses real shared packing, reuse and send barriers."""

import asyncio
from datetime import timedelta
from hashlib import sha256
from time import monotonic
from uuid import uuid4

import pytest

from personal_ai.context import ContextAssembler, ContextError
from personal_ai.context.authority import permission_dependencies_current
from personal_ai.context.tokens import FakeTokenCounter
from personal_ai.contracts.context_references import ContextSourceSnapshot
from personal_ai.entities import Conversation, Message
from personal_ai.evaluation.control_runtime import ControlRuntime
from personal_ai.evaluation.memory_control import mutation
from personal_ai.evaluation.memory_knowledge import memory_query
from personal_ai.llm import ChatMessage
from personal_ai.memory.dependencies import MemoryPermissionRevalidator
from personal_ai.services import ChatTurnService
from personal_ai.services.chat.service import _PreparedTurn
from personal_ai.storage.fake import InMemoryConversationRepository, InMemoryMessageRepository


def setup():
    rt = ControlRuntime()
    validator = MemoryPermissionRevalidator(
        rt.settings, rt.memories, rt.memories.messages, rt.lifecycle, knowledge_service=rt.knowledge
    )
    return rt, validator


@pytest.mark.parametrize("when", ["before_pack", "final_count"])
def test_forget_cached_retrieval_and_final_token_count_suppresses_input(when):
    rt, validator = setup()
    with rt.user():
        record = rt.seed()
        retrieval = rt.knowledge.select(memory_query(rt.scope, rt.authority))
        dependency = retrieval.permission_dependencies[0][1][0]
        pending = Message(
            id=uuid4(),
            owner_id=rt.scope.owner_id,
            application_id=rt.scope.application_id,
            workspace_id=rt.scope.workspace_id,
            conversation_id=uuid4(),
            role="user",
            status="completed",
            content="Next task",
            created_at=rt.now,
        )
        counter = FakeTokenCounter()
        if when == "before_pack":
            assert rt.service.mutate("forget", record.id, mutation()).status == "applied"
        else:
            original = counter.count
            forgotten = [False]

            def count(*args, **kwargs):
                result = original(*args, **kwargs)
                # Revoke when the count actually includes the selected record.
                text = str(args)
                if record.proposal.claim in text and not forgotten[0]:
                    forgotten[0] = True
                    assert rt.service.mutate("forget", record.id, mutation()).status == "applied"
                return result

            counter.count = count
        assembler = ContextAssembler(rt.settings, counter, permission_revalidator=validator)
        try:
            packed = assembler.assemble(
                [], pending, retrieval=retrieval, refresh=False, clock=lambda: rt.now
            )
            assert record.id not in packed.selected_memory_ids
        except ContextError as error:
            # The assembler may reject the entire pack after final-count invalidation.
            assert getattr(error, "code", None) == "context_source_authority_changed"
        assert not rt.knowledge.is_current(dependency)
        # History and summary reuse share this same authoritative dependency check.
        assert not permission_dependencies_current((dependency,), validator)


def test_forget_after_pack_before_provider_handoff_never_starts_later_call():
    rt, validator = setup()
    with rt.user():
        record = rt.seed()
        dep = rt.knowledge.dependency(record, rt.scope)
        conversations = InMemoryConversationRepository()
        conv = Conversation(
            id=uuid4(),
            owner_id=rt.scope.owner_id,
            workspace_id=rt.scope.workspace_id,
            title="Synthetic",
            created_at=rt.now,
            updated_at=rt.now,
        )
        conversations.create(conv)
        messages = InMemoryMessageRepository(conversations)
        user = Message(
            id=uuid4(),
            owner_id=rt.scope.owner_id,
            workspace_id=rt.scope.workspace_id,
            conversation_id=conv.id,
            role="user",
            status="completed",
            content="Next task",
            created_at=rt.now,
        )
        assistant = Message(
            id=uuid4(),
            owner_id=rt.scope.owner_id,
            workspace_id=rt.scope.workspace_id,
            conversation_id=conv.id,
            parent_message_id=user.id,
            role="assistant",
            status="streaming",
            content="",
            created_at=rt.now + timedelta(microseconds=1),
        )
        messages.create(user)
        messages.create(assistant)

        class Provider:
            requires_inference_context = False
            started = False

            async def stream_events(self, *args, **kwargs):
                self.started = True
                yield None

        provider = Provider()
        chat = ChatTurnService(
            conversations,
            messages,
            provider,
            owner_id=rt.scope.owner_id,
            model="synthetic",
            context_assembler=ContextAssembler(
                rt.settings, FakeTokenCounter(), permission_revalidator=validator
            ),
        )
        snapshot = ContextSourceSnapshot(
            provider_id="memory.retrieval",
            source_id=str(record.id),
            source_version="v3",
            item_id=str(record.id),
            source_classes=("ai_memory",),
            owner_id=rt.scope.owner_id,
            application_id=rt.scope.application_id,
            workspace_id=rt.scope.workspace_id,
            content_fingerprint=sha256(record.content.encode()).hexdigest(),
            permission_dependencies=(dep,),
        )
        turn = _PreparedTurn(
            created=(user, assistant),
            assistant=assistant,
            history=(ChatMessage("system", record.content),),
            request_id="control-forget-send",
            deadline=monotonic() + 5,
            source_snapshots=(snapshot,),
        )
        assert rt.service.mutate("forget", record.id, mutation()).status == "applied"

        async def drain():
            return [event async for event in chat._stream_events(turn, [])]

        events = asyncio.run(drain())
        assert events[-1].code == "context_source_authority_changed"
        assert not provider.started


def test_authenticated_forget_during_final_marginal_count_fails_closed():
    from personal_ai.context.builder import ContextBuilder, ContextBuildItem, ContextBuildPolicy

    rt, validator = setup()
    with rt.user():
        record = rt.seed()
        dep = rt.knowledge.dependency(record, rt.scope)
        fired = [False]

        class FinalCounter(FakeTokenCounter):
            def count(self, messages):
                result = super().count(messages)
                text = "\n".join(message.content for message in messages)
                if (
                    "final-count-anchor" in text
                    and "Next task" in text
                    and record.proposal.claim not in text
                    and not fired[0]
                ):
                    fired[0] = True
                    assert rt.service.mutate("forget", record.id, mutation()).status == "applied"
                return result

        memory = ContextBuildItem(
            source_class="ai_memory",
            provider_id="memory.retrieval",
            source_id=str(record.id),
            item_id=str(record.id),
            content=record.content,
            authority="user_asserted",
            sensitivity="personal",
            permission_dependencies=(dep,),
        )
        anchor = ContextBuildItem(
            source_class="domain_current",
            provider_id="synthetic.current",
            source_id="anchor",
            item_id="anchor",
            content="final-count-anchor",
            authority="authoritative",
            sensitivity="personal",
        )
        with pytest.raises(ContextError, match="context_source_authority_changed"):
            ContextBuilder(
                FinalCounter(), permission_revalidator=validator, clock=lambda: rt.now
            ).build(
                (ChatMessage("user", "Next task"),),
                (memory, anchor),
                ContextBuildPolicy.for_settings(rt.settings, 4096),
            )
        assert fired[0]
