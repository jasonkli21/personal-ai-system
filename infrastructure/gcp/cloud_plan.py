"""Validate a proposed cloud topology against a closed, static policy."""

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path

VERSION = "cloud-plan-check-v1"
UNVERIFIED_BINDINGS = [
    "project_number_to_live_project",
    "run_app_audiences_to_deployed_services",
    "service_accounts_and_iam_existence",
    "image_digest_provenance_and_registry_policy",
    "neon_secret_version_and_host_ownership",
    "aws_role_trust_and_dynamodb_resources",
    "network_routes_and_effective_egress",
    "provider_account_caps_and_billed_cost",
]
MAX_BYTES = 32_768
FIELDS = {
    "schema",
    "target",
    "project",
    "project_number",
    "region",
    "images",
    "identity",
    "services",
    "iam",
    "storage",
    "egress",
    "inference",
    "limits",
    "features",
    "rollback",
}
FEATURES = {
    key: False
    for key in (
        "reference_apps",
        "external_consumers",
        "external_turns",
        "profile_sharing",
        "retrieval",
        "research",
        "memory",
        "memory_controls",
        "agents",
        "maintenance",
        "export",
        "deletion",
    )
}
INFERENCE = {
    "provider": "fake",
    "profile": "offline_fake",
    "cost_mode": "offline_fake",
    "summary": "disabled",
    "extraction": "disabled",
    "embedding": "disabled",
    "external_provider_kill_switch": True,
    "source_scopes": [],
}
LIMITS = {
    "api_requests_per_minute": 60,
    "model_physical_calls": 0,
    "search_physical_calls": 0,
    "provider_spend_microusd": 0,
}
EGRESS = {
    "policy": "default_deny",
    "web": ["api", "google_oidc"],
    "api": ["google_oidc", "neon", "aws_sts", "dynamodb"],
    "worker": ["google_oidc", "neon", "aws_sts", "dynamodb"],
}


class Refused(ValueError):
    """Messages are fixed refusal codes, with no input interpolation."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def require(condition, code):
    if not condition:
        raise Refused(code)


def exact(actual, expected, code):
    require(canonical(actual) == canonical(expected), code)


def shape(value, keys, code):
    require(isinstance(value, dict) and set(value) == keys, code)


def matches(value, pattern, code):
    require(isinstance(value, str) and re.fullmatch(pattern, value) is not None, code)


HOST = r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}"
HTTPS = "https://" + HOST


def service_policy(project, project_number, api_audience, worker_audience):
    domain = f"@{project}.iam.gserviceaccount.com"
    accounts = {
        name: f"personal-ai-{name}{domain}"
        for name in (
            "web-runtime",
            "api-runtime",
            "worker-runtime",
            "pubsub-invoker",
        )
    }
    services = {
        "web": {
            "account": accounts["web-runtime"],
            "ingress": "public",
            "invoker": "public",
            "concurrency": 20,
            "min_instances": 0,
            "max_instances": 1,
            "proxy": {
                "target": "api",
                "audience": api_audience,
                "forward_verified_user_jwt": True,
            },
        },
        "api": {
            "account": accounts["api-runtime"],
            "ingress": "internal",
            "invoker": accounts["web-runtime"],
            "audience": api_audience,
            "concurrency": 10,
            "min_instances": 0,
            "max_instances": 1,
        },
        "worker": {
            "account": accounts["worker-runtime"],
            "ingress": "internal",
            "invoker": accounts["pubsub-invoker"],
            "audience": worker_audience,
            "push_auth": "google_oidc",
            "push_endpoint": "/tasks/memory",
            "concurrency": 1,
            "min_instances": 0,
            "max_instances": 1,
        },
    }
    iam = {
        "api_invoker": [accounts["web-runtime"]],
        "worker_invoker": [accounts["pubsub-invoker"]],
        "neon_secret_accessor": [accounts["api-runtime"], accounts["worker-runtime"]],
        "pubsub_publishers": [accounts["api-runtime"]],
        "pubsub_token_creator": {
            "member": f"service-{project_number}@gcp-sa-pubsub.iam.gserviceaccount.com",
            "target": accounts["pubsub-invoker"],
        },
    }
    return services, iam


def validate(plan):
    shape(plan, FIELDS, "manifest_shape")
    exact(plan["schema"], VERSION, "schema")
    require(plan["target"] == "staging", "target_requires_separate_review")
    project, region = plan["project"], plan["region"]
    matches(project, r"[a-z][a-z0-9-]{4,28}[a-z0-9]", "project")
    require(not project.startswith("goog"), "project")
    matches(plan["project_number"], r"[1-9][0-9]{5,19}", "project_number")
    matches(
        region,
        r"(?:africa|asia|australia|europe|me|northamerica|southamerica|us)-[a-z]+[1-9][0-9]*",
        "region",
    )
    prefix = re.escape(f"{region}-docker.pkg.dev/{project}/personal-ai/")
    shape(plan["images"], {"web", "api", "worker"}, "images")
    for name, repository in (
        ("web", "frontend"),
        ("api", "backend"),
        ("worker", "backend"),
    ):
        matches(
            plan["images"][name],
            prefix + repository + "@sha256:[a-f0-9]{64}",
            "image_digest",
        )
    require(plan["images"]["api"] == plan["images"]["worker"], "api_worker_image_drift")

    identity = plan["identity"]
    shape(
        identity,
        {
            "issuer",
            "auth_mode",
            "auth_required",
            "audience",
            "owner_email",
            "hosted_domain",
            "web_origin",
            "api_audience",
            "worker_audience",
        },
        "identity_shape",
    )
    exact(identity["issuer"], "https://accounts.google.com", "identity_issuer")
    exact(identity["auth_mode"], "google_oidc", "user_auth_mode")
    exact(identity["auth_required"], True, "user_auth_required")
    matches(
        identity["audience"],
        r"[a-z0-9-]{8,120}\.apps\.googleusercontent\.com",
        "user_audience",
    )
    matches(identity["owner_email"], r"[a-z0-9._%+-]{1,64}@" + HOST, "owner_allowlist")
    domain = identity["owner_email"].rsplit("@", 1)[1]
    exact(
        identity["hosted_domain"],
        "" if domain == "gmail.com" else domain,
        "hosted_domain",
    )
    matches(identity["web_origin"], HTTPS, "cors_origin")
    for name in ("api_audience", "worker_audience"):
        matches(
            identity[name],
            r"https://[a-z][a-z0-9-]{2,62}(?:\.[a-z0-9-]+)*\.run\.app",
            "service_audience",
        )
    require(
        identity["api_audience"] != identity["worker_audience"],
        "shared_service_audience",
    )
    services, iam = service_policy(
        project,
        plan["project_number"],
        identity["api_audience"],
        identity["worker_audience"],
    )
    exact(plan["services"], services, "service_ingress_identity_or_limits")
    exact(plan["iam"], iam, "iam_policy")

    storage = plan["storage"]
    shape(
        storage,
        {
            "neon_secret_version",
            "neon_host",
            "aws_role",
            "aws_audience",
            "aws_google_claims",
            "aws_region",
            "dynamodb_table",
        },
        "storage_shape",
    )
    matches(
        storage["neon_secret_version"],
        re.escape(f"projects/{project}/secrets/")
        + r"[a-zA-Z0-9_-]{1,128}/versions/[1-9][0-9]*",
        "neon_secret_reference",
    )
    matches(
        storage["neon_host"],
        r"ep-[a-z0-9-]+-pooler\.[a-z0-9.-]+\.neon\.tech",
        "neon_pooler",
    )
    matches(
        storage["aws_role"],
        r"arn:aws:iam::[0-9]{12}:role/[A-Za-z0-9+=,.@_-]{1,64}",
        "aws_role",
    )
    matches(storage["aws_audience"], HTTPS + "/personal-ai-runtime", "aws_audience")
    matches(
        storage["aws_region"],
        r"(?:af|ap|ca|eu|il|me|mx|sa|us)-[a-z]+-[1-9][0-9]*",
        "aws_region",
    )
    matches(storage["dynamodb_table"], r"[A-Za-z0-9_.-]{3,255}", "dynamodb_table")
    claims = storage["aws_google_claims"]
    shape(claims, {"api", "worker"}, "aws_runtime_claims")
    for service, binding in claims.items():
        shape(binding, {"account", "sub", "azp_or_aud", "oaud"}, "aws_runtime_claims")
        exact(binding["account"], services[service]["account"], "aws_runtime_account")
        exact(binding["oaud"], storage["aws_audience"], "aws_runtime_audience")
        for key in ("sub", "azp_or_aud"):
            matches(binding[key], r"[1-9][0-9]{15,29}", "aws_runtime_numeric_claim")
    require(
        claims["api"]["sub"] != claims["worker"]["sub"], "shared_aws_runtime_subject"
    )
    exact(plan["egress"], EGRESS, "egress_policy")
    exact(plan["inference"], INFERENCE, "inference_requires_offline_fake")
    exact(plan["limits"], LIMITS, "budget_policy")
    exact(plan["features"], FEATURES, "features_require_separate_review")
    exact(plan["rollback"], "quarantine_and_review_prior_revision", "rollback_policy")


def unique_object(pairs):
    result = dict(pairs)
    require(len(result) == len(pairs), "duplicate_manifest_key")
    return result


def invalid_constant(_):
    raise Refused("invalid_json_constant")


def read_manifest(path):
    # Nonblocking open rejects FIFOs before reading. Reading is size bounded
    # even when the file grows after fstat. Parser messages can contain inputs.
    try:
        with open(
            path, "rb", opener=lambda p, _: os.open(p, os.O_RDONLY | os.O_NONBLOCK)
        ) as stream:
            require(
                stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "manifest_not_regular"
            )
            raw = stream.read(MAX_BYTES + 1)
        require(len(raw) <= MAX_BYTES, "manifest_too_large")
        result = json.loads(
            raw, object_pairs_hook=unique_object, parse_constant=invalid_constant
        )
        validate(result)
        return result
    except Refused:
        raise
    except (ValueError, OSError, RecursionError):
        raise Refused("manifest_unreadable_or_invalid") from None


class PlanParser(argparse.ArgumentParser):
    def error(self, _message):
        raise Refused("invalid_plan_arguments")


def main():
    parser = PlanParser(description=__doc__, allow_abbrev=False)
    # Unknown tokens may contain secrets. Never let argparse render them.
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--baseline", type=Path)
    try:
        args, unknown = parser.parse_known_args()
        require(not unknown and args.manifest, "explicit_manifest_required")
        plan = read_manifest(args.manifest)
        baseline = read_manifest(args.baseline) if args.baseline else None
        changes = (
            sorted(
                name
                for name in FIELDS
                if canonical(plan[name]) != canonical(baseline[name])
            )
            if baseline is not None
            else None
        )
        print(
            json.dumps(
                {
                    "schema": VERSION,
                    "status": "blocked_drift" if changes else "static_policy_validated_only",
                    "plan_sha256": hashlib.sha256(canonical(plan).encode()).hexdigest(),
                    "baseline": "operator_file"
                    if baseline is not None
                    else "not_supplied",
                    "changed_sections": changes,
                    "evidence": "static_only",
                    "verified_live_bindings": [],
                    "unverified_bindings": UNVERIFIED_BINDINGS,
                    "apply": "blocked_unverified",
                    "provider_cost": {
                        "configured_remote_budget_microusd": 0,
                        "billed": "unobserved",
                    },
                    "rollback": plan["rollback"],
                },
                sort_keys=True,
            )
        )
        return 2 if changes else 0
    except Refused as error:
        print(
            json.dumps({"schema": VERSION, "status": "refused", "reason": str(error)})
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
