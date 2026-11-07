"""Isolated offline information handling offline evaluator with fail-closed coverage and native fencing."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import logging
import math
import multiprocessing
import platform
import socket
import sys
from hashlib import sha256
from time import perf_counter, process_time

from personal_ai.evaluation.evaluation_effect_audit import (
    BoundedTextSink,
    EffectAudit,
    install_python_network_fence,
)
from personal_ai.evaluation.offline_information_contracts import (
    OPTIONAL_PACKAGES,
    Observation,
    Task,
    _package_tree_digest,
    canonical,
    load_corpus,
)
from personal_ai.evaluation.offline_information_scoring import aggregate, score

OPERATION_DEADLINE_SECONDS = 5
SUITE_DEADLINE_SECONDS = 300
MAX_LOG_BYTES = 4096
MAX_RESULT_BYTES = 8192


def verify_native_fence() -> str:
    """Prove OS-level remote connects fail in the process about to measure."""
    if sys.platform != "darwin":
        raise RuntimeError("native_loopback_fence_unavailable")
    for family, address in (
        (socket.AF_INET, ("192.0.2.1", 9)),
        (socket.AF_INET6, ("2001:db8::1", 9, 0, 0)),
    ):
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.25)
            try:
                probe.connect(address)
            except OSError as error:
                if error.errno not in {1, 13}:  # EPERM/EACCES from the native sandbox.
                    raise RuntimeError("native_loopback_fence_not_proven") from None
            else:
                raise RuntimeError("native_loopback_fence_absent")
    return "native_loopback_only"


def _worker(task_data, arm, connection, driver, require_native):
    """Run one operation in a process that can be terminated without orphan work."""
    audit = EffectAudit()
    stdout, stderr = BoundedTextSink(MAX_LOG_BYTES), BoundedTextSink(MAX_LOG_BYTES)
    # This process is the isolation boundary. Keep its streams redirected through
    # os._exit so late worker-thread output cannot reach the parent process.
    sys.stdout, sys.stderr = stdout, stderr
    from personal_ai.evaluation.evaluation_effect_audit import bind_audit
    from personal_ai.evaluation.offline_task_driver import dispatch

    started_cpu = process_time()
    native_fence = "unverified"
    observation = None
    prior_disable = logging.root.manager.disable
    try:
        with bind_audit(audit):
            if require_native:
                try:
                    native_fence = verify_native_fence()
                except Exception:  # noqa: BLE001 - return only a fixed error code.
                    observation = Observation(
                        outcome="failed",
                        hard_valid=False,
                        factual=None,
                        status="unmeasured",
                        error="native_fence_missing",
                    )
            install_python_network_fence(audit)
            if observation is None:
                logging.disable(logging.CRITICAL)
                try:
                    task = Task.model_validate(task_data)
                    try:
                        observation = (driver or dispatch)(task, arm)
                    except ModuleNotFoundError as error:
                        missing = error.name or ""
                        if missing.startswith("reading_logbook"):
                            observation = Observation(
                                outcome="failed",
                                hard_valid=False,
                                factual=None,
                                status="blocked_capability",
                                ineligibility="missing_optional_host",
                            )
                        else:
                            observation = Observation(
                                outcome="failed",
                                hard_valid=False,
                                factual=None,
                                error="offline_failure",
                            )
                    except Exception:  # noqa: BLE001 - content-free failure contract.
                        error = (
                            "network_attempt"
                            if audit.counts["external_send"]
                            else "offline_failure"
                        )
                        observation = Observation(
                            outcome="failed", hard_valid=False, factual=None, error=error
                        )
                    try:
                        observation = Observation.model_validate(observation)
                    except Exception:  # noqa: BLE001 - malformed drivers are not successful.
                        observation = Observation(
                            outcome="failed",
                            hard_valid=False,
                            factual=None,
                            error="offline_failure",
                        )
                finally:
                    logging.disable(prior_disable)
        payload = {
            "observation": observation.model_dump(mode="json"),
            "audit": {
                **audit.snapshot(),
                "complete": not bool(audit.counts["audit_overflow"]),
                "log_truncated": stdout.truncated or stderr.truncated,
            },
            "native_fence": native_fence,
            "cpu_ms": round((process_time() - started_cpu) * 1000, 3),
        }
        encoded = canonical(payload).encode()
        connection.send_bytes(encoded[:MAX_RESULT_BYTES])
    except BaseException:  # noqa: BLE001 - child crash is content-free to the parent.
        try:
            connection.send_bytes(b"{}")
        except Exception:  # noqa: BLE001 - parent observes the closed/crashed worker.
            logging.getLogger(__name__).debug("offline_information_handling_worker_result_unavailable")
    finally:
        connection.close()
    # Terminate daemon threads that might outlive their owning task.
    import os

    os._exit(0)


def safe_dispatch(
    task, arm, *, driver=None, timeout_seconds=OPERATION_DEADLINE_SECONDS, require_native=True
):
    """Return bounded observation, independent effect counts and fence evidence."""
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=_worker,
        args=(task.model_dump(mode="json"), arm, sender, driver, require_native),
        daemon=True,
    )
    started = perf_counter()
    try:
        process.start()
    except Exception:  # noqa: BLE001 - failure to isolate means no trusted observation.
        receiver.close()
        sender.close()
        return (
            Observation(
                outcome="failed",
                hard_valid=False,
                factual=None,
                status="unmeasured",
                error="worker_crash",
            ),
            {"complete": False},
            round((perf_counter() - started) * 1000, 3),
            None,
            "unverified",
        )
    sender.close()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(0.25)
        if process.is_alive():
            process.kill()
            process.join(0.25)
        receiver.close()
        return (
            Observation(
                outcome="failed",
                hard_valid=False,
                factual=None,
                status="unmeasured",
                error="operation_timeout",
            ),
            {"complete": False},
            round((perf_counter() - started) * 1000, 3),
            None,
            "unverified",
        )
    elapsed = round((perf_counter() - started) * 1000, 3)
    try:
        if not receiver.poll(0.1):
            raise ValueError("worker_no_result")
        payload = json.loads(receiver.recv_bytes(MAX_RESULT_BYTES))
        observation = Observation.model_validate(payload["observation"])
        audit = payload["audit"]
        native_fence = payload["native_fence"]
        cpu_ms = payload["cpu_ms"]
    except Exception:  # noqa: BLE001 - malformed/crashed workers fail closed.
        observation = Observation(
            outcome="failed",
            hard_valid=False,
            factual=None,
            status="unmeasured",
            error="worker_crash",
        )
        audit, native_fence, cpu_ms = {"complete": False}, "unverified", None
    finally:
        receiver.close()
        process.close()
    return observation, audit, elapsed, cpu_ms, native_fence


def runtime_identity():
    """Hash installed code identities without Git, checkout paths or editable hooks."""
    rows = []
    for module, distribution in (
        ("personal_ai", "personal-ai-backend"),
        *OPTIONAL_PACKAGES.values(),
    ):
        digest = _package_tree_digest(module)
        try:
            version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            version = "source-tree" if digest else "not_installed"
        rows.append(
            {
                "distribution": distribution,
                "version": version,
                "package_sha256": digest or "not_installed",
            }
        )
    rows.sort(key=lambda row: row["distribution"])
    return {"sha256": sha256(canonical(rows).encode()).hexdigest(), "distributions": rows}


def enforce_operation_budgets(observation, corpus):
    too_large = (
        observation.input_units is not None and observation.input_units > corpus.input_cap
    ) or (observation.output_units is not None and observation.output_units > corpus.output_cap)
    if too_large:
        return observation.model_copy(update={"hard_valid": False, "error": "budget_exceeded"})
    return observation


def nearest_rank(values, quantile):
    ordered = sorted(values)
    if not ordered or not 0 < quantile <= 1:
        raise ValueError("nearest_rank_input_invalid")
    return ordered[math.ceil(quantile * len(ordered)) - 1]


def _row(case, arm, order, observation, audit, wall, cpu, native_fence):
    digest = sha256(canonical(case.model_dump(mode="json")).encode()).hexdigest()
    source_digest = sha256(canonical(case.task.model_dump(mode="json")).encode()).hexdigest()
    return {
        "case_digest": digest,
        "source_digest": source_digest,
        "family": case.task.family,
        "split": case.split,
        "arm": arm,
        "order": order,
        "authority": "synthetic_exact_scope",
        "owner_class": "synthetic",
        "actor_class": "verified_synthetic",
        "application_class": "unrelated_http_consumer"
        if case.task.family not in {"memory", "research"}
        else "local_service",
        "workspace_class": "isolated_synthetic",
        "rights_epoch_class": "local_revision_one",
        "output_token_confidence": "estimated"
        if observation.output_units is not None
        else "unknown",
        "provider": (
            "offline_fake_alt"
            if case.task.family == "provider" and arm == "candidate"
            else "offline_fake"
        )
        if case.task.family not in {"memory", "research"}
        else "synthetic_only",
        "model": (
            "offline_fake_alt-v1"
            if case.task.family == "provider" and arm == "candidate"
            else "offline_fake-v1"
        )
        if case.task.family not in {"memory", "research"}
        else "not_applicable",
        "token_counter": "pi3-local-json-bytes-v1"
        if observation.token_confidence == "authoritative_local_bytes"
        else observation.token_confidence,
        "serializer": "pi3-local-json-bytes-v1"
        if case.task.family not in {"memory", "research"}
        else "not_applicable",
        "observation": observation.model_dump(mode="json"),
        "effects": audit,
        "score": score(case, arm, observation, audit),
        "wall_ms": wall,
        "cpu_ms": cpu,
        "latency_class": "local_synthetic",
        "native_fence": native_fence,
        "cost": {
            "synthetic_usd": 0,
            "real_usd": None,
            "upper_bound_usd": None,
            "estimated_usd": None,
            "confidence": "synthetic_only",
        },
        "quota": {"reservation": None, "settlement": None, "status": "unmeasured"},
        "cancellation": "not_applicable",
        "unknown_outcome": observation.error != "none",
    }


def evaluate(*, emit=None, require_native=True):
    corpus, manifest = load_corpus()
    runtime = runtime_identity()
    started = perf_counter()
    warmup = Task(
        family="provider", variant="current", subject="warmup", value="ready", distractor="absent"
    )
    warmed, warm_audit, _wall, _cpu, warm_fence = safe_dispatch(
        warmup, "baseline", require_native=require_native
    )
    rows = []
    warmup_ok = (
        warmed.error == "none"
        and warmed.hard_valid
        and warm_audit.get("model_dispatch") == 1
        and (not require_native or warm_fence == "native_loopback_only")
    )
    for case in corpus.cases:
        arms = (
            ("baseline", "candidate")
            if (len(rows) + corpus.seed) % 2
            else ("candidate", "baseline")
        )
        if case.task.family == "retrieval":
            arms = (*arms, "standalone")
        for arm in arms:
            if perf_counter() - started >= SUITE_DEADLINE_SECONDS:
                observation = Observation(
                    outcome="failed",
                    hard_valid=False,
                    factual=None,
                    status="unmeasured",
                    ineligibility="suite_deadline",
                )
                audit, wall, cpu, fence = {"complete": False}, 0.0, None, "unverified"
            else:
                observation, audit, wall, cpu, fence = safe_dispatch(
                    case.task, arm, require_native=require_native
                )
            observation = enforce_operation_budgets(observation, corpus)
            row = _row(case, arm, len(rows), observation, audit, wall, cpu, fence)
            rows.append(row)
            if emit:
                safe_copy = json.loads(canonical(row))
                if len(canonical(safe_copy).encode()) > MAX_RESULT_BYTES:
                    raise ValueError("offline_information_handling_row_output_cap_exceeded")
                emit(safe_copy)
    analysis = aggregate(rows, corpus)
    all_native = require_native and all(
        row["native_fence"] == "native_loopback_only"
        for row in rows
        if row["observation"]["status"] == "measured"
    )
    analysis["native_fence_complete"] = all_native
    analysis["warmup_valid"] = warmup_ok
    if not require_native:
        analysis["untrusted_python_only"] = True
        analysis["evaluation_complete"] = False
    if not warmup_ok:
        analysis["evaluation_complete"] = False
        analysis["coverage"]["valid"] = False
        analysis["coverage"]["violations"] = sorted(
            set(analysis["coverage"]["violations"] + ["warmup_invalid"])
        )
    elapsed = sorted(row["wall_ms"] for row in rows)
    return {
        "suite": corpus.suite,
        "rubric": corpus.rubric,
        "seed": corpus.seed,
        "evidence_class": "offline_scripted_service_proxy"
        if require_native
        else "untrusted_python_only",
        "fixture_hashes": manifest["hashes"],
        "preregistration": manifest["preregistration"],
        "runtime_identity": runtime,
        "configuration_sha256": sha256(
            canonical(
                {
                    "input_cap": corpus.input_cap,
                    "output_cap": corpus.output_cap,
                    "source_bytes": corpus.source_bytes,
                    "operation_deadline_seconds": corpus.deadline_seconds,
                    "suite_deadline_seconds": SUITE_DEADLINE_SECONDS,
                }
            ).encode()
        ).hexdigest(),
        "runtime": platform.python_version(),
        "os": platform.system(),
        "architecture": platform.machine(),
        "rows": rows,
        "analysis": analysis,
        "latency": {
            "class": "local_synthetic",
            "n": len(elapsed),
            "p50_ms": __import__("statistics").median(elapsed) if elapsed else None,
            "p95_ms": nearest_rank(elapsed, 0.95) if elapsed else None,
            "p95_method": "nearest_rank",
        },
        "ineligible": [
            {
                "arm": "external_source_to_model",
                "status": "blocked_capability",
                "reason": "distributed_authority_absent",
            },
            {
                "arm": "live_provider_quality",
                "status": "unmeasured",
                "reason": "no_live_authorization",
            },
            {
                "arm": "paid_or_arbitrary_tool",
                "status": "denied_policy",
                "reason": "outside_offline_scope",
            },
            {
                "arm": "memory_on_nonmemory_tasks",
                "status": "not_applicable",
                "reason": "task_has_no_durable_memory",
            },
        ],
        "completion_status": "blocked_unverified",
        "offline_evaluation": "complete_local"
        if analysis["evaluation_complete"]
        else "changes_required",
        "offline_information_handling_production_promotion": "no_go",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = evaluate(require_native=True)
    payload = canonical(result) + "\n"
    if len(payload.encode()) > 10_000_000:
        raise SystemExit("OFFLINE_BENCHMARK result exceeds fixed output limit")
    from pathlib import Path

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload)
    summary = {
        "suite": result["suite"],
        "rows": len(result["rows"]),
        "evaluation_complete": result["analysis"]["evaluation_complete"],
        "coverage": result["analysis"]["coverage"],
        "safety_veto": result["analysis"]["safety_veto"],
    }
    print(canonical(summary))
    analysis = result["analysis"]
    return (
        1
        if (
            not analysis["evaluation_complete"]
            or analysis["safety_veto"]
            or not analysis["native_fence_complete"]
            or not analysis["warmup_valid"]
        )
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
