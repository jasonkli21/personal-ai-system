"""Additional sealed public fixture host, isolated from application composition."""

from datetime import timedelta
from threading import RLock
from uuid import uuid4

from personal_ai.context.tokens import FakeTokenCounter
from personal_ai.evaluation.knowledge_runtime import NOW
from personal_ai.memory.research.contracts import ResearchFailure, ResearchScope, digest
from personal_ai.memory.research.engine import MemoryNavigationResearch
from personal_ai.memory.research.source import FixtureAuthority

from .dataset import SOURCE_SHA256, load_sources


class LongitudinalAuthority(FixtureAuthority):
    """Monotonic state survives session/index replacement, not cold issuer restore."""

    def __init__(self, task_id):
        self.task = next(t for t in load_sources().tasks if t.id == task_id)
        self._records = {r.id: r for r in self.task.records}
        self._grants = frozenset({(digest(self.task.scope), self.task.project)})
        self.offset = 0
        self._clock = lambda: NOW + timedelta(seconds=self.offset)
        self._lock = RLock()
        self._revision = 1
        self._instance = uuid4().hex
        self._tombstones, self._purged = set(), set()
        self._available = True
        self.project_revision = "rev-one"
        self.permission_epoch = 1
        self.effect_host = None

    def generation(self, query):
        return digest([SOURCE_SHA256, super().generation(query)])

    def eligible(self, record, query):
        # The synthetic issuer only verifies a closed fact envelope. Text that
        # claims evaluator authority or unobserved success cannot become fact.
        templates = (
            f"{record.subject} historical action {record.value}.",
            f"{record.subject} corrected historical action {record.value}.",
            f"{record.subject} disputed historical action {record.value}.",
        )
        return (
            super().eligible(record, query)
            and self.task.evidence_outcome == "success"
            and record.content in templates
            and record.source_revision == self.project_revision
        )

    def is_current(self, dependency):
        if not super().is_current(dependency):
            return False
        record = self._records.get(dependency.entity_ref.entity_id)
        return record is not None and record.source_revision == self.project_revision

    def mutate(self, event):
        action, target = event.action, event.target
        if action in ("forget", "forget_restore"):
            snapshot = dict(self._records)
            self.transition("forget", target)
            if action == "forget_restore":
                self._records = snapshot  # Tombstones/authority are deliberately not restored.
        elif action == "revision":
            self.project_revision = "rev-two"
            self._revision += 1
        elif (
            action in ("owner", "workspace", "application", "actor", "project_denied")
            or action == "revoke_grant"
        ):
            self.revoke_grant(self.task.scope.model_dump(), self.task.project)
            self.permission_epoch += 1
        elif action == "regrant":
            self.revoke_grant(self.task.scope.model_dump(), self.task.project)
            self.regrant(self.task.scope.model_dump(), self.task.project)
            self.permission_epoch += 2
        elif action == "advance":
            self.offset = 3
            self._revision += 1
        elif action == "stale":
            self._revision += 1
        elif action == "partial":
            raise ResearchFailure("incomplete", "partial_source_page")
        elif action == "cancel":
            raise ResearchFailure("cancelled", "cancelled")
        elif action == "timeout":
            raise ResearchFailure("timed_out", "original_deadline")
        elif action == "refresh_interrupted":
            raise RuntimeError("interrupted_checkpoint")
        elif action != "tight":
            raise ValueError("mutation_unsupported")


class LongitudinalNavigation(MemoryNavigationResearch):
    """Reuse navigation and packing, admitting only this sealed fixture type."""

    def __init__(self, source=None, *, enabled=False):
        if source is not None and type(source) is not LongitudinalAuthority:
            raise ResearchFailure("unsupported", "sealed_source_required")
        self.source, self.enabled, self.counter = source, enabled, FakeTokenCounter()

    def _ready(self):
        super()._ready()
        if type(self.source) is not LongitudinalAuthority:
            raise ResearchFailure("unsupported", "sealed_source_required")
        # No arbitrary substitute corpus or untrusted supplied manifest is accepted.
        ResearchScope.model_validate(self.source.task.scope.model_dump())
