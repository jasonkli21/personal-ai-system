"""Finite scripted task policy and fake tools. No access to case, gold or rubric."""

from personal_ai.evaluation.memory_task_contracts import ActionTrace, Record, Task
from personal_ai.evaluation.memory_task_runtime import VisibleEvidence


class DriverInput(Record):
    task: Task
    evidence: tuple[VisibleEvidence, ...]


class SyntheticTools:
    """No I/O or writes. Receipt resolution is against visible, bounded evidence."""

    @staticmethod
    def receipt(evidence, revision):
        receipt = evidence.receipt
        if not receipt or evidence.authority != "tool_receipt_verified":
            return "unknown", None
        if (
            receipt["revision"] != revision
            or evidence.revision != revision
            or receipt["command"] != evidence.fact.value
        ):
            return "unknown", None
        return {
            "success": "verified",
            "failure": "failed",
            "uncertain": "unknown",
            "partial": "unknown",
        }[receipt["outcome"]], receipt["receipt_id"]

    @staticmethod
    def reconcile(evidence, subject):
        observations = [
            s
            for s in evidence
            if s.current
            and s.fact
            and s.fact.subject == subject
            and s.authority == "canonical_domain_version"
        ]
        if len(observations) != 1:
            return None, ()
        observation = observations[0]
        messages = {
            "uncertain": "effect_uncertain_inspect_original_key",
            "success": "effect_confirmed_observed_original_key",
            "failure": "effect_failed_inspect_original_key",
        }
        return messages.get(observation.fact.value), (observation,)


def run_driver(view: DriverInput) -> tuple[ActionTrace, ...]:
    task = view.task
    actions = []

    def act(
        name,
        evidence=(),
        answer=None,
        verification="not_applicable",
        receipt_id=None,
        arguments=None,
    ):
        if name not in task.allowed_actions:
            raise ValueError("scripted_tool_not_allowed:" + name)
        actions.append(
            ActionTrace(
                action=name,
                arguments=arguments or {},
                evidence_ids=tuple(s.source_id for s in evidence),
                revision=task.revision,
                receipt_id=receipt_id,
                verification=verification,
                answer=answer,
            )
        )

    act("inspect")
    if task.operation == "compute":
        act("answer", answer=str(sum(task.operands)))
        return tuple(actions)
    sources = [
        s
        for s in view.evidence
        if s.fact
        and s.fact.subject == task.subject
        and s.authority not in ("untrusted_external", "model_proposed")
    ]
    sources.sort(key=lambda s: (s.current, s.effective_at, s.source_id), reverse=True)
    if task.operation in ("current", "workflow"):
        act("read_current")
    if task.operation == "current":
        sources = [s for s in sources if s.current and s.authority == "canonical_domain_version"]
    if task.operation == "reconcile":
        answer, observed = SyntheticTools.reconcile(view.evidence, task.subject)
        act("reconcile", observed, verification="unknown")
        if answer is None:
            act("abstain", verification="unknown")
        else:
            act("answer", observed, answer=answer)
        return tuple(actions)
    if task.operation == "workflow":
        act("check_revision")
        heads = [
            s.fact.value
            for s in view.evidence
            if s.current
            and s.fact
            and s.fact.subject == "revision"
            and s.authority == "canonical_domain_version"
        ]
        if heads != [task.revision]:
            act("abstain", verification="unknown")
            return tuple(actions)
        sources = [s for s in sources if s.fact.kind in ("workflow", "failure_lesson")]
        for source in sources:
            verification, receipt_id = SyntheticTools.receipt(source, task.revision)
            if verification == "verified":
                act(
                    "reuse_workflow",
                    [source],
                    verification="verified",
                    receipt_id=receipt_id,
                    arguments={"command": source.fact.value},
                )
                act("answer", [source], answer=source.fact.value)
                return tuple(actions)
            if verification == "failed":
                act("avoid_failed", [source], verification="failed", receipt_id=receipt_id)
                act("answer", [source], answer="avoid:" + source.fact.value)
                return tuple(actions)
        act("abstain", verification="unknown")
    elif sources:
        source = sources[0]
        if task.operation == "recall" and source.fact.subject != "response_format":
            act("check_revision", [source])
            if source.revision != task.revision:
                act("abstain", verification="unknown")
                return tuple(actions)
        act("answer", [source], answer=source.fact.value)
    else:
        act("abstain", verification="unknown")
    return tuple(actions)
