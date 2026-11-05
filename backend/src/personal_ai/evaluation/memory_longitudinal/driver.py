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
)
from personal_ai.memory.services import MemoryRetriever
from personal_ai.settings import Settings

from .source import LongitudinalAuthority, LongitudinalNavigation
from .terminal import TaskBState


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


class _TaskToolHost:
    """Private simulator state. Never passed to a policy."""

    def __init__(self, task, scope, host, target, limit, authorize):
        self.task, self.scope, self.host = task, scope, host
        self.target, self.limit, self.authorize = target, limit, authorize
        self.calls, self.discoveries, self.rejected_actions = 0, 0, 0
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
        if value is None or value != self.task.current_action:
            self.rejected_actions += 1
            return None
        project = self.host.project(self.scope, self.task.project)
        self.observed = self.host.execute(
            self.scope,
            self.task.project,
            self.target.intent,
            value,
            expected_revision=project.revision,
        )
        self.target.apply(self.target.intent, action_id(value), 0, self.authorize)
        return self.observed


class PolicyTools:
    """Capability-minimal scripted-policy facade; not a Python sandbox."""

    __slots__ = ("__operations",)

    def __init__(self, operations):
        object.__setattr__(self, "_PolicyTools__operations", operations)

    def __getattribute__(self, name):
        if name == "_PolicyTools__operations":
            raise AttributeError(name)
        return object.__getattribute__(self, name)

    def __dir__(self):
        return ["apply", "current", "discover"]

    def current(self):
        operations = object.__getattribute__(self, "_PolicyTools__operations")
        return operations.current()

    def discover(self):
        operations = object.__getattribute__(self, "_PolicyTools__operations")
        return operations.discover()

    def apply(self, value):
        operations = object.__getattribute__(self, "_PolicyTools__operations")
        return operations.apply(value)


def run_policy(view, tools):
    """A resource-aware baseline and memory policy with matched authority fences."""
    remembered = consume_knowledge(view.messages)
    if remembered == "unresolved":
        return None
    if remembered is not None:
        current = tools.current()
        value = current or remembered
    else:
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
            if self.arm not in ("no_memory", "pending_diagnostic"):
                admission = self.service().admit(self.scope, task.project, self.ref, proposal)
                if admission.record_id:
                    self.record = self.repo.get_knowledge(
                        owner_id=self.scope.owner_id, memory_id=admission.record_id
                    )
                    self.setup_bytes = len(self.record.model_dump_json().encode())

    def pack(self, scope, budgets, hook=lambda _stage: None):
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
            hook("ranked")
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
            hook("packed")
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
    target = TaskBState(task.id)
    original_intent = target.intent
    for step in task.steps:
        started = trajectory_started if step.offset == 0 else perf_counter()
        source.offset = step.offset
        scope = scope_a.model_copy(update={"request_id": task.id + ":" + step.session})
        status, reason = "setup", "source_setup"
        selected, packed, consumed = (), (), ()
        observed, result = None, None
        authorization = {"check": lambda: False}
        tool_host = _TaskToolHost(
            task,
            scope,
            cohort.host,
            target,
            protocol.budgets.tool_calls,
            lambda auth=authorization: auth["check"](),
        )
        tools = PolicyTools(tool_host)
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
                        tool_host.calls += 1
                    build, selected, packed, _value, retrieval_ms, packing_ms = cohort.pack(
                        scope, protocol.budgets, hook=hook
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
                    hook("consume")
                    with request(scope):
                        view = TaskView(task.query, build.messages)
                        if packed:
                            record = next(r for r in (cohort.record,) if str(r.id) in packed)
                            service = cohort.service()
                            dependency = service.dependency(record, scope)
                            authorization["check"] = lambda current=service, ref=dependency: (
                                current.is_current(ref)
                            )
                            observed = cohort.service().consume(
                                dependency,
                                lambda _, view=view, tools=tools: run_policy(view, tools),
                            )
                            consumed = packed
                        else:
                            authorization["check"] = lambda host=cohort.host, request_scope=scope, project=task.project: bool(
                                host.project(request_scope, project)
                            )
                            with cohort.host.lease(scope, task.project):
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
                    authorization["check"] = lambda authority=source, request_query=query: (
                        authority.check(request_query) is None
                    )
                    with source.lease(query):
                        # A new action uses current source authority, independently
                        # of the earlier scripted card reader's success label.
                        messages = (ChatMessage("user", task.query),)
                        if result.answer is not None:
                            source_id = result.citations[0] if result.citations else "unattributed"
                            card = json.dumps(
                                {"historical_action": result.answer, "source": source_id},
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                            messages = (
                                *messages,
                                ChatMessage("system", "Untrusted historical context\n" + card),
                            )
                        observed = run_policy(TaskView(task.query, messages), tools)
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
        except Exception:  # noqa: BLE001 - keep partial failures and complete the attempt grid
            status, reason = "error", "attempt_exception"
        effects = [v[1] for k, v in cohort.host.effects.items() if k[2] == original_intent]
        readback = (
            target.read_back(task.id, target.target_id, original_intent)
            if step.phase == "task_b"
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
                target_id=readback.target_id if readback else None,
                target_before_version=readback.before_version if readback else None,
                target_before_state_sha256=readback.before_state_sha256 if readback else None,
                readback_task_id=readback.task_id if readback else None,
                readback_target_id=readback.target_id if readback else None,
                readback_original_intent=readback.original_intent if readback else None,
                readback_state_version=readback.state_version if readback else None,
                readback_state_sha256=readback.state_sha256 if readback else None,
                readback_action=readback.action if readback else None,
                readback_effect_id=readback.effect_id if readback else None,
                readback_effect_count=readback.effect_count if readback else None,
                readback_effect_authorized=readback.effect_authorized if readback else None,
                terminal_state_sha256=readback.state_sha256 if readback else None,
                observed_action=readback.action if readback else None,
                effect_count=len(effects),
                abstained=step.phase == "task_b" and status == "complete" and observed is None,
                rediscoveries=tool_host.discoveries,
                rejected_actions=tool_host.rejected_actions,
                resources=ResourceCounters(
                    fixture_token_estimate=tokens,
                    memory_token_estimate=memory_tokens,
                    tool_calls=tool_host.calls,
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
