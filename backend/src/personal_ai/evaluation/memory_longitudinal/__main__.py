"""Explicit opt-in offline evaluation and fresh-process replay verification."""

import argparse
import json
from pathlib import Path
from uuid import uuid4

from personal_ai.memory.research.experiments.artifacts import (
    append_decision,
    checked_json,
    immutable_write,
    read_decisions,
    validate_grid,
    verify_package,
)
from personal_ai.memory.research.experiments.contracts import (
    AttemptReceipt,
    EvaluationReport,
    ResearchDecision,
    RunManifest,
    canonical,
    digest,
)
from personal_ai.memory.research.experiments.decisions import EvidenceRegistry, evaluate_decision

from .campaign import campaign
from .dataset import load_sources
from .scorer import analyze
from .study import ROOT, make_run, render_report, replay, verify_git_provenance


def blocked_plans(run, decision):
    # No independent issuer exists here. Retain a concrete blocked canary request,
    # not fabricated reviewer approval or an executable runtime canary.
    baseline = next(p for p in run.policies if p.arm == run.protocol.primary.baseline)
    canary = {
        "version": "memory-offline-canary-request-v1",
        "status": "blocked",
        "decision_sha256": digest(decision),
        "required": "independent_review",
        "stages": [4, 12, 48],
        "stop": "any_safety_failure_or_unknown_resource",
        "rollback_policy_sha256": digest(baseline),
        "effective_policy": "unchanged",
    }
    rollback = {
        "version": "memory-offline-rollback-request-v1",
        "status": "dry_run_only",
        "stable_policy_sha256": digest(baseline),
        "receipts": "retained",
        "forget_authority": "canonical_owner_unchanged",
        "effective_policy": "unchanged",
    }
    return canary, rollback


def verify(directory):
    verify_package(directory)
    run = RunManifest.model_validate(checked_json(directory / "run.json"))
    verify_git_provenance(run, ROOT)
    report = EvaluationReport.model_validate(checked_json(directory / "report.json"))
    rows = tuple(
        AttemptReceipt.model_validate(r) for r in checked_json(directory / "receipts.json")
    )
    validate_grid(run, rows, load_sources().tasks)
    checks = campaign()
    rebuilt, metrics = analyze(run, rows, checks)
    if digest(rebuilt) != digest(report):
        raise ValueError("report_custody_mismatch")
    decision = ResearchDecision.model_validate(checked_json(directory / "decision.json"))
    registry = EvidenceRegistry(
        verified_runs=frozenset({digest(run)}), verified_reports=frozenset({digest(report)})
    )
    expected = evaluate_decision(run, report, registry=registry)
    # The CLI installs no reviewer issuer. A package cannot grant one to itself.
    if decision != expected:
        # An externally retained failure may make a proposal more restrictive.
        blocked = evaluate_decision(
            run,
            report,
            registry=EvidenceRegistry(
                verified_runs=registry.verified_runs,
                verified_reports=registry.verified_reports,
                vetoed_evidence=frozenset({expected.evidence_key}),
            ),
        )
        if decision != blocked:
            raise ValueError("decision_custody_mismatch")
    canary, rollback = blocked_plans(run, decision)
    for name, value in (
        ("metrics.json", metrics),
        ("faults.json", list(checks)),
        ("canary.json", canary),
        ("rollback.json", rollback),
    ):
        if digest(checked_json(directory / name)) != digest(value):
            raise ValueError("summary_or_plan_custody_mismatch")
    if (directory / "report.md").read_text() != render_report(run, report, metrics, decision):
        raise ValueError("human_report_custody_mismatch")
    fresh = replay(run)
    fresh_report, _ = analyze(run, fresh, checks)
    if (
        fresh_report.semantic_replay_sha256 != report.semantic_replay_sha256
        or not fresh_report.replay_match
        or fresh_report.safety_failures
        or any(value != "pass" for _, value in checks)
    ):
        raise ValueError("fresh_process_replay_failed")
    return {
        "verified": True,
        "run_sha256": digest(run),
        "semantic_sha256": report.semantic_replay_sha256,
        "rows": len(rows),
    }


def evaluate(output=None):
    run = make_run()
    directory = (output or ROOT / "artifacts/memory-research") / digest(run) / uuid4().hex
    # Immutable author protocol/identity is saved before the first measured trial.
    inventory = {"run.json": immutable_write(directory / "run.json", canonical(run))}
    rows = replay(run)
    checks = campaign()
    report, metrics = analyze(run, rows, checks)
    ledger = (output or ROOT / "artifacts/memory-research") / "decisions"
    prior = read_decisions(ledger)
    failures = [d for d in prior if d.status in ("blocked", "rejected")]
    registry = EvidenceRegistry(
        verified_runs=frozenset({digest(run)}),
        verified_reports=frozenset({digest(report)}),
        vetoed_evidence=frozenset(d.evidence_key for d in failures),
    )
    decision = evaluate_decision(run, report, registry=registry)
    canary, rollback = blocked_plans(run, decision)
    values = {
        "receipts.json": [r.model_dump(mode="json") for r in rows],
        "report.json": report.model_dump(mode="json"),
        "metrics.json": metrics,
        "decision.json": decision.model_dump(mode="json"),
        "canary.json": canary,
        "rollback.json": rollback,
        "faults.json": list(checks),
    }
    for name, value in values.items():
        inventory[name] = immutable_write(directory / name, canonical(value))
    inventory["report.md"] = immutable_write(
        directory / "report.md", render_report(run, report, metrics, decision).encode()
    )
    immutable_write(
        directory / "package.json",
        canonical(
            {
                "version": "memory-replay-package-v1",
                "files": inventory,
            }
        ),
    )
    verify_package(directory)
    ledger_decision = decision.model_copy(
        update={
            "previous_decision": digest(prior[-1]) if prior else None,
            "prior_failure": digest(failures[-1]) if failures else None,
        }
    )
    append_decision(ledger, ledger_decision)
    if (
        not report.replay_match
        or report.safety_failures
        or any(status != "pass" for _, status in checks)
    ):
        raise ValueError(f"research_safety_or_replay_veto:{directory}")
    return {
        "package": str(directory),
        "run_sha256": digest(run),
        "rows": len(rows),
        "semantic_sha256": report.semantic_replay_sha256,
        "decision": decision.status,
        "comparisons": [c.model_dump(mode="json") for c in report.comparisons],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify", type=Path, help="Verify package and replay in this fresh process"
    )
    parser.add_argument("--output", type=Path, help="Local generated artifact root")
    args = parser.parse_args()
    value = verify(args.verify) if args.verify else evaluate(args.output)
    print(json.dumps(value, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
