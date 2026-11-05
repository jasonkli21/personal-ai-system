"""Reproducible, content-free evidence for the offline reasoning cohort."""

import argparse
import errno
import json
import re
import socket
import sys
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
from os import O_ACCMODE, O_APPEND, O_CREAT, O_TRUNC
from pathlib import Path
from time import perf_counter_ns

from .reasoning_contracts import Observation
from .reasoning_harness import Effects, run_arm
from .reasoning_scoring import ARMS, complete, score
from .reasoning_seal import MANIFEST_SHA256, load


class EffectFence:
    """Python audit fence scoped to measurement. Native fencing is separate."""

    blocked = 0
    active = True

    def audit(self, event, args):
        denied = event.startswith(("socket.", "subprocess.", "os.exec", "os.spawn"))
        denied |= event in {
            "os.system",
            "os.fork",
            "os.posix_spawn",
            "os.remove",
            "os.rename",
            "os.mkdir",
            "os.rmdir",
            "os.symlink",
            "os.link",
            "os.chmod",
            "os.truncate",
            "os.chdir",
        }
        if event == "open":
            # CPython audit reports the integer open flags even for file objects.
            denied = bool(args[2] & WRITE_FLAGS)
        if self.active and denied:
            self.blocked += 1
            raise PermissionError("benchmark_effect_denied")


# Access and creation flags also catch O_RDONLY combined with truncation.
WRITE_FLAGS = O_ACCMODE | O_APPEND | O_CREAT | O_TRUNC


class QuietMeasurement:
    wrote = False

    def write(self, value: str) -> int:
        self.wrote |= bool(value)
        return len(value)

    def flush(self) -> None:
        pass


def digest(data) -> str:
    return sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def evaluate() -> tuple[dict, list[int]]:
    corpus, manifest = load()
    rows = []
    timing = []
    for case in corpus.cases:
        for arm in ARMS:
            effects = Effects()
            start = perf_counter_ns()
            try:
                observation = Observation.model_validate(
                    run_arm(case.task, case.scenario, case.foreign_slots, arm, effects)
                )
                row = score(case, arm, observation, effects)
            except (
                Exception  # noqa: BLE001
            ):  # Deliberately retain the row and suppress payload-bearing exceptions.
                row = score(
                    case,
                    arm,
                    Observation(status="internal_error", reason="internal_failure"),
                    effects,
                )
            timing.append(perf_counter_ns() - start)
            rows.append(row)
    load()
    cohorts = []
    for family in dict.fromkeys(case.task.family for case in corpus.cases):
        for arm in ARMS:
            selected = [row for row in rows if row["family"] == family and row["arm"] == arm]
            cohorts.append(
                {
                    "family": family,
                    "arm": arm,
                    "outcomes": dict(Counter(row["status"] for row in selected)),
                    "proxy_observed": sum(row["task_proxy"] is not None for row in selected),
                    "proxy_met": sum(row["task_proxy"] is True for row in selected),
                }
            )
    direct, diagnostic = rows[::2], rows[1::2]
    pairs = [
        (a, b) for a, b in zip(direct, diagnostic, strict=True) if b["status"] != "unsupported"
    ]
    return {
        "suite": corpus.version,
        "manifest_sha256": MANIFEST_SHA256,
        "frozen_files": manifest["files"],
        "model": manifest["model"],
        "quality": "proxy_only",
        "actual_model_tokens": None,
        "actual_provider_cost_usd": None,
        "quota_denials": sum(row["reason"] == "quota" for row in rows),
        "e2_local_model": "blocked_unverified",
        "expected_rows": len(corpus.cases) * len(ARMS),
        "coverage_complete": complete(corpus.cases, rows),
        "safety_vetoes": sum(row["safety_veto"] for row in rows),
        "pairing": {
            "expected": len(corpus.cases),
            "eligible": len(pairs),
            "unsupported": len(corpus.cases) - len(pairs),
            "matched": all(
                (a["model_attempts"], a["prepared_sha256"])
                == (b["model_attempts"], b["prepared_sha256"])
                for a, b in pairs
            ),
        },
        "outcomes": dict(Counter(row["status"] for row in rows)),
        "cohorts": cohorts,
        "rows": rows,
    }, timing


def verify_native() -> None:
    # Only literal loopback probes. A blocked connect must be a permission denial.
    for family, address in [
        (socket.AF_INET, ("127.0.0.1", 9)),
        (socket.AF_INET6, ("::1", 9, 0, 0)),
    ]:
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.25)
            try:
                probe.connect(address)
            except OSError as error:
                if error.errno in {errno.EPERM, errno.EACCES}:
                    continue
            raise ValueError("native_network_denial_unverified")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", required=True)
    parser.add_argument("--tree", required=True)
    parser.add_argument("--dirty", choices=("yes", "no"), required=True)
    parser.add_argument("--native-fence", action="store_true")
    args = parser.parse_args()
    if not all(re.fullmatch(r"[0-9a-f]{40}", value) for value in (args.commit, args.tree)):
        parser.error("invalid source provenance")
    if args.native_fence:
        verify_native()
    fence = EffectFence()
    sys.addaudithook(fence.audit)
    sink = QuietMeasurement()
    try:
        with redirect_stdout(sink), redirect_stderr(sink):
            semantic, timings = evaluate()
    except Exception:  # noqa: BLE001 - do not print fixture or observation payloads.
        print("reasoning_evaluation_invalid_source_or_internal_failure", file=sys.stderr)
        return 1
    finally:
        fence.active = False

    valid = (
        semantic["coverage_complete"]
        and semantic["pairing"]["matched"]
        and fence.blocked == 0
        and not sink.wrote
    )
    report = {
        "commit": args.commit,
        "tree": args.tree,
        "dirty": args.dirty == "yes",
        "native_network_fence": "loopback_denied" if args.native_fence else "unverified",
        "python_effect_audit_attempts_blocked": fence.blocked,
        "unexpected_console_output": sink.wrote,
        "semantic_sha256": digest(semantic),
        "semantic": semantic,
        "local_fake_row_elapsed_ns": timings,
        "valid": valid,
    }
    output = Path("artifacts/reasoning/report.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(output)
    print(
        f"reasoning: {len(semantic['rows'])}/{semantic['expected_rows']} rows "
        f"valid={valid} semantic_sha256={report['semantic_sha256']}"
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
