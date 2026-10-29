"""Versioned synthetic control probes. Scoring expectations never enter the runtime."""

import json
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from importlib.resources import files
from statistics import median
from time import perf_counter
from uuid import uuid4

from pydantic import Field

from personal_ai.evaluation.control_runtime import ControlRuntime
from personal_ai.evaluation.knowledge_runtime import request
from personal_ai.memory.control_contracts import (
    MutationInput,
    ProposalInput,
    ReviewInput,
    SearchInput,
)
from personal_ai.memory.control_tools import MemoryToolRun
from personal_ai.memory.knowledge import Strict


class Probe(Strict):
    scenario: str
    value: str = ""


class Observation(Strict):
    status: str
    state_version: int
    knowledge_count: int
    disclosed: int = 0
    pending_count: int = 0
    receipts: int = 0
    replayed: bool = False


class Case(Strict):
    id: str
    family: str
    split: str
    threat: str
    negative_control: str
    input: Probe
    expected: Observation


class Corpus(Strict):
    version: str
    cases: tuple[Case, ...] = Field(min_length=24)


def candidate(claim="Use the compact component layout."):
    return ProposalInput(kind="project_decision", title="Component layout", claim=claim)


def mutation(version=0, operation_id=None):
    return MutationInput(
        operation_id=operation_id or uuid4(), expected_version=version, confirm=True
    )


def run_probe(probe: Probe) -> Observation:
    """Only scenario inputs enter this driver; expected outcomes are scorer-only."""
    rt = ControlRuntime()
    result, replayed = None, False
    disclosed = 0
    with rt.user():
        record = rt.seed()
        scenario = probe.scenario
        if scenario == "isolation":
            changes = json.loads(probe.value)
            other = rt.scope.model_copy(update=changes)
            # Give the other actor its own project grant: exact record actor still gates reads.
            rt.authority.projects[
                (
                    (
                        other.owner_id,
                        other.application_id,
                        other.workspace_id,
                        other.acting_user_id,
                    ),
                    "repo-alpha",
                )
            ] = record.project
            with request(other):
                result = rt.for_scope(other).read(SearchInput(), memory_id=record.id)
                disclosed = len(result.items)
        elif scenario == "membership":
            rt.authority.disclosure_allowed = False
            result = rt.service.read(SearchInput(), memory_id=record.id)
        elif scenario == "poison_fields":
            result = MemoryToolRun(rt.service).invoke(
                "propose_memory", {**candidate().model_dump(), **json.loads(probe.value)}
            )
        elif scenario == "poison_text":
            result = MemoryToolRun(rt.service).invoke(
                "propose_memory", candidate(probe.value).model_dump()
            )
        elif scenario == "malformed":
            result = MemoryToolRun(rt.service).invoke("propose_memory", "{bad json")
        elif scenario == "stale_version":
            result = rt.service.mutate("forget", record.id, mutation(3))
        elif scenario == "forget":
            dep = rt.knowledge.dependency(record, rt.scope)
            result = rt.service.mutate("forget", record.id, mutation())
            disclosed = int(rt.knowledge.is_current(dep)) + len(
                rt.service.read(SearchInput(), memory_id=record.id).items
            )
        elif scenario == "double_forget":
            rt.service.mutate("forget", record.id, mutation())
            result = rt.service.mutate("forget", record.id, mutation())
        elif scenario == "revision":
            result = rt.service.mutate("revise", record.id, mutation())
        elif scenario == "review":
            p = rt.service.propose(candidate())
            result = rt.service.mutate(
                "reviewed", p.target_id, ReviewInput(**mutation().model_dump(), decision="reviewed")
            )
        elif scenario == "reject":
            p = rt.service.propose(candidate())
            result = rt.service.mutate(
                "rejected", p.target_id, ReviewInput(**mutation().model_dump(), decision="rejected")
            )
        elif scenario in {"same_key", "altered_key", "lost_ack", "before_commit", "unknown_commit"}:
            req = mutation()
            original = rt.repository.execute
            if scenario in {"lost_ack", "before_commit", "unknown_commit"}:

                def fail(*args):
                    if scenario != "before_commit":
                        original(*args)
                        if scenario == "unknown_commit":

                            def unavailable(*args):
                                raise OSError("synthetic reconciliation outage")

                            rt.repository.reconcile = unavailable
                    raise OSError("synthetic transport failure")

                rt.repository.execute = fail
            result = rt.service.mutate("forget", record.id, req)
            if scenario in {"same_key", "altered_key"}:
                result = rt.service.mutate(
                    "forget",
                    record.id,
                    req if scenario == "same_key" else mutation(2, req.operation_id),
                )
            replayed = result.replayed
        elif scenario == "source_revoke":
            edge = record.evidence.edges[0]
            rt.memories.revoke_knowledge_source(
                scope=rt.scope,
                resolver_id=edge.resolver_id,
                source_id=edge.source_id,
                expected_epoch=0,
            )
            result = rt.service.read(SearchInput(), memory_id=record.id)
            disclosed = len(result.items)
        elif scenario == "expiry":
            rt.now += timedelta(days=2)
            result = rt.service.read(SearchInput(), memory_id=record.id)
        elif scenario == "owner_delete":
            rt.memories.knowledge_fenced_owners.add(rt.scope.owner_id)
            result = rt.service.propose(candidate())
        elif scenario == "proposal_quota":
            for _ in range(32):
                rt.service.propose(candidate())
            result = rt.service.propose(candidate())
        elif scenario == "proposal_ttl":
            rt.service.propose(candidate())
            rt.now += timedelta(days=2)
            result = rt.service.proposals()
            disclosed = len(result.proposals)
        elif scenario == "run_budget":
            run = MemoryToolRun(rt.service)
            for _ in range(10):
                run.invoke("search_memory", {})
            result = run.invoke("search_memory", {})
        elif scenario == "cancel":
            run = MemoryToolRun(rt.service)
            run.cancel()
            result = run.invoke("propose_memory", candidate().model_dump())
        elif scenario == "feature_off":
            rt.settings.memory_agent_tools_enabled = False
            result = rt.service.propose(candidate())
        elif scenario == "stale_auth":
            with rt.user(principal=replace(rt.principal, authenticated_at=0)):
                result = rt.service.mutate("forget", record.id, mutation())
        elif scenario == "positive_read":
            result = rt.service.read(SearchInput(query="backend-lint"))
            disclosed = len(result.items)
        elif scenario == "negative_read":
            result = rt.service.read(SearchInput(query="unrelated tropical bananas"))
            disclosed = len(result.items)
        elif scenario == "agent_forget":
            result = MemoryToolRun(rt.service).invoke(
                "forget_memory", {"memory_id": str(record.id)}
            )
        else:
            raise ValueError("unregistered_scenario")
        version = rt.lifecycle.get_state(
            owner_id=rt.scope.owner_id, memory_id=record.id
        ).state_version
    return Observation(
        status=result.status,
        state_version=version,
        knowledge_count=len(rt.memories.knowledge_records),
        disclosed=disclosed,
        pending_count=len(rt.memories.control_proposals),
        receipts=len(rt.memories.control_receipts),
        replayed=replayed,
    )


def load_corpus():
    raw = (
        files("personal_ai.evaluation")
        .joinpath("fixtures/memory/mem2-control-v1.json")
        .read_bytes()
    )
    return Corpus.model_validate_json(raw), sha256(raw).hexdigest()


def evaluate():
    corpus, checksum = load_corpus()
    results, elapsed = [], []
    for case in corpus.cases:
        start = perf_counter()
        observation = run_probe(case.input)
        elapsed.append((perf_counter() - start) * 1000)
        results.append(
            {
                "id": case.id,
                "passed": observation == case.expected,
                "observed": observation.model_dump(),
            }
        )
    unauthorized_reads = sum(
        r["observed"]["disclosed"]
        for r, c in zip(results, corpus.cases, strict=True)
        if c.family == "authorization"
    )
    unauthorized_writes = sum(
        r["observed"]["state_version"] + max(0, r["observed"]["knowledge_count"] - 1)
        for r, c in zip(results, corpus.cases, strict=True)
        if c.family in {"authorization", "proposal_injection"}
    )
    false_successes = sum(
        r["observed"]["status"] == "applied" and r["observed"]["state_version"] != 1
        for r in results
    )
    return {
        "version": corpus.version,
        "classification": "synthetic/offline; no model utility evidence",
        "checksum": checksum,
        "cases": len(results),
        "safety": {
            "unauthorized_reads": unauthorized_reads,
            "unauthorized_writes": unauthorized_writes,
            "false_successes": false_successes,
        },
        "unsupported_revision_abstentions": sum(
            r["observed"]["status"] == "unsupported_evidence_source" for r in results
        ),
        "passed": sum(r["passed"] for r in results),
        "splits": {
            split: sum(c.split == split for c in corpus.cases)
            for split in sorted({c.split for c in corpus.cases})
        },
        "latency_ms": {
            "p50": median(elapsed),
            "p95": sorted(elapsed)[int(len(elapsed) * 0.95) - 1],
            "max": max(elapsed),
        },
        "results": results,
    }


if __name__ == "__main__":
    report = evaluate()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] == report["cases"] else 1)
