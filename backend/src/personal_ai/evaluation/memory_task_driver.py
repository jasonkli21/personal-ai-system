"""Finite scripted task policy and fake tools. No access to case, gold or rubric."""

from personal_ai.evaluation.memory_task_contracts import (
    ActionTrace,
    Record,
    Scope,
    Task,
)
from personal_ai.evaluation.memory_task_runtime import VisibleEvidence


class DriverInput(Record):
    task: Task
    scope: Scope
    evidence: tuple[VisibleEvidence, ...]


class SyntheticTools:
    """No I/O or writes. Receipts and observations are explicit bounded evidence."""

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
    def reconcile(evidence, task, scope):
        identity = (task.effect_key, task.effect_run_id, task.effect_command)
        if any(value is None for value in identity):
            return None, ()
        matches = []
        for source in evidence:
            observation = source.observation
            if (
                source.current
                and source.authority == "canonical_domain_version"
                and source.scope == scope
                and observation
                and observation["scope"] == scope.model_dump(mode="json")
                and observation["effect_key"] == task.effect_key
                and observation["run_id"] == task.effect_run_id
                and observation["command"] == task.effect_command
                and observation["original_revision"] == task.revision
                and source.revision == task.revision
            ):
                matches.append(source)
        if len(matches) != 1:
            return None, ()
        return matches[0].observation, (matches[0],)


class SyntheticEffectLedger:
    """Tiny evaluation-only idempotency fake; it has no external effects."""

    def __init__(self):
        self._receipts = {}
        self.effect_count = 0

    def execute_once(self, effect_key, command):
        if effect_key in self._receipts:
            return self._receipts[effect_key], False
        self.effect_count += 1
        receipt = {"effect_key": effect_key, "command": command, "effect_number": self.effect_count}
        self._receipts[effect_key] = receipt
        return receipt, True


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
        result=None,
        scope=None,
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
                result=result or {},
                scope=scope,
            )
        )

    act("inspect")
    if task.operation == "compute":
        act("answer", answer=str(sum(task.operands)))
        return tuple(actions)

    visible = [
        s
        for s in view.evidence
        if s.authority not in ("untrusted_external", "model_proposed")
        and (s.authority != "historical_derived" or s.support_verified)
    ]
    current = [
        s for s in visible
        if s.current and s.authority == "canonical_domain_version" and s.fact
    ]

    if task.operation == "reconcile":
        observation, observed = SyntheticTools.reconcile(view.evidence, task, view.scope)
        args = {
            "effect_key": task.effect_key or "",
            "run_id": task.effect_run_id or "",
            "command": task.effect_command or "",
        }
        if observation is None:
            result = {
                **args,
                "outcome": "unknown",
                "observation_id": "",
            }
            act(
                "reconcile", verification="unknown", arguments=args, result=result, scope=view.scope
            )
            act("abstain", verification="unknown")
            return tuple(actions)
        status = {
            "success": "verified",
            "failure": "failed",
            "uncertain": "unknown",
            "partial": "unknown",
        }[observation["outcome"]]
        result = {
            **args,
            "outcome": observation["outcome"],
            "observation_id": observation["observation_id"],
        }
        act(
            "reconcile",
            observed,
            verification=status,
            receipt_id=observation["observation_id"],
            arguments=args,
            result=result,
            scope=view.scope,
        )
        answers = {
            "success": "effect_confirmed_observed_original_key",
            "failure": "effect_failed_inspect_original_key",
            "uncertain": "effect_uncertain_inspect_original_key",
            "partial": "effect_uncertain_inspect_original_key",
        }
        act("answer", observed, answer=answers[observation["outcome"]])
        return tuple(actions)

    if task.operation in ("current", "workflow"):
        subject = "revision" if task.operation == "workflow" else task.subject
        current_matches = [s for s in current if s.fact.subject == subject]
        if len(current_matches) == 1:
            read = current_matches[0]
            read_result = {"subject": subject, "value": read.fact.value}
            act("read_current", [read], result=read_result, verification="verified")
        else:
            read = None
            act(
                "read_current",
                result={"subject": subject, "value": "not_found"},
                verification="verified",
            )

        if task.operation == "workflow":
            observed_revision = read.fact.value if read else "not_found"
            check_status = "verified" if observed_revision == task.revision else "failed"
            act(
                "check_revision",
                [read] if read else [],
                verification=check_status,
                arguments={"expected_revision": task.revision},
                result={"observed_revision": observed_revision},
            )
            if check_status != "verified":
                act("abstain", verification="unknown")
                return tuple(actions)
            sources = [
                s for s in visible
                if s.fact
                and s.fact.subject == task.subject
                and s.fact.kind in ("workflow", "failure_lesson")
            ]
            sources.sort(key=lambda s: (s.effective_at, s.source_id), reverse=True)
            for source in sources:
                receipt_status, receipt_id = SyntheticTools.receipt(source, task.revision)
                if receipt_status == "verified":
                    receipt = source.receipt
                    act(
                        "reuse_workflow",
                        [source],
                        verification="verified",
                        receipt_id=receipt_id,
                        arguments={"command": receipt["command"]},
                        result={"outcome": "success", "run_id": receipt["run_id"]},
                    )
                    act("answer", [source], answer=source.fact.value)
                    return tuple(actions)
                if receipt_status == "failed":
                    receipt = source.receipt
                    act(
                        "avoid_failed",
                        [source],
                        verification="failed",
                        receipt_id=receipt_id,
                        arguments={"command": receipt["command"]},
                        result={"outcome": "failure", "run_id": receipt["run_id"]},
                    )
                    act("answer", [source], answer="avoid:" + source.fact.value)
                    return tuple(actions)
            act("abstain", verification="unknown")
            return tuple(actions)

        sources = [s for s in current_matches if s.fact.subject == task.subject]
    else:
        sources = [
            s for s in visible
            if s.fact and s.fact.subject == task.subject
        ]
        if task.operation == "recall" and task.subject != "response_format" and sources:
            source = sources[0]
            status = "verified" if source.revision == task.revision else "failed"
            act(
                "check_revision",
                [source],
                verification=status,
                arguments={"expected_revision": task.revision},
                result={"observed_revision": source.revision},
            )
            if status != "verified":
                act("abstain", verification="unknown")
                return tuple(actions)

    sources.sort(key=lambda s: (s.effective_at, s.source_id), reverse=True)
    if sources:
        source = sources[0]
        claim = diagnostic_claim_from_visible(source)
        if claim is not None and claim[0] == task.subject:
            act("answer", [source], answer=claim[1])
            return tuple(actions)
    act("abstain", verification="unknown")
    return tuple(actions)


def diagnostic_claim_from_visible(source: VisibleEvidence):
    if source.fact is None:
        return None
    # Legal v1 assertions are mapped by the source adapter's narrow grammar.
    return source.fact.subject, source.fact.value
