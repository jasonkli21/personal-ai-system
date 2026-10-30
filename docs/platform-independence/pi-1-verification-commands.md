# PI-1 reproducible verification commands

2026-10-30. Run at repository root with existing dependencies; no download,
credentials, .env, native-store or live-provider execution is authorized here.
Commands below identify the implementation report's C1–C8 checks. Python audit
fencing covers Python socket APIs, not arbitrary native code/OS-wide networking.

C1 — built artifacts, metadata, real installed core/reference/uninstall/restore:

```sh
export UV_CACHE_DIR=/private/tmp/pi1-uv-cache
export UV_OFFLINE=true
export PATH="$PWD/backend/.venv/bin:$PATH"
make backend-build reference-build
backend/.venv/bin/python backend/scripts/pi1_artifact_checks.py
```

The artifact script creates `/private/tmp/pi1-installed-*`, physically copies the
existing venv's dependency files while excluding `.pth`, editable hooks and
platform packages, installs the built wheel with `uv --no-index --no-deps`, and
runs copied probes/tests there. Each subprocess gets an explicit clean environment
without PYTHONPATH. Dependency inventory is saved as `dependency-files.json` in
that workspace. It does not claim a fresh network dependency resolution or native
store acceptance. Copied test files resolve installed modules, not source trees.

C2 — core/context/auth/MEM/Phase36 regression (the shell line continuation is
literal; no local environment files):

```sh
env -i PATH="$PWD/backend/.venv/bin:/usr/bin:/bin" \
  AI_PROVIDER=gemini AI_MODEL=pi1-fixture PYTHONDONTWRITEBYTECODE=1 \
  backend/.venv/bin/python backend/scripts/pi1_offline_checks.py -q \
  backend/tests/test_platform_independence.py backend/tests/test_reference_persistence.py \
  backend/tests/test_conversation_routes.py backend/tests/test_context_authorization.py \
  backend/tests/test_context_sources.py backend/tests/test_context_provider.py \
  backend/tests/test_context_routes.py backend/tests/test_context_builder.py \
  backend/tests/test_context_traces.py backend/tests/test_auth.py \
  backend/tests/test_task_deployment.py backend/tests/test_phase36_integrated.py \
  backend/tests/test_memory_control.py backend/tests/test_memory_control_api.py \
  backend/tests/test_memory_control_context.py backend/tests/test_memory_knowledge.py \
  backend/tests/test_mem0_task_baseline.py backend/tests/test_memory_phase34.py \
  backend/tests/test_memory_worker.py backend/tests/test_external_turn_composition.py \
  backend/tests/test_openapi.py backend/tests/test_health.py
```

C3 — reference compatibility:

```sh
env -i PATH="$PWD/backend/.venv/bin:/usr/bin:/bin" \
  AI_PROVIDER=gemini AI_MODEL=pi1-fixture PYTHONDONTWRITEBYTECODE=1 \
  backend/.venv/bin/python backend/scripts/pi1_offline_checks.py -q \
  backend/tests/test_applications.py backend/tests/test_context_runtime_composition.py \
  backend/tests/test_application_scope.py backend/tests/test_federation.py \
  backend/tests/test_mutations.py backend/tests/test_task_deployment.py \
  backend/tests/test_travel_context.py backend/tests/test_shopping_context.py \
  backend/tests/test_finance_context.py backend/tests/test_health_context.py \
  backend/tests/test_health_federation.py backend/tests/test_booking_extractions.py \
  backend/tests/test_itinerary_proposals.py backend/tests/test_domains.py \
  backend/tests/test_domain_evaluation.py backend/tests/test_platform_dependency_inventory.py
```

C4 — additional inspected fake-backed core utility:

```sh
env -i PATH="$PWD/backend/.venv/bin:/usr/bin:/bin" \
  AI_PROVIDER=gemini AI_MODEL=pi1-fixture PYTHONDONTWRITEBYTECODE=1 \
  backend/.venv/bin/python backend/scripts/pi1_offline_checks.py -q \
  backend/tests/test_memory_integration.py backend/tests/test_memory_disclosure_authorization.py \
  backend/tests/test_research_routes.py backend/tests/test_iterative_research_routes.py \
  backend/tests/test_memory.py
```

C5 — delegated identity, frozen MEM-1 paired/consumer and added negative tests:

```sh
env -i PATH="$PWD/backend/.venv/bin:/usr/bin:/bin" \
  AI_PROVIDER=gemini AI_MODEL=pi1-fixture PYTHONDONTWRITEBYTECODE=1 \
  backend/.venv/bin/python backend/scripts/pi1_offline_checks.py -q \
  backend/tests/test_delegated_tasks.py backend/tests/test_memory_knowledge_evaluation.py \
  backend/tests/test_memory_knowledge_consumer.py backend/tests/test_platform_independence.py \
  backend/tests/test_reference_persistence.py
```

C6 — static guard (including injected forbidden-edge tests), lint, whitespace:

```sh
backend/.venv/bin/python backend/scripts/platform_dependency_inventory.py --check
backend/.venv/bin/python -m unittest discover -s backend/tests -p test_platform_dependency_inventory.py -v
PATH="$PWD/backend/.venv/bin:$PATH" make backend-lint
backend/.venv/bin/python -m ruff check reference-apps
git diff --check
```

C7 — frontend (existing dependencies, bundled Node; gates remain off by default):

```sh
export PATH="/Users/jasonkli/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH"
make frontend-test frontend-lint frontend-typecheck frontend-build
```

C8 — source/fixture preservation: verify the SHA-256 records in
`pi-1-source-manifest.json`, compare its frozen paths against the initial revision,
and inspect `git diff --name-status 623327da171d4acd3d48d96a4c50bd40394c1925`.
No migration, memory implementation, historical lock/fixture or frontend file is
expected to differ. The new packaged itinerary fixture must match the historical
fixture hash. This check binds source identity; it does not execute SQL migrations.
