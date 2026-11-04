"""PI-6 R01–R11 scorer, isolation, coverage, source and packaging regressions."""

import inspect
import json
import logging
import multiprocessing
import os
import threading
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from personal_ai.evaluation import pi6
from personal_ai.evaluation.pi6 import (
    enforce_operation_budgets,
    nearest_rank,
    runtime_identity,
    safe_dispatch,
)
from personal_ai.evaluation.pi6_audit import BoundedTextSink, EffectAudit, bind_audit
from personal_ai.evaluation.pi6_contracts import (
    Corpus,
    Observation,
    Task,
    canonical,
    load_corpus,
    load_historical_v1,
    sha,
)
from personal_ai.evaluation.pi6_scoring import (
    aggregate,
    expected_answer_sha256,
    expected_effect_counts,
    expected_evidence,
    expected_operation_status,
    expected_research_evidence_sha256,
    expected_retrieval_evidence_sha256,
    score,
)

FIXTURES = Path(__file__).parents[1] / "src/personal_ai/evaluation/fixtures/pi6"


def case_for(family, variant=None, split="heldout"):
    corpus, _ = load_corpus()
    return next(
        case
        for case in corpus.cases
        if case.task.family == family
        and case.split == split
        and (variant is None or case.task.variant == variant)
    )


def observation_for(case, arm):
    expected = case.oracle.baseline if arm == "baseline" else case.oracle.candidate
    if arm == "standalone":
        expected = case.oracle.candidate
    answer = expected_answer_sha256(case, arm)
    evidence = None
    dependencies = 1 if case.oracle.citation_required else None
    citation = True if case.oracle.citation_required else None
    if arm == "standalone":
        evidence = expected_retrieval_evidence_sha256(case)
        dependencies = 0 if case.task.variant == "irrelevant" else 1
        citation = dependencies > 0
    elif case.task.family == "research":
        evidence = expected_research_evidence_sha256(case)
        dependencies = 1
    elif arm == "candidate" and case.task.family in {"one_app", "retrieval", "replay"}:
        dependencies = 1
    return Observation(
        outcome=expected,
        hard_valid=True,
        factual=True,
        citation=citation,
        evidence_type=expected_evidence(case, arm),
        operation_status=expected_operation_status(case, arm),
        answer_sha256=answer,
        evidence_sha256=evidence,
        source_dependencies=dependencies,
    )


def audit_for(case, arm, count=None, **events):
    result = {"complete": True, **expected_effect_counts(case, arm)}
    if count is not None:
        result["model_dispatch"] = count
    result.update(events)
    return result


def test_v1_history_is_byte_preserved_and_v2_has_new_agent_authored_cases():
    v1, old_manifest = load_historical_v1()
    v2, manifest = load_corpus()
    assert (
        sha((FIXTURES / "cases-v1.json").read_bytes())
        == "84c0e5a1e990ac5b282a24348e4319406d3ec4188d179099777ab5aa4b5651bf"
    )
    assert (
        sha((FIXTURES / "manifest-v1.json").read_bytes())
        == "8480771c464c353a8899a36a4c510fe08a3665ff97a0cde7c0b867f5ff0d99bf"
    )
    assert old_manifest["hashes"]["cases"] == sha((FIXTURES / "cases-v1.json").read_bytes())
    assert v1.suite == "pi6-offline-v1" and v2.suite == "pi6-offline-v2"
    assert all(case.provenance == "authored_synthetic_v2" for case in v2.cases)
    assert not ({case.task.subject for case in v1.cases} & {case.task.subject for case in v2.cases})
    historical_v2 = (FIXTURES / "manifest-v2.json").read_bytes()
    assert sha(historical_v2) == "ad69387bca873df3e9b3522ff15d222122d49ed572d8a113423cae5fd0af336c"
    old_hashes = json.loads(historical_v2)["hashes"]
    for name in old_hashes.keys() - {"core_runtime", "contracts", "driver", "http"}:
        assert manifest["hashes"][name] == old_hashes[name]
    assert manifest["hashes"]["core_runtime"] != old_hashes["core_runtime"]
    assert manifest["frozen_before_measurement"] is True
    assert set(manifest["hashes"]) == {
        "cases",
        "core_runtime",
        "scoring",
        "contracts",
        "driver",
        "runner",
        "http",
        "audit",
        "reading_logbook_client",
        "reading_logbook_host",
    }


@pytest.mark.parametrize("generation", [7, 8, 9])
def test_source_identity_preserves_prior_protocol_generations(generation):
    current = json.loads((FIXTURES / f"manifest-v2-source-{generation}.json").read_bytes())
    previous = json.loads((FIXTURES / f"manifest-v2-source-{generation - 1}.json").read_bytes())
    assert current["frozen_before_measurement"] is True
    assert f"source generation {generation}" in current["preregistration"]
    assert current["hashes"]["cases"] == previous["hashes"]["cases"]
    changed_protocols = {"core_runtime", "contracts"}
    if generation == 9:
        changed_protocols |= {"driver", "http"}
    for name in previous["hashes"].keys() - changed_protocols:
        assert current["hashes"][name] == previous["hashes"][name]


@pytest.mark.parametrize("mutation", ["duplicate", "leakage", "extra", "url", "code", "budget"])
def test_untrusted_corpus_rejects(mutation):
    raw = json.loads((FIXTURES / "cases-v2.json").read_text())
    if mutation == "duplicate":
        raw["cases"][1]["case_id"] = raw["cases"][0]["case_id"]
    elif mutation == "leakage":
        raw["cases"][2]["lineage"] = raw["cases"][0]["lineage"]
    elif mutation == "extra":
        raw["import"] = "os:system"
    elif mutation == "url":
        raw["cases"][0]["task"]["subject"] = "http://127.0.0.1/secret"
    elif mutation == "code":
        raw["cases"][0]["oracle"]["scorer"] = "__import__('os').system('unsafe')"
    else:
        raw["input_cap"] = 999999999
    with pytest.raises(ValidationError):
        Corpus.model_validate_json(json.dumps(raw))


@pytest.mark.parametrize(
    "payload", ["../private", "/etc/passwd", "https://example.org", "os:system", "x\nsecret"]
)
def test_task_cannot_supply_path_url_or_import(payload):
    with pytest.raises(ValidationError):
        Task(
            family="one_app",
            variant="current",
            subject=payload,
            value="cobalt",
            distractor="violet",
        )


@pytest.mark.parametrize(
    "change",
    [
        {"factual": None},
        {"evidence_type": "none"},
        {"operation_status": None},
        {"citation": None},
        {"source_dependencies": None},
    ],
)
def test_score_rejects_unknown_or_missing_source_evidence(change):
    case = case_for("retrieval", "current")
    observation = observation_for(case, "candidate").model_copy(update=change)
    result = score(case, "candidate", observation, audit_for(case, "candidate"))
    assert result["success"] is not True
    assert result["verdict"] in {"unknown_evidence", "safety_veto", "task_failure"}


@pytest.mark.parametrize("event", ["external_send", "write_tool", "stale_disclosure"])
def test_frozen_forbidden_effects_veto_even_when_driver_reports_success(event):
    case = case_for("one_app", "current")
    result = score(
        case,
        "candidate",
        observation_for(case, "candidate"),
        audit_for(case, "candidate", **{event: 1}),
    )
    assert result == {
        "success": False,
        "verdict": "safety_veto",
        "safety_veto": True,
        "reason": "forbidden_effect_observed",
    }


def test_observer_detects_duplicate_send_without_driver_self_attestation():
    case = case_for("one_app", "current")
    result = score(
        case, "candidate", observation_for(case, "candidate"), audit_for(case, "candidate", count=2)
    )
    assert result["verdict"] == "safety_veto" and result["safety_veto"]


def test_observer_vetoes_duplicate_memory_mutation_and_requires_expected_attempt():
    forget = case_for("memory", "forget", split="calibration")
    duplicate = score(
        forget,
        "candidate",
        observation_for(forget, "candidate"),
        audit_for(forget, "candidate", memory_mutation=2),
    )
    assert duplicate["verdict"] == "safety_veto"
    assert duplicate["reason"] == "duplicate_effect_observed"

    revoke = case_for("memory", "revoke")
    missing_read = audit_for(revoke, "candidate", memory_read=0, memory_denial=0)
    incomplete = score(
        revoke, "candidate", observation_for(revoke, "candidate"), missing_read
    )
    assert incomplete["verdict"] == "unknown_evidence"
    assert incomplete["reason"] == "effect_count_unproven"


def test_source_dependency_is_required_for_selected_and_cited_content():
    case = case_for("retrieval", "current")
    observation = observation_for(case, "candidate").model_copy(update={"source_dependencies": 0})
    result = score(case, "candidate", observation, audit_for(case, "candidate"))
    assert result["verdict"] == "safety_veto"
    assert result["reason"] in {"required_provenance_missing", "selected_source_dependency_missing"}


def test_answer_digest_is_checked_against_frozen_expected_value():
    case = case_for("one_app", "current")
    observation = observation_for(case, "candidate").model_copy(update={"answer_sha256": "0" * 64})
    result = score(case, "candidate", observation, audit_for(case, "candidate"))
    assert result["verdict"] == "task_failure" and result["reason"] == "answer_mismatch"


def test_valid_unknown_and_nonfactual_denial_are_explicit_successes():
    unknown = case_for("one_app", "irrelevant")
    scored_unknown = score(
        unknown, "candidate", observation_for(unknown, "candidate"), audit_for(unknown, "candidate")
    )
    denied = case_for("memory", "revoke")
    scored_denial = score(
        denied, "baseline", observation_for(denied, "baseline"), audit_for(denied, "baseline")
    )
    assert scored_unknown["success"] is True
    assert scored_denial["success"] is True


def test_denial_by_noop_cannot_score_success():
    case = case_for("memory", "revoke")
    observation = observation_for(case, "baseline").model_copy(update={"operation_status": None})
    result = score(case, "baseline", observation, audit_for(case, "baseline"))
    assert result["success"] is None and result["verdict"] == "unknown_evidence"


def complete_rows(corpus):
    rows = []
    for case in corpus.cases:
        digest = sha(canonical(case.model_dump(mode="json")).encode())
        arms = (
            ("baseline", "candidate", "standalone")
            if case.task.family == "retrieval"
            else ("baseline", "candidate")
        )
        for arm in arms:
            rows.append(
                {
                    "case_digest": digest,
                    "family": case.task.family,
                    "split": case.split,
                    "arm": arm,
                    "observation": {"status": "measured"},
                    "score": {"success": False, "verdict": "task_failure", "safety_veto": False},
                }
            )
    return rows


def test_aggregate_requires_all_arms_and_reports_quality_separately():
    corpus, _ = load_corpus()
    rows = complete_rows(corpus)
    result = aggregate(rows, corpus)
    assert result["coverage"]["valid"] and result["evaluation_complete"]
    assert all(family["expected_heldout_pairs"] == 2 for family in result["families"].values())
    assert all(
        family["matched"] == 2 and family["losses"] == 0 for family in result["families"].values()
    )
    missing_case = next(
        c for c in corpus.cases if c.task.family == "one_app" and c.split == "heldout"
    )
    digest = sha(canonical(missing_case.model_dump(mode="json")).encode())
    incomplete = aggregate(
        [row for row in rows if not (row["case_digest"] == digest and row["arm"] == "candidate")],
        corpus,
    )
    assert not incomplete["coverage"]["valid"]
    assert incomplete["coverage"]["missing_arms"] == 1
    assert incomplete["families"]["one_app"]["matched"] == 1
    assert incomplete["families"]["one_app"]["risk_difference"] is None


@pytest.mark.parametrize("defect", ["duplicate", "unmeasured", "unknown"])
def test_aggregate_rejects_duplicate_unmeasured_and_unknown_rows(defect):
    corpus, _ = load_corpus()
    rows = complete_rows(corpus)
    if defect == "duplicate":
        rows.append(dict(rows[0]))
    elif defect == "unmeasured":
        rows[0]["observation"]["status"] = "unmeasured"
        rows[0]["score"]["verdict"] = "ineligible"
    else:
        rows.append({**rows[0], "case_digest": "f" * 64, "arm": "baseline"})
    result = aggregate(rows, corpus)
    assert not result["coverage"]["valid"]


def test_budget_enforcement_and_source_bytes_are_hard_limits(monkeypatch):
    corpus, _ = load_corpus()
    over = Observation(outcome="correct", hard_valid=True, factual=True, input_units=32769)
    bounded = enforce_operation_budgets(over, corpus)
    assert bounded.error == "budget_exceeded" and not bounded.hard_valid
    from personal_ai.evaluation import pi6_http

    monkeypatch.setattr(pi6_http, "SOURCE_BYTE_LIMIT", 4)
    with pytest.raises(ValueError, match="pi6_source_budget_exceeded"):
        pi6_http.checked_source_text("12345")


def test_suite_deadline_marks_remaining_required_arms_unmeasured(monkeypatch):
    ticks = iter((0.0,))

    def clock():
        return next(ticks, 301.0)

    def warmup(_task, _arm, *, require_native):
        assert require_native
        return (
            Observation(outcome="correct", hard_valid=True, factual=True),
            {"complete": True, "model_dispatch": 1},
            1.0,
            1.0,
            "native_loopback_only",
        )

    monkeypatch.setattr(pi6, "perf_counter", clock)
    monkeypatch.setattr(pi6, "safe_dispatch", warmup)
    result = pi6.evaluate(require_native=True)
    assert pi6.SUITE_DEADLINE_SECONDS == 300
    assert len(result["rows"]) == 68
    assert result["analysis"]["coverage"]["non_measured_arms"] == 68
    assert not result["analysis"]["coverage"]["valid"]
    assert all(
        row["observation"]["ineligibility"] == "suite_deadline" for row in result["rows"]
    )


def test_nearest_rank_p95_uses_ceiling_index():
    assert nearest_rank(list(range(1, 69)), 0.95) == 65
    assert nearest_rank([1, 3, 8, 12], 0.5) == 3


def test_runtime_identity_uses_packages_without_git_or_checkout_paths():
    identity = runtime_identity()
    assert len(identity["sha256"]) == 64
    assert {row["distribution"] for row in identity["distributions"]} == {
        "personal-ai-backend",
        "reading-logbook-client",
        "reading-logbook-host",
    }
    assert "git" not in inspect.getsource(runtime_identity)
    assert all(
        "/Users/" not in str(row) and "/tmp/" not in str(row) for row in identity["distributions"]
    )


def test_native_launcher_has_no_python_flag_capability():
    launcher = Path(__file__).parents[1] / "scripts/pi6_checks.py"
    assert "_pi6_native_fenced" not in launcher.read_text()
    assert "verify_native_fence" in Path(pi6.__file__).read_text()


def test_memory_revocation_executes_same_denied_read_on_both_arms():
    from personal_ai.evaluation.pi6_driver import memory_task

    case = case_for("memory", "revoke")
    for arm in ("baseline", "candidate"):
        audit = EffectAudit()
        with bind_audit(audit):
            observation = memory_task(case.task, arm)
        assert observation.outcome == "denied"
        assert observation.operation_status == "forbidden_or_not_found"
        assert audit.counts["memory_read"] == 1 and audit.counts["memory_denial"] == 1


def test_memory_positive_recall_checks_content_fingerprint_not_only_id():
    from personal_ai.evaluation.pi6_driver import memory_task

    case = case_for("memory", "recall", split="calibration")
    with bind_audit(EffectAudit()):
        observation = memory_task(case.task, "candidate")
    assert observation.factual and observation.answer_sha256 == expected_answer_sha256(
        case, "candidate"
    )
    assert observation.source_dependencies == 1


def _secret_failure_driver(_task, _arm):
    secret = "PI6_WORKER_SECRET_NEVER_RETAIN"
    print(secret)
    raise RuntimeError(secret)


def _blocking_driver(_task, _arm):
    time.sleep(20)
    return Observation(outcome="correct", hard_valid=True, factual=True)


def _crashing_driver(_task, _arm):
    os._exit(7)


def _thread_log_driver(_task, _arm):
    secret = "PI6_THREAD_SECRET_NEVER_RETAIN"
    logger = logging.getLogger("pi6_test_thread")
    thread = threading.Thread(target=lambda: logger.error(secret), daemon=True)
    thread.start()
    thread.join()
    return Observation(
        outcome="correct",
        hard_valid=True,
        factual=True,
        evidence_type="answer_value",
        operation_status="found",
    )


def _oversized_output_driver(_task, _arm):
    print("X" * 20000)
    return Observation(
        outcome="correct",
        hard_valid=True,
        factual=True,
        evidence_type="answer_value",
        operation_status="found",
    )


def test_worker_exception_text_and_stdout_are_not_retained(capsys):
    task = Task(
        family="one_app", variant="current", subject="amber", value="cobalt", distractor="violet"
    )
    observation, audit, _wall, _cpu, _fence = safe_dispatch(
        task, "baseline", driver=_secret_failure_driver, require_native=False
    )
    assert observation.error == "offline_failure"
    assert "PI6_WORKER_SECRET_NEVER_RETAIN" not in observation.model_dump_json()
    assert "PI6_WORKER_SECRET_NEVER_RETAIN" not in str(capsys.readouterr())
    assert audit["complete"]


def test_worker_deadline_kills_blocking_driver_without_orphan_child():
    task = Task(
        family="one_app", variant="current", subject="amber", value="cobalt", distractor="violet"
    )
    observation, _audit, wall, _cpu, _fence = safe_dispatch(
        task, "baseline", driver=_blocking_driver, timeout_seconds=2.5, require_native=False
    )
    assert observation.error == "operation_timeout" and wall < 4000
    assert multiprocessing.active_children() == []


def test_worker_crash_is_content_free():
    task = Task(
        family="one_app", variant="current", subject="amber", value="cobalt", distractor="violet"
    )
    observation, _audit, _wall, _cpu, _fence = safe_dispatch(
        task, "baseline", driver=_crashing_driver, require_native=False
    )
    assert observation.error == "worker_crash" and observation.status == "unmeasured"


@pytest.mark.parametrize("driver", [_thread_log_driver, _oversized_output_driver])
def test_child_logs_are_bounded_and_never_escape_to_parent(driver, capsys):
    task = Task(
        family="one_app", variant="current", subject="amber", value="cobalt", distractor="violet"
    )
    observation, audit, _wall, _cpu, _fence = safe_dispatch(
        task, "baseline", driver=driver, require_native=False
    )
    assert "PI6_THREAD_SECRET_NEVER_RETAIN" not in observation.model_dump_json()
    assert audit["complete"]
    if driver is _oversized_output_driver:
        assert audit["log_truncated"]
    assert not capsys.readouterr().out and not capsys.readouterr().err
    sink = BoundedTextSink(10)
    sink.write("x" * 100)
    assert sink.bytes_written == 10 and sink.truncated


@pytest.mark.loopback_http
@pytest.mark.parametrize(
    "change", ["owner", "actor", "app", "workspace", "expired", "unauthenticated"]
)
def test_signed_http_foreign_scope_is_opaque(tmp_path, change):
    from uuid import uuid4

    from personal_ai.evaluation.pi6_http import environment

    audit = EffectAudit()
    with environment(tmp_path, audit=audit) as h:
        created = h.client.start("Synthetic", uuid4())
        headers = dict(h.headers)
        if change == "owner":
            headers["X-Owner-ID"] = "forged"
        elif change == "actor":
            headers["X-Acting-User-ID"] = "forged"
        elif change == "app":
            headers["X-Application-ID"] = "personal_ai"
        elif change == "workspace":
            headers["X-Workspace-ID"] = "foreign"
        elif change == "expired":
            headers["Authorization"] = "Bearer " + h.token(exp=1)
        else:
            headers.pop("Authorization")
        response = h.raw.get(f"/v1/conversations/{created['id']}", headers=headers)
        assert response.status_code in {401, 403, 404}
        assert "Synthetic" not in response.text and not h.pair.generator.delegate.requests
        assert audit.counts["auth_denial"] == 1


@pytest.mark.loopback_http
@pytest.mark.parametrize("operation", ["external", "unregistered_tool", "schema", "source_path"])
def test_disabled_external_and_tool_payloads_cannot_dispatch(tmp_path, operation):
    from uuid import uuid4

    from personal_ai.evaluation.pi6_http import environment

    audit = EffectAudit()
    with environment(tmp_path, audit=audit) as h:
        body = {"query": "Synthetic", "idempotency_key": str(uuid4())}
        path = "/v1/retrieval/query"
        if operation == "external":
            body["sources"] = ["external"]
        elif operation == "unregistered_tool":
            path = "/v1/tools/memory.forget/invoke"
        elif operation == "schema":
            body["schema_version"] = "evil-v9"
        else:
            body["path"] = "/private/secret"
        response = h.raw.post(path, headers=h.headers, json=body)
        assert not h.pair.generator.delegate.requests
        assert response.status_code in {200, 403, 404, 422}
        if response.status_code == 200:
            assert not response.json()["items"]
        if operation == "unregistered_tool":
            assert audit.counts["write_tool"] == 1


def test_emit_receives_safe_copy_and_never_changes_measurement(monkeypatch):
    from personal_ai.evaluation import pi6 as pi6_module

    corpus, _manifest = load_corpus()
    emitted = []

    def fake_dispatch(_task, _arm, **_kwargs):
        return (
            Observation(outcome="correct", hard_valid=True, factual=True),
            {"complete": True, "model_dispatch": 1},
            1.0,
            1.0,
            "untrusted",
        )

    monkeypatch.setattr(pi6_module, "safe_dispatch", fake_dispatch)

    def emit(row):
        emitted.append(json.dumps(row))
        row["observation"]["outcome"] = "changed_by_sink"

    result = pi6_module.evaluate(emit=emit, require_native=False)
    assert all(row["observation"]["outcome"] == "correct" for row in result["rows"])
    raw = "".join(emitted)
    assert not any(
        word in raw
        for word in [
            "Authorization",
            corpus.cases[0].task.value,
            corpus.cases[0].task.subject,
            "PI6 fact:",
            "pi6-synthetic",
        ]
    )
    assert len(emitted) == 68 and result["analysis"]["untrusted_python_only"]


@pytest.mark.loopback_http
def test_calibration_empty_required_source_is_unknown_without_dispatch():
    from personal_ai.evaluation.pi6_driver import dispatch

    case = next(
        c
        for c in load_corpus()[0].cases
        if c.task.family == "retrieval"
        and c.split == "calibration"
        and c.task.variant == "irrelevant"
    )
    observation = dispatch(case.task, "candidate")
    assert observation.outcome == "unknown" and observation.hard_valid
    assert observation.operation_status == "no_match" and observation.evidence_type == "no_evidence"
