"""Run the offline matrix and derive reproducible evidence, report and blockers."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from personal_ai.evaluation.verification.contracts import (
    VerificationMatrix,
    execution_status,
    integrated_promotion,
    release_projection,
)

ROOT = Path(__file__).resolve().parents[5]
MATRIX_PATH = Path(__file__).with_name("matrix.json")


def source_identity(root=ROOT):
    """Bind dirty/new code as well as HEAD; exclude generated evidence and personal files."""
    paths = [
        root / "Makefile",
        root / "backend/pyproject.toml",
        root / "backend/uv.lock",
        root / "frontend/package.json",
        root / "frontend/pnpm-lock.yaml",
    ]
    for directory in ("backend/src", "backend/tests", "frontend/src", "frontend/tests"):
        paths.extend(
            p
            for p in (root / directory).rglob("*")
            if p.is_file()
            and "__pycache__" not in p.parts
            and p.suffix != ".pyc"
            and p.name != ".DS_Store"
        )
    return sha256(
        json.dumps(
            [(str(p.relative_to(root)), sha256(p.read_bytes()).hexdigest()) for p in sorted(paths)],
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def render_report(report):
    release = report["release"]
    lines = [
        "# Phase 36 release verification",
        "",
        f"Tested revision: `{report['tested_revision']}`.",
        f"Configuration/source: `{report['configuration_sha256']}`.",
        f"Matrix SHA256: `{report['matrix_sha256']}`.",
        f"Recorded UTC: {report['recorded_at']}.",
        "",
        (
            f"Release ready: **{str(release['release_ready']).lower()}**. "
            "This report grants no runtime authorization or promotion."
        ),
        "",
        "Status counts: " + json.dumps(release["status_counts"], sort_keys=True) + ".",
        "",
        "Default/promoted strategy coverage: "
        + json.dumps(report["strategy_coverage"], sort_keys=True)
        + ".",
        "",
        "| ID | Boundary | Class | Severity | Status | Evidence / original authority |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["rows"]:
        lines.append(
            f"| {row['verification_id']} | {row['boundary']} | "
            f"{row['evidence_class']} | {row['severity']} | {row['status']} | "
            f"{row['evidence_ref'] or row['authority_ref']} |"
        )
    lines.extend(["", "## Capability blockers and availability", ""])
    for name, capability in sorted(release["capabilities"].items()):
        blockers = ", ".join(b["verification_id"] for b in capability["blockers"]) or "none"
        lines.append(f"- {name}: {capability['release_status']}; blockers: {blockers}.")
    lines.extend(
        [
            "",
            "## Combined measurements and resource growth",
            "",
            "Thresholds: " + json.dumps(report["thresholds"], sort_keys=True) + ".",
            "",
            "Full observations are in `matrix-results.json`; summaries follow.",
            "",
        ]
    )
    for measurement in report["measurements"]:
        summary = {
            key: value for key, value in measurement.items() if key not in {"rows", "samples"}
        }
        if measurement.get("samples"):
            summary["first_sample"] = measurement["samples"][0]
            summary["last_sample"] = measurement["samples"][-1]
        lines.extend(["```json", json.dumps(summary, indent=2), "```", ""])
    lines.extend(
        [
            "Optimization promotion assessment: "
            + json.dumps(report.get("optimization_promotion", {}), sort_keys=True)
            + ".",
            "",
        ]
    )
    lines.extend(
        [
            "## Deferred environment-dependent verification — intentionally not executed",
            "",
            (
                "The known PostgreSQL/pgvector, DynamoDB Local, reviewed cloud-smoke and live "
                "Gemini suites are intentionally not executed: their environments are deferred. "
                "These are availability gates, not implementation defects. Domain, browser, "
                "ChatGPT billing/transport and real-service capacity/IAM/headroom remain "
                "unverified. Local proxies do not close these obligations."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def run(output):
    raw = MATRIX_PATH.read_bytes()
    matrix = VerificationMatrix.model_validate_json(raw)
    # Source matrix cannot self-certify evidence. All passes are derived below.
    if any(r.status == "passed" for r in matrix.rows):
        raise ValueError("matrix_input_cannot_claim_pass")
    identity = source_identity()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    refs = sorted(
        {ref for row in matrix.rows if row.evidence_class == "offline" for ref in row.test_refs}
    )
    with tempfile.TemporaryDirectory(prefix="phase36-") as scratch:
        receipt_path = Path(scratch) / "receipts.json"
        env = {
            **os.environ,
            "PHASE36_RECEIPTS": str(receipt_path),
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "ARTIFACTS_ENABLED": "false",
        }
        # No external opt-ins, user pytest flags or third-party plugins in this program.
        for key in tuple(env):
            if key.startswith(
                ("PERSISTENCE_TEST_", "RUN_LIVE_", "RUN_CLOUD_", "PYTEST_ADDOPTS")
            ) or key in {
                "RUN_GEMINI_MANUAL_TEST",
                "RUN_CONTEXT_MANUAL_TEST",
            }:
                env.pop(key)
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "anyio.pytest_plugin",
                    "-p",
                    "personal_ai.evaluation.verification.pytest_evidence",
                    "-m",
                    "not persistence_integration and not cloud_smoke",
                    *refs,
                ],
                cwd=ROOT / "backend",
                env=env,
                timeout=300,
                check=False,
            )
            receipt = (
                json.loads(receipt_path.read_text())
                if receipt_path.exists()
                else {
                    "exit_code": result.returncode,
                    "cases": [],
                }
            )
        except subprocess.TimeoutExpired:
            receipt = {"exit_code": 124, "cases": []}
    if source_identity() != identity:
        raise ValueError("source_changed_during_verification")
    receipt_digest = sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest()
    rows = []
    for row in matrix.rows:
        if row.evidence_class == "offline":
            status = execution_status(row.test_refs, receipt["cases"])
            # Infrastructure/collection failure cannot be a successful verification batch.
            if receipt["exit_code"] not in (0, 1) and status == "passed":
                status = "unverified"
            row = row.model_copy(
                update={
                    "status": status,
                    "tested_revision": head,
                    "configuration_sha256": identity,
                    "evidence_ref": f"receipts.json#sha256={receipt_digest}",
                    "rationale": "Executed selected canonical regression/conformance cases."
                    if status == "passed"
                    else "Failure, skipped/missing case or incomplete execution.",
                }
            )
        rows.append(row)
    report = {
        "schema_version": matrix.schema_version,
        "tested_revision": head,
        "configuration_sha256": identity,
        "matrix_sha256": sha256(raw).hexdigest(),
        "recorded_at": datetime.now(UTC).isoformat(),
        "strategy_coverage": matrix.strategy_coverage,
        "thresholds": matrix.thresholds,
        "fault_scenarios": [
            {
                **fault.model_dump(),
                "status": execution_status(fault.test_refs, receipt["cases"]),
                "evidence_ref": f"receipts.json#sha256={receipt_digest}",
            }
            for fault in matrix.fault_scenarios
        ],
        "runtime": {
            "python": sys.version,
            "platform": sys.platform,
            "external_execution": "disabled; fixed offline pytest selection",
        },
        "rows": [row.model_dump(mode="json") for row in rows],
        "measurements": [
            c["metrics"] for c in receipt["cases"] if "metrics" in c and c["status"] == "passed"
        ],
        "release": release_projection(rows),
    }
    report["optimization_promotion"] = integrated_promotion(
        report["measurements"], matrix.thresholds
    )
    output.mkdir(parents=True, exist_ok=True)
    for name, data in (
        ("matrix-results.json", report),
        ("receipts.json", receipt),
        ("blockers.json", report["release"]),
    ):
        (output / name).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    (output / "release-report.md").write_text(render_report(report))
    print(json.dumps(report["release"]["status_counts"], sort_keys=True))
    return 1 if any(row.status == "failed" for row in rows) or receipt["exit_code"] else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/phase36")
    args = parser.parse_args()
    return run(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
