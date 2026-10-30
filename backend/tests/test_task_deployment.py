"""Current write capabilities and retained observation adapters remain separate."""

import base64

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from personal_ai_reference_apps.applications import (
    reference_application_registry as default_application_registry,
)
from personal_ai_reference_apps.tasks import configured_task_contribution

from personal_ai.mutations.deployment import install_task_metadata
from personal_ai.settings import Settings


def settings(enabled):
    key = Ed25519PrivateKey.generate()
    return Settings(
        _env_file=None,
        ai_provider="fake",
        ai_model="fake",
        app_environment="test",
        auth_mode="google_oidc",
        auth_required=True,
        auth_audience="synthetic-client",
        auth_allowed_emails=("owner@gmail.com",),
        task_delegation_enabled=True,
        task_delegation_audience="https://pai.invalid",
        task_delegation_issuer="pai",
        task_delegation_key_id="key",
        task_delegation_private_key=base64.urlsafe_b64encode(key.private_bytes_raw()).decode(),
        task_domain_service_account="pai@synthetic.iam.gserviceaccount.com",
        task_shopping_enabled=enabled,
        task_shopping_base_url="https://shopping.invalid",
        task_shopping_audience="https://shopping.invalid",
        task_shopping_operation_fingerprint="a" * 64,
        task_shopping_note_operation_fingerprint="b" * 64,
        task_callback_accounts={"shopping": "shopping@synthetic.iam.gserviceaccount.com"},
        task_shopping_retained_operation_fingerprints={"project.set_budget": ("c" * 64,)},
    )


def test_draining_disables_new_writes_but_keeps_exact_old_reconciliation():
    runtime = configured_task_contribution(settings(False))
    assert runtime.mutation_adapters == {}
    assert set(runtime.mutation_reconciliation_adapters) == {
        ("shopping", "project.set_budget", 1, "a" * 64),
        ("shopping", "project.set_budget", 1, "c" * 64),
        ("shopping", "project.append_context_note", 1, "b" * 64),
    }


def test_metadata_installs_only_current_pinned_operations_once():
    config = settings(True)
    runtime = configured_task_contribution(config)
    registry = install_task_metadata(default_application_registry(), config, runtime)
    assert install_task_metadata(registry, config, runtime) is registry
    assert {item.contract_fingerprint for item in registry.get("shopping").mutation_operations} == {
        "a" * 64,
        "b" * 64,
    }
