"""Stateful later-action driver. Policy input is packed messages and task tools only."""

import json
from dataclasses import dataclass
from hashlib import sha256
from time import monotonic, perf_counter

from personal_ai.auth.scope import RequestScope
from personal_ai.context.builder import ContextBuilder, ContextBuildItem
from personal_ai.context.tokens import FakeTokenCounter
from personal_ai.contracts.context_references import ContextSourceReference
from personal_ai.evaluation.knowledge_runtime import (
    HermeticKnowledgeAuthority,
    messages_stub,
    request,
)
from personal_ai.evaluation.memory_knowledge import make_proposal, memory_query
from personal_ai.evaluation.memory_navigation import policy, query_for
from personal_ai.llm.client import ChatMessage
from personal_ai.memory.control_contracts import SearchInput
from personal_ai.memory.control_service import MemoryControlService
from personal_ai.memory.knowledge import KnowledgeProposal
from personal_ai.memory.knowledge_service import KnowledgeService
from personal_ai.memory.knowledge_sources import KnowledgeSourceError
from personal_ai.memory.lifecycle.repositories import InMemoryMemoryLifecycleRepository
from personal_ai.memory.repositories import InMemoryMemoryRepository
from personal_ai.memory.research.contracts import ResearchFailure
from personal_ai.memory.research.experiments.contracts import (
    AttemptReceipt,
    ResourceCounters,
    digest,
)
from personal_ai.memory.services import MemoryRetriever
from personal_ai.settings import Settings

from .source import LongitudinalAuthority, LongitudinalNavigation


class SyntheticSettings(Settings):
    """Only explicit fixture configuration; never reads credentials or host flags."""

    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
    ):
        return (init_settings,)


def action_id(value):
    return "action-" + sha256(value.encode()).hexdigest()[:24] if value is not None else None


@dataclass(frozen=True)
class TaskView:
    query: str
    current_hint: str | None
    messages: tuple


def consume_knowledge(messages):
    """Scorer, corpus, source objects and scenario labels are unavailable here."""
    for message in messages:
        if message.role == "system" and message.content.startswith("Untrusted historical context"):
            for line in message.content.splitlines():
                if line.startswith('{"historical_action":'):
                    card = json.loads(line)
                    if set(card) != {"historical_action", "source"}:
                        return None
                    return card["historical_action"]
    return None


class SimulatedTaskTools:
    """Reuses the existing hermetic original-key effect host; no external executor."""

    def __init__(self, task, source, scope, host, intent, limit):
        self.task, self.source, self.scope, self.host = task, source, scope, host
        self.intent, self.limit = intent, limit
        self.calls, self.discoveries = 0, 0
        self.rejected_actions = 0
        self.observed = None

    def current(self):
        self.calls += 1
        return self.task.current_hint

    def discover(self):
        self.calls += 1
        self.discoveries += 1
        return self.task.current_action if self.calls < self.limit else None

    def apply(self, value):
        if self.calls >= self.limit:
            return None
        self.calls += 1
        # Domain rules, permission and revision remain authoritative even if a
        # poisoned or stale historical card recommends an action.
        if value is None or value != self.task.current_action:
            self.rejected_actions += 1
            return None
        project = self.host.project(self.scope, self.task.project)
        self.observed = self.host.execute(
            self.scope,
            self.task.project,
            self.intent,
            value,
            expected_revision=project.revision,
        )
        return self.observed


def run_policy(view, tools, remembered=None):
    """A narrow scripted action proxy, without outcome labels or fixture handles."""
    current = tools.current()
    value = current or remembered or consume_knowledge(view.messages)
    if value == "unresolved":
        return None
    if value is None:
        value = tools.discover()
    return tools.apply(value) if value is not None else None


class KnowledgeCohort:
    def __init__(self, source, arm):
        self.source, self.arm = source, arm
        task = source.task
        self.scope = RequestScope(**task.scope.model_dump(), request_id=task.id + ":session-a")
        self.host = HermeticKnowledgeAuthority(self.scope)
        self.messages = messages_stub()
        self.repo = InMemoryMemoryRepository(self.messages)
        self.lifecycle = InMemoryMemoryLifecycleRepository(
            self.repo, self.messages, clock=source.now
        )
        self.settings = SyntheticSettings(
            _env_file=None,
            ai_provider="gemini",
            ai_model="synthetic",
            memory_enabled=True,
            memory_knowledge_admission_enabled=True,
            memory_knowledge_selection_enabled=True,
            memory_agent_tools_enabled=True,
            memory_max_context_tokens=1024,
        )
        self.record = None
        self.ref = None
        self.setup_bytes = 0

    def service(self):
        return KnowledgeService(
            self.settings, self.repo, self.lifecycle, self.host, clock=self.source.now
        )

    def learn(self):
        task, record = self.source.task, self.source.task.records[0]
        if record.kind == "procedure":
            proposal = make_proposal("procedure", record.value)
        else:
            proposal = KnowledgeProposal(
                kind="project_decision",
                title="Component action",
                claim=record.value,
                limitations=("Applies only to the recorded project revision.",),
            )
        with request(self.scope):
            self.ref = self.host.complete_task_a(
                self.scope, task.project, proposal, run_id=task.id + ":task-a"
            )
            if self.arm != "no_memory":
                admission = self.service().admit(self.scope, task.project, self.ref, proposal)
                if admission.record_id:
                    self.record = self.repo.get_knowledge(
                        owner_id=self.scope.owner_id, memory_id=admission.record_id
                    )
                    self.setup_bytes = len(self.record.model_dump_json().encode())

    def pack(self, scope, budgets):
        task, service = self.source.task, self.service()
        selected = []
        started = perf_counter()
        with request(scope):
            if self.arm == "tool_lookup":
                control = MemoryControlService(
                    service, None, scope, task.project, clock=self.source.now
                )
                found = control.read(SearchInput(query="", limit=8), channel="agent_tools")
                if found.status != "found":
                    raise ResearchFailure("denied", "control_read_unavailable")
                for item in found.items:
                    selected.append(
                        self.repo.get_knowledge(owner_id=scope.owner_id, memory_id=item.id)
                    )
            elif self.arm == "full_history":
                if self.record and service.reason(self.record, scope) is None:
                    selected = [self.record]
            else:
                query = memory_query(scope, self.host).model_copy(
                    update={
                        "as_of": self.source.now(),
                        "deadline": monotonic() + budgets.deadline_seconds,
                        "time_budget_seconds": budgets.deadline_seconds,
                    }
                )
                retrieval = MemoryRetriever(
                    self.settings,
                    self.repo,
                    self.messages,
                    None,
                    self.lifecycle,
                    knowledge_service=service,
                ).retrieve_knowledge(query)
                selected = [item.memory for item in retrieval.selected]
            retrieval_ms = (perf_counter() - started) * 1000
            entries = tuple(
                ContextBuildItem(
                    source_class="ai_memory",
                    provider_id="synthetic_longitudinal_knowledge",
                    source_id=str(record.id),
                    item_id=str(record.id),
                    content=json.dumps(
                        {
                            "historical_action": record.proposal.command or record.proposal.claim,
                            "source": str(record.id),
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    authority="derived",
                    sensitivity="public",
                    source_refs=(
                        ContextSourceReference(kind="source", reference_id=str(record.id)),
                    ),
                    permission_dependencies=(service.dependency(record, scope),),
                )
                for record in selected
            )
            started = perf_counter()
            build = ContextBuilder(
                FakeTokenCounter(),
                permission_revalidator=service,
                clock=self.source.now,
            ).build(
                (ChatMessage("user", task.query),),
                entries,
                policy(global_tokens=budgets.context_tokens, memory_tokens=budgets.memory_tokens),
                base_sensitivity="public",
            )
            packing_ms = (perf_counter() - started) * 1000
            packed = tuple(i for i in build.included_item_ids if i in {str(r.id) for r in selected})
            if self.arm == "full_history" and len(packed) != len(selected):
                raise ResearchFailure("unsupported", "unsupported_full_context")
            value = consume_knowledge(build.messages)
            return (
                build,
                tuple(str(r.id) for r in selected),
                packed,
                value,
                retrieval_ms,
                packing_ms,
            )


def run_trajectory(task_id, arm, run_hash, protocol, repetition):
    """Every requested step gets a row, including setup and unsupported attempts."""
    trajectory_started = perf_counter()
    source = LongitudinalAuthority(task_id)
    task = source.task
    compatible = (
        arm not in ("verified_knowledge", "tool_lookup") or task.profile == "canonical_knowledge"
    ) and (
        arm
        not in (
            "lexical",
            "topic_hierarchical",
            "adaptive",
            "semantic",
            "hybrid",
            "hybrid_reranked",
        )
        or task.profile == "navigation_fixture"
    )
    cohort = KnowledgeCohort(source, arm)
    scope_a = cohort.scope
    rows = []
    original_intent = digest([task.id, "new-target"])
    for step in task.steps:
        started = trajectory_started if step.offset == 0 else perf_counter()
        source.offset = step.offset
        scope = scope_a.model_copy(update={"request_id": task.id + ":" + step.session})
        status, reason = "setup", "source_setup"
        selected, packed, consumed = (), (), ()
        observed, result = None, None
        tools = SimulatedTaskTools(
            task, source, scope, cohort.host, original_intent, protocol.budgets.tool_calls
        )
        tokens = memory_tokens = index_bytes = 0
        index_ms = retrieval_ms = packing_ms = consumption_ms = 0.0
        fault_fired = False
        maintenance = 0

        def hook(stage):
            nonlocal fault_fired, maintenance
            if task.fault and task.fault.stage == stage and not fault_fired:
                fault_fired = True
                maintenance += 1
                try:
                    source.mutate(task.fault)
                except RuntimeError:
                    raise ResearchFailure("unavailable", "interrupted_checkpoint") from None

        try:
            for event in step.events:
                source.mutate(event)
                maintenance += 1
            if step.phase == "learn":
                if task.profile == "canonical_knowledge":
                    cohort.learn()
            elif step.phase == "task_b":
                status, reason = "complete", "terminal_observed"
                if not compatible:
                    raise ResearchFailure("unsupported", "unsupported_record_kind")
                if arm == "pending_diagnostic":
                    raise ResearchFailure("unsupported", "pending_proposal_not_approved")
                canonical = task.profile == "canonical_knowledge" and arm in (
                    "verified_knowledge",
                    "tool_lookup",
                    "full_history",
                )
                if canonical:
                    if arm == "tool_lookup":
                        tools.calls += 1
                    build, selected, packed, _value, retrieval_ms, packing_ms = cohort.pack(
                        scope, protocol.budgets
                    )
                    tokens, memory_tokens = build.token_count, build.memory_tokens
                    source.check(
                        query_for(
                            {
                                "query": task.query,
                                "scope": task.scope.model_dump(),
                                "project": task.project,
                            },
                            now=source.now(),
                        )
                    )
                    hook("ranked")
                    hook("packed")
                    hook("consume")
                    with request(scope):
                        view = TaskView(task.query, task.current_hint, build.messages)
                        if packed:
                            record = next(r for r in (cohort.record,) if str(r.id) in packed)
                            dependency = cohort.service().dependency(record, scope)
                            observed = cohort.service().consume(
                                dependency,
                                lambda _, view=view, tools=tools: run_policy(view, tools),
                            )
                            consumed = packed
                        else:
                            observed = run_policy(view, tools)
                else:
                    nav_arm = "eligible_full_context" if arm == "full_history" else arm
                    query = query_for(
                        {
                            "query": task.query,
                            "scope": task.scope.model_dump(),
                            "project": task.project,
                        },
                        nav_arm,
                        now=source.now(),
                    )
                    tight = task.fault and task.fault.action == "tight"
                    result = LongitudinalNavigation(source, enabled=True).run(
                        query,
                        policy(
                            global_tokens=protocol.budgets.context_tokens,
                            memory_tokens=1 if tight else protocol.budgets.memory_tokens,
                        ),
                        hook=hook,
                    )
                    tokens, memory_tokens = result.tokens, result.memory_tokens
                    if arm == "no_memory":
                        base = ContextBuilder(FakeTokenCounter()).build(
                            (ChatMessage("user", task.query),),
                            (),
                            policy(
                                global_tokens=protocol.budgets.context_tokens,
                                memory_tokens=protocol.budgets.memory_tokens,
                            ),
                            base_sensitivity="public",
                        )
                        tokens = base.token_count
                    index_bytes, index_ms = result.index_bytes, result.index_build_ms
                    retrieval_ms, packing_ms = result.retrieval_ms, result.packing_ms
                    consumption_ms = result.consume_ms
                    if result.status != "ok":
                        mapped = "error" if result.status == "unavailable" else result.status
                        raise ResearchFailure(mapped, result.reason)
                    selected, packed = result.selected_ids, result.packed_ids
                    # The no-memory arm skips index work, but has the same task
                    # cancellation, permission and terminal-action fence.
                    if arm == "no_memory":
                        for stage in ("ranked", "packed", "consume"):
                            hook(stage)
                    with source.lease(query):
                        # A new action uses current source authority, independently
                        # of the earlier scripted card reader's success label.
                        observed = run_policy(
                            TaskView(task.query, task.current_hint, ()),
                            tools,
                            remembered=result.answer,
                        )
                        consumed = tuple(
                            i for i in packed if source._records[i].source_id in result.citations
                        )
                if task.retry and observed:
                    replayed = cohort.host.execute(
                        scope,
                        task.project,
                        original_intent,
                        observed["command"],
                        expected_revision=observed["revision"],
                    )
                    if replayed != observed:
                        raise RuntimeError("original_intent_replay_changed")
        except (ResearchFailure, KnowledgeSourceError) as exc:
            status = exc.status if isinstance(exc, ResearchFailure) else "denied"
            status = {"unavailable": "error", "disabled": "unsupported"}.get(status, status)
            reason = exc.reason if isinstance(exc, ResearchFailure) else "knowledge_consume_denied"
            consumed, observed = (), None
        except Exception:  # noqa: BLE001 - keep partial failures and complete the attempt grid
            status, reason = "error", "attempt_exception"
            consumed, observed = (), None
        effects = [v[1] for k, v in cohort.host.effects.items() if k[2] == original_intent]
        # Setup effects have different intent keys and cannot enter target counts.
        terminal = (
            digest(
                {
                    "intent": original_intent,
                    "action": action_id(observed["command"]),
                    "revision": observed["revision"],
                }
            )
            if observed
            else None
        )
        rows.append(
            AttemptReceipt(
                run_sha256=run_hash,
                task_id=task.id,
                arm=arm,
                repetition=repetition,
                seed=protocol.repetition_seeds[repetition],
                time_step=step.offset,
                session=step.session,
                original_intent=original_intent,
                retry_of=original_intent if step.offset == 3 and task.retry else None,
                status=status,
                reason=reason,
                source_epoch=source._revision,
                permission_epoch=source.permission_epoch,
                selected=selected,
                packed=packed,
                consumed=consumed,
                terminal_state_sha256=terminal,
                observed_action=action_id(observed["command"]) if observed else None,
                effect_count=len(effects),
                abstained=step.phase == "task_b" and status == "complete" and observed is None,
                rediscoveries=tools.discoveries,
                rejected_actions=tools.rejected_actions,
                resources=ResourceCounters(
                    fixture_token_estimate=tokens,
                    memory_token_estimate=memory_tokens,
                    tool_calls=tools.calls,
                    index_bytes=index_bytes,
                    retained_bytes=cohort.setup_bytes + index_bytes,
                    maintenance_calls=maintenance,
                    elapsed_ms=(perf_counter() - started) * 1000,
                    index_build_ms=index_ms,
                    retrieval_ms=retrieval_ms,
                    packing_ms=packing_ms,
                    consumption_ms=consumption_ms,
                ),
            )
        )
    return rows
