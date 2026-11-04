"""Sealed research orchestration through the canonical context builder only."""

import json
from dataclasses import dataclass
from time import monotonic

from pydantic import ValidationError

from personal_ai.context.builder import ContextBuilder, ContextBuildItem, ContextBuildPolicy
from personal_ai.context.contracts import ContextError
from personal_ai.context.tokens import FakeTokenCounter
from personal_ai.contracts.context_references import ContextSourceReference
from personal_ai.llm.client import ChatMessage
from personal_ai.memory.research.contracts import (
    PAGE_SIZE,
    ResearchFailure,
    ResearchResult,
    digest,
)
from personal_ai.memory.research.index import (
    browse,
    build_index,
    fetch_topic,
    fuse,
    lexical_ranks,
    terms,
    validate_index,
)
from personal_ai.memory.research.semantic import CanonicalSemanticRanks
from personal_ai.memory.research.source import FixtureAuthority


@dataclass(frozen=True)
class PackedResearchContext:
    """Transient builder result; not a reusable source or authority token."""

    index: object
    query: object
    build: object
    selected_ids: tuple[str, ...]


def card(record):
    return json.dumps(
        {
            "id": record.id,
            "source_id": record.source_id,
            "source_revision": record.source_revision,
            "source_epoch": record.source_epoch,
            "fingerprint": digest(record),
            "kind": record.kind,
            "authority": record.authority,
            "sensitivity": record.sensitivity,
            "observed_at": record.observed_at.isoformat(),
            "effective_at": record.effective_at.isoformat(),
            "expires_at": record.expires_at.isoformat(),
            "subject": record.subject,
            "value": record.value,
            "content": record.content,
            "conflict": record.conflict,
            "historical_advice_only": True,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def scripted_consumer(messages, text):
    """Read serialized cards only, with no fixture, source, rubric or effect access."""
    cards = []
    for message in messages:
        if message.role != "system" or not message.content.startswith(
            "Untrusted historical context (source-derived data"
        ):
            continue
        for line in message.content.splitlines():
            if line.startswith("{"):
                cards.append(json.loads(line))
    query_terms = set(terms(text))
    matches = sorted(
        (
            (len(query_terms & set(terms(c["content"]))), position, c)
            for position, c in enumerate(cards)
        ),
        key=lambda row: (-row[0], row[1]),
    )
    if not matches or matches[0][0] == 0:
        return None, ()
    best = matches[0][2]
    if best["conflict"]:
        supporting = [c for c in cards if c["conflict"] == best["conflict"]]
        if len(supporting) < 2:
            return None, ()
        return "unresolved", tuple(c["source_id"] for c in supporting)
    supporting = [
        c for c in cards if c["subject"] == best["subject"] and c["value"] == best["value"]
    ]
    return best["value"], tuple(c["source_id"] for c in supporting)


class MemoryNavigationResearch:
    def __init__(self, source=None, *, enabled=False):
        # Concrete fixture type is intentional: no arbitrary production issuer or
        # provider can become eligible by satisfying a structural protocol.
        if source is not None and type(source) is not FixtureAuthority:
            raise ResearchFailure("unsupported", "source_profile_unsupported")
        self.source, self.enabled = source, enabled
        self.counter = FakeTokenCounter()

    def _ready(self):
        if not self.enabled:
            raise ResearchFailure("disabled", "disabled")
        if self.source is None:
            raise ResearchFailure("unavailable", "issuer_unavailable")

    def index(self, query, *, cancelled=lambda: False):
        self._ready()
        return build_index(self.source, query, cancelled=cancelled)

    def _records(self, query, index, selected):
        result = []
        for offset in range(0, len(selected), 16):
            result.extend(self.source.fetch(index, query, selected[offset : offset + 16]))
        return tuple(result)

    def _selection(self, query, index, *, semantic=None, allow_fake=False):
        if query.arm == "fixed":
            raise ResearchFailure("unsupported", "legacy_fixed_cannot_represent_project_facts")
        if query.arm == "no_memory":
            return (), 0
        lexical = lexical_ranks(index, query.text)
        if query.arm in ("semantic", "hybrid", "hybrid_reranked"):
            # FixtureAuthority never has a trusted canonical vector issuer.
            # A caller-built rank frame, including one labelled canonical, is
            # metadata and cannot turn fixture vectors into real evidence.
            if (
                type(semantic) is not CanonicalSemanticRanks
                or semantic.origin != "fake_vector_contract"
                or not allow_fake
            ):
                raise ResearchFailure("unsupported", "real_embeddings_unavailable")
            semantic_rank = semantic.validated(query, index, allow_fake=True)
            ranked = semantic_rank if query.arm == "semantic" else fuse(lexical, semantic_rank)
        elif query.arm == "eligible_full_context":
            ranked = tuple(e.record_id for e in index.entries)
        else:
            ranked = lexical
        pages = 0
        if query.arm == "topic_hierarchical":
            roots = browse(self.source, index, query)
            targets = []
            for root in roots:
                children = browse(self.source, index, query, parent_id=root.id)
                targets.append(root)
                targets.extend(children)
            topics = {t.id: t for t in targets}
            entry_topics = {e.record_id: e.topic_id for e in index.entries}
            fetched = set()
            for identifier in ranked:
                topic = topics.get(entry_topics[identifier])
                if topic is None:
                    raise ResearchFailure("denied", "topic_ambiguous")
                page = topic.leaf_ids.index(identifier) // PAGE_SIZE
                if identifier in fetched:
                    continue
                if pages == 2:
                    break
                records = fetch_topic(self.source, index, query, topic.id, page=page)
                fetched.update(r.id for r in records)
                pages += 1
            ranked = tuple(i for i in ranked if i in fetched)
        all_records = {r.id: r for r in self.source.universe(query)}
        if query.arm == "hybrid_reranked":
            positions = {i: n for n, i in enumerate(ranked)}
            correction_for = {
                old_id: correction.id
                for correction in all_records.values()
                if correction.kind == "explicit_correction"
                for old_id in correction.supersedes
                if old_id in positions and correction.id in positions
                and correction.subject == all_records[old_id].subject
            }
            rank_position = dict(positions)
            for old_id, correction_id in correction_for.items():
                shared_position = min(positions[old_id], positions[correction_id])
                rank_position[old_id] = shared_position
                rank_position[correction_id] = shared_position
            ranked = tuple(
                sorted(
                    ranked,
                    key=lambda i: (
                        rank_position[i],
                        0 if i in correction_for.values() else 1,
                        all_records[i].authority != "tool_receipt_verified",
                        -all_records[i].effective_at.timestamp(),
                        i,
                    ),
                )
            )
        selected = list(ranked if query.arm == "eligible_full_context" else ranked[: query.top_k])
        # Contradictions are indivisible. Never fit only a convenient side.
        for identifier in tuple(selected):
            conflict = all_records[identifier].conflict
            if conflict:
                selected.extend(
                    i
                    for i, r in all_records.items()
                    if r.conflict == conflict and i not in selected
                )
        if query.arm != "eligible_full_context" and len(selected) > min(16, query.top_k):
            raise ResearchFailure("incomplete", "conflict_group_cap")
        return tuple(selected), pages

    def pack(self, query, index, selected, policy, *, protected=(), cancelled=lambda: False):
        self._ready()
        # Research accepts only a local fixture counter, no remote token counter.
        with self.source.lease(query, cancelled=cancelled):
            validate_index(self.source, index, query)
            if policy.global_input_tokens > 4096:
                raise ResearchFailure("incomplete", "global_token_cap")
            if any(i.source_class == "ai_memory" or not i.required for i in protected):
                raise ResearchFailure("unsupported", "protected_context_invalid")
            base = (ChatMessage("user", query.text or "No query"),)
            builder = ContextBuilder(
                self.counter, permission_revalidator=self.source, clock=self.source.now
            )
            reserved = builder.build(base, protected, policy, base_sensitivity="public")
            spare = max(1, policy.global_input_tokens - reserved.token_count)
            ceiling = min(
                policy.source_max_tokens["ai_memory"], query.canonical.max_tokens, 1024, spare
            )
            records = self._records(query, index, selected)
            universe = self.source.universe(query)
            selected_set = set(selected)
            if len(selected_set) != len(selected) or any(
                r.conflict
                and any(
                    other.conflict == r.conflict and other.id not in selected_set
                    for other in universe
                )
                for r in records
            ):
                raise ResearchFailure("incomplete", "conflict_group_incomplete")
            items = tuple(
                ContextBuildItem(
                    source_class="ai_memory",
                    provider_id="synthetic_memory_navigation",
                    source_version="memory-navigation-index-v1",
                    source_id=r.source_id,
                    item_id=r.id,
                    content=card(r),
                    authority="derived",
                    sensitivity=r.sensitivity,
                    source_refs=(
                        ContextSourceReference(
                            kind="source", reference_id=r.source_id, fingerprint=digest(r)
                        ),
                    ),
                    permission_dependencies=(self.source.dependency(r),),
                    expires_at=r.expires_at,
                    atomic_group_id=r.conflict,
                    order=n,
                )
                for n, r in enumerate(records)
            )
            if query.arm == "request_aware":
                ceiling = min(ceiling, max(1, spare // 2))
            elif query.arm == "adaptive":
                # Request only the serialized selected evidence cost. The builder
                # still counts wrappers and enforces every original hard ceiling.
                estimated = self.counter.count(
                    (builder._source_message("ai_memory", items),)
                ).tokens
                ceiling = min(ceiling, max(1, estimated))
            limits = dict(policy.source_max_tokens)
            limits["ai_memory"] = ceiling
            narrowed = ContextBuildPolicy(
                global_input_tokens=policy.global_input_tokens,
                source_max_tokens=limits,
                source_priorities=dict(policy.source_priorities),
            )
            build = builder.build(base, (*protected, *items), narrowed, base_sensitivity="public")
            if query.arm == "eligible_full_context" and not set(selected).issubset(
                build.included_item_ids
            ):
                raise ResearchFailure("unsupported", "eligible_full_context_infeasible")
            validate_index(self.source, index, query)
            return PackedResearchContext(index, query, build, selected)

    def consume(self, packed, *, cancelled=lambda: False):
        """Last supported boundary, held under the simulator's mutation fence.

        There is deliberately no callback for model dispatch or external effects.
        """
        self._ready()
        with self.source.lease(packed.query, cancelled=cancelled):
            validate_index(self.source, packed.index, packed.query)
            records = self._records(packed.query, packed.index, packed.selected_ids)
            included = tuple(i for i in packed.build.included_item_ids if i in packed.selected_ids)
            expected_cards = tuple(card(r) for r in records if r.id in included)
            actual_cards = tuple(
                line
                for message in packed.build.messages
                if message.role == "system"
                and message.content.startswith("Untrusted historical context (source-derived data")
                for line in message.content.splitlines()
                if line.startswith("{")
            )
            if actual_cards != expected_cards:
                raise ResearchFailure("denied", "packed_content_changed")
            answer = scripted_consumer(packed.build.messages, packed.query.text)
            validate_index(self.source, packed.index, packed.query)
            return answer

    def run(
        self,
        query,
        policy,
        *,
        cancelled=lambda: False,
        hook=lambda stage: None,
        semantic=None,
        allow_fake_vectors_for_contract_test=False,
        protected=(),
    ):
        started = monotonic()
        index_bytes = 0
        build_ms = 0.0
        preflight_ms = retrieval_ms = packing_ms = consume_ms = 0.0
        try:
            self._ready()
            # Each stage shares one original deadline, rather than renewing it.
            query = type(query).model_validate(query.model_dump(mode="python"))
            query = query.model_copy(
                update={
                    "canonical": query.canonical.model_copy(
                        update={
                            "deadline": min(
                                query.canonical.deadline,
                                started + query.canonical.time_budget_seconds,
                            )
                        }
                    )
                }
            )
            # Keep the same source and grant preflight, but the null baseline
            # performs no index build or memory retrieval work.
            phase_started = monotonic()
            self.source.check(query, cancelled=cancelled)
            preflight_ms = (monotonic() - phase_started) * 1000
            if query.arm == "no_memory":
                return ResearchResult(
                    status="ok",
                    reason="complete",
                    preflight_ms=preflight_ms,
                    elapsed_ms=(monotonic() - started) * 1000,
                )
            if query.arm == "fixed":
                self._selection(query, None, semantic=semantic)
            index_started = monotonic()
            index = self.index(query, cancelled=cancelled)
            build_ms = (monotonic() - index_started) * 1000
            index_bytes = len(index.model_dump_json().encode())
            phase_started = monotonic()
            try:
                with self.source.lease(query, cancelled=cancelled):
                    selected, pages = self._selection(
                        query,
                        index,
                        semantic=semantic,
                        allow_fake=allow_fake_vectors_for_contract_test,
                    )
            finally:
                retrieval_ms = (monotonic() - phase_started) * 1000
            hook("ranked")
            phase_started = monotonic()
            try:
                packed = self.pack(
                    query, index, selected, policy, protected=protected, cancelled=cancelled
                )
            finally:
                packing_ms = (monotonic() - phase_started) * 1000
            hook("packed")
            hook("consume")
            phase_started = monotonic()
            try:
                answer, citations = self.consume(packed, cancelled=cancelled)
                # Synthetic final disclosure seam: still no transport or model send.
                hook("pre_send")
                with self.source.lease(query, cancelled=cancelled):
                    validate_index(self.source, index, query)
            finally:
                consume_ms = (monotonic() - phase_started) * 1000
            return ResearchResult(
                status="ok",
                reason="complete",
                generation=index.generation,
                selected_ids=selected,
                packed_ids=tuple(i for i in packed.build.included_item_ids if i in selected),
                tokens=packed.build.token_count,
                memory_tokens=packed.build.memory_tokens,
                index_bytes=index_bytes,
                index_build_ms=build_ms,
                preflight_ms=preflight_ms,
                retrieval_ms=retrieval_ms,
                packing_ms=packing_ms,
                consume_ms=consume_ms,
                elapsed_ms=(monotonic() - started) * 1000,
                fetch_pages=pages,
                answer=answer,
                citations=citations,
            )
        except ResearchFailure as exc:
            return ResearchResult(
                status=exc.status,
                reason=exc.reason,
                index_bytes=index_bytes,
                index_build_ms=build_ms,
                preflight_ms=preflight_ms,
                retrieval_ms=retrieval_ms,
                packing_ms=packing_ms,
                consume_ms=consume_ms,
                elapsed_ms=(monotonic() - started) * 1000,
            )
        except ValidationError:
            return ResearchResult(
                status="denied", reason="query_invalid", index_bytes=index_bytes,
                index_build_ms=build_ms, preflight_ms=preflight_ms,
                retrieval_ms=retrieval_ms, packing_ms=packing_ms, consume_ms=consume_ms,
                elapsed_ms=(monotonic() - started) * 1000
            )
        except ContextError:
            return ResearchResult(
                status="denied",
                reason="context_unavailable",
                index_bytes=index_bytes,
                index_build_ms=build_ms,
                preflight_ms=preflight_ms,
                retrieval_ms=retrieval_ms,
                packing_ms=packing_ms,
                consume_ms=consume_ms,
                elapsed_ms=(monotonic() - started) * 1000,
            )
