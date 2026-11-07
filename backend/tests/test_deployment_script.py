"""Static deployment boundary with a tripwire for any cloud CLI invocation."""

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "infrastructure/gcp/deploy.sh"
EXAMPLE = SCRIPT.with_name("cloud-plan.example.json")
CANARY = "PRIVATE_CANARY_NEVER_ECHO_4369"


@pytest.fixture
def shell(tmp_path):
    tripwire = tmp_path / "commands"
    for name in ("gcloud", "docker", "aws", "curl"):
        executable = tmp_path / name
        executable.write_text('#!/bin/sh\necho called >> "$TRIPWIRE"\nexit 33\n')
        executable.chmod(0o755)
    env = {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "TRIPWIRE": str(tripwire),
        "AI_API_KEY": CANARY,
        "NEON_RUNTIME_DSN_SECRET_NAME": CANARY,
        "PRODUCTION_DEPLOY_ACK": "I_REVIEWED_THE_PRODUCTION_CHANGE",
        "MAINTENANCE_ENABLED": "true",
    }

    def run(*args):
        result = subprocess.run(
            ["/bin/bash", str(SCRIPT), *map(str, args)],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        assert not tripwire.exists()
        assert CANARY not in result.stdout + result.stderr
        return result

    return run


def test_static_plan_and_baseline_never_invoke_cloud(shell):
    result = shell("plan", "--manifest", EXAMPLE, "--baseline", EXAMPLE)
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["status"] == "static_policy_validated_only"
    assert plan["changed_sections"] == []
    assert plan["evidence"] == "static_only"
    assert plan["verified_live_bindings"] == []
    assert "project_number_to_live_project" in plan["unverified_bindings"]
    assert "run_app_audiences_to_deployed_services" in plan["unverified_bindings"]
    assert plan["apply"] == "blocked_unverified"
    assert plan["provider_cost"] == {"configured_remote_budget_microusd": 0, "billed": "unobserved"}
    assert "operator@example.test" not in result.stdout and "projects/" not in result.stdout


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("apply", "--manifest", EXAMPLE),
        ("production", CANARY),
        ("staging", CANARY),
        ("plan", "--manifest", EXAMPLE, "--bogus", CANARY),
    ],
)
def test_legacy_default_and_apply_cannot_invoke_cloud(shell, args):
    assert shell(*args).returncode == 2


@pytest.mark.parametrize(
    ("path", "value", "reason"),
    [
        (("project",), CANARY, "project"),
        (("region",), "https://example.test", "region"),
        (("target",), "production", "target_requires_separate_review"),
        (("images", "api"), "backend:latest", "image_digest"),
        (("identity", "issuer"), "https://evil.example.test", "identity_issuer"),
        (("identity", "web_origin"), "https://example.test/path", "cors_origin"),
        (("identity", "api_audience"), "http://api.run.app", "service_audience"),
        (("storage", "neon_secret_version"), CANARY, "neon_secret_reference"),
        (
            ("storage", "neon_secret_version"),
            "projects/synthetic-deployment/secrets/dsn/versions/latest",
            "neon_secret_reference",
        ),
        (("services", "api", "ingress"), "public", "service_ingress_identity_or_limits"),
        (("services", "worker", "concurrency"), True, "service_ingress_identity_or_limits"),
        (("identity", "auth_required"), False, "user_auth_required"),
        (("identity", "hosted_domain"), "", "hosted_domain"),
        (
            ("storage", "aws_google_claims", "api", "sub"),
            "runtime@example.test",
            "aws_runtime_numeric_claim",
        ),
        (
            ("storage", "aws_google_claims", "api", "oaud"),
            "https://wrong.example.test",
            "aws_runtime_audience",
        ),
        (
            ("storage", "aws_google_claims", "worker", "sub"),
            "100000000000000000001",
            "shared_aws_runtime_subject",
        ),
        (("iam", "pubsub_token_creator", "member"), "allUsers", "iam_policy"),
        (("iam", "worker_invoker"), ["allUsers"], "iam_policy"),
        (("egress", "worker"), ["*"], "egress_policy"),
        (("features", "memory_controls"), True, "features_require_separate_review"),
        (("inference", "cost_mode"), "strict_free", "inference_requires_offline_fake"),
        (("inference", "cost_mode"), "explicit_paid", "inference_requires_offline_fake"),
        (("inference", "source_scopes"), ["*"], "inference_requires_offline_fake"),
        (("limits", "model_physical_calls"), 1, "budget_policy"),
        (("limits", "provider_spend_microusd"), float("nan"), "invalid_json_constant"),
    ],
)
def test_malformed_or_expanding_policy_is_refused(shell, tmp_path, path, value, reason):
    manifest = json.loads(EXAMPLE.read_text())
    section = manifest
    for key in path[:-1]:
        section = section[key]
    section[path[-1]] = value
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps(manifest))
    result = shell("plan", "--manifest", candidate)
    assert result.returncode == 2
    assert json.loads(result.stdout)["reason"] == reason


def test_valid_static_drift_requires_review_and_prints_only_section(shell, tmp_path):
    manifest = json.loads(EXAMPLE.read_text())
    manifest["identity"]["owner_email"] = "different-owner@example.test"
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps(manifest))
    result = shell("plan", "--manifest", candidate, "--baseline", EXAMPLE)
    assert result.returncode == 2
    assert json.loads(result.stdout)["changed_sections"] == ["identity"]
    assert "different-owner" not in result.stdout + result.stderr


def test_consistent_unbound_resource_names_remain_policy_only(shell, tmp_path):
    manifest = json.loads(EXAMPLE.read_text())
    manifest["identity"]["api_audience"] = "https://unrelated-service.run.app"
    manifest["services"]["api"]["audience"] = manifest["identity"]["api_audience"]
    manifest["services"]["web"]["proxy"]["audience"] = manifest["identity"]["api_audience"]
    manifest["project_number"] = "999999999999"
    manifest["iam"]["pubsub_token_creator"]["member"] = (
        "service-999999999999@gcp-sa-pubsub.iam.gserviceaccount.com"
    )
    candidate = tmp_path / "unbound.json"
    candidate.write_text(json.dumps(manifest))
    result = shell("plan", "--manifest", candidate)
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["status"] == "static_policy_validated_only"
    assert plan["verified_live_bindings"] == []
    assert "run_app_audiences_to_deployed_services" in plan["unverified_bindings"]
    assert "project_number_to_live_project" in plan["unverified_bindings"]


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (b'{"schema":"one","schema":"two"}', "duplicate_manifest_key"),
        (CANARY.encode(), "manifest_unreadable_or_invalid"),
        (b" " * 32769, "manifest_too_large"),
    ],
)
def test_untrusted_json_is_bounded_and_never_echoed(shell, tmp_path, content, reason):
    candidate = tmp_path / "candidate.json"
    candidate.write_bytes(content)
    result = shell("plan", "--manifest", candidate)
    assert result.returncode == 2
    assert json.loads(result.stdout)["reason"] == reason


def test_non_regular_manifest_returns_without_waiting_for_writer(shell, tmp_path):
    candidate = tmp_path / "fifo"
    os.mkfifo(candidate)
    result = shell("plan", "--manifest", candidate)
    assert result.returncode == 2
    assert json.loads(result.stdout)["reason"] == "manifest_not_regular"
