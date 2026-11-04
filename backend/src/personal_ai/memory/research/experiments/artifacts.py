"""Bounded immutable local replay packages and append-only decision custody."""

import json
import os
from hashlib import sha256
from pathlib import Path

from personal_ai.memory.research.experiments.contracts import (
    AttemptReceipt,
    ResearchDecision,
    RunManifest,
    canonical,
    digest,
)

MAX_PACKAGE_BYTES = 16_777_216
MAX_ROWS = 9216


def immutable_write(path, payload: bytes):
    """Exclusive creation; an exact replay is idempotent, changed bytes conflict."""
    path = Path(path)
    if len(payload) > MAX_PACKAGE_BYTES:
        raise ValueError("artifact_capacity")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != payload:
            raise ValueError("immutable_artifact_conflict") from None
    return sha256(payload).hexdigest()


def checked_json(path, *, limit=MAX_PACKAGE_BYTES):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > limit:
        raise ValueError("artifact_capacity_or_link")
    payload = path.read_bytes()
    return parse_json(payload, limit=limit)


def parse_json(payload, *, limit=MAX_PACKAGE_BYTES):
    """Bound bytes, duplicate keys, nonfinite numbers and structural depth."""
    if len(payload) > limit:
        raise ValueError("artifact_capacity")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    try:
        value = json.loads(
            payload,
            object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")),
        )
    except RecursionError:
        raise ValueError("json_depth_capacity") from None
    pending = [(value, 0)]
    nodes = 0
    while pending:
        current, depth = pending.pop()
        nodes += 1
        if depth > 20 or nodes > 1_000_000:
            raise ValueError("json_structure_capacity")
        if isinstance(current, dict):
            pending.extend((v, depth + 1) for v in current.values())
        elif isinstance(current, list):
            pending.extend((v, depth + 1) for v in current)
    return value


def validate_grid(run, rows, tasks):
    run = RunManifest.model_validate(run.model_dump())
    run_hash = digest(run)
    if len(rows) > MAX_ROWS:
        raise ValueError("receipt_capacity")
    rows = tuple(AttemptReceipt.model_validate(r.model_dump()) for r in rows)
    expected = {
        (task.id, p.arm, rep, step.offset)
        for task in tasks
        for p in run.policies
        for rep in range(2)
        for step in task.steps
    }
    actual = set()
    identities = set()
    for row in rows:
        key = row.task_id, row.arm, row.repetition, row.time_step
        if row.run_sha256 != run_hash or key in actual or row.receipt_id in identities:
            raise ValueError("receipt_binding_or_duplicate")
        if row.seed != run.protocol.repetition_seeds[row.repetition]:
            raise ValueError("receipt_seed_mismatch")
        budgets = run.protocol.budgets
        if (
            row.resources.tool_calls > budgets.tool_calls
            or row.resources.fixture_token_estimate > budgets.context_tokens
            or row.resources.memory_token_estimate > budgets.memory_tokens
        ):
            raise ValueError("receipt_resource_parity")
        actual.add(key)
        identities.add(row.receipt_id)
    if actual != expected:
        raise ValueError("receipt_grid_incomplete")
    return rows


def verify_sources(run, root):
    root = Path(root).resolve()
    for entry in run.source_hashes:
        path = (root / entry.path).resolve()
        if not path.is_relative_to(root) or sha256(path.read_bytes()).hexdigest() != entry.sha256:
            raise ValueError("experiment_source_drift")


def verify_package(directory):
    """The package index is a digest inventory, not a signature or source grant."""
    directory = Path(directory)
    inventory = checked_json(directory / "package.json", limit=65536)
    if set(inventory) != {"version", "files"} or inventory["version"] != "memory-replay-package-v1":
        raise ValueError("package_schema")
    if not isinstance(inventory["files"], dict) or not 1 <= len(inventory["files"]) <= 16:
        raise ValueError("package_capacity")
    total = 0
    for name, fingerprint in inventory["files"].items():
        if name not in {
            "run.json",
            "receipts.json",
            "report.json",
            "metrics.json",
            "decision.json",
            "canary.json",
            "rollback.json",
            "report.md",
            "faults.json",
        }:
            raise ValueError("package_path")
        path = directory / name
        if path.is_symlink():
            raise ValueError("package_link")
        total += path.stat().st_size
        if total > MAX_PACKAGE_BYTES or sha256(path.read_bytes()).hexdigest() != fingerprint:
            raise ValueError("package_integrity")
    if not {"run.json", "receipts.json", "report.json"} <= inventory["files"].keys():
        raise ValueError("package_missing_inputs")
    return inventory


def append_decision(directory, decision):
    """One immutable child per chain head; competing appends conflict, not overwrite.

    Rejected evidence aliases are blocked across the entire chain. New evidence
    after a rejection must explicitly link the previous failure.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    decision = ResearchDecision.model_validate(decision.model_dump())
    chain = read_decisions(directory)
    head = digest(chain[-1]) if chain else None
    if decision.previous_decision != head:
        raise ValueError("decision_head_conflict")
    failures = [d for d in chain if d.status in ("rejected", "blocked")]
    if decision.status == "eligible_for_offline_canary" and any(
        d.evidence_key == decision.evidence_key for d in failures
    ):
        raise ValueError("failed_evidence_alias")
    if (
        failures
        and decision.evidence_key != failures[-1].evidence_key
        and (decision.prior_failure != digest(failures[-1]))
    ):
        raise ValueError("prior_failure_link_required")
    # Sequence filename uses exclusive creation, providing a bounded CAS seam.
    if len(chain) >= 128:
        raise ValueError("decision_ledger_capacity")
    immutable_write(directory / f"{len(chain):03d}.json", canonical(decision))
    return digest(decision)


def read_decisions(directory):
    directory = Path(directory)
    paths = sorted(directory.glob("*.json"))
    if len(paths) > 128:
        raise ValueError("decision_ledger_capacity")
    records = []
    head = None
    for n, path in enumerate(paths):
        if path.name != f"{n:03d}.json":
            raise ValueError("decision_chain_gap")
        item = ResearchDecision.model_validate(checked_json(path, limit=65536))
        if item.previous_decision != head:
            raise ValueError("decision_chain_tampered")
        records.append(item)
        head = digest(item)
    return tuple(records)
