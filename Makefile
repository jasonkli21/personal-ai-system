.PHONY: adaptive-routing-eval memory-optimization-eval planning-eval cascade-eval research-eval retrieval-eval decision-eval domain-eval iterative-research-eval itinerary-proposal-eval quota-scarcity-eval memory-lifecycle-eval memory-eval context-eval context-plan-eval backend-test backend-lint backend-build frontend-test frontend-lint frontend-typecheck frontend-build run-backend run-frontend persistence-up persistence-down persistence-ready persistence-bootstrap persistence-clean persistence-test-up persistence-test-down persistence-test
.DEFAULT_GOAL := backend-test

.PHONY: memory-task-eval memory-knowledge-eval memory-knowledge-causal-eval

PLATFORM_PYTHON := backend/.venv/bin/python
UV ?= uv

memory-knowledge-eval:

	cd backend && python -m personal_ai.evaluation.memory_knowledge

memory-knowledge-causal-eval:

	cd backend && python -m personal_ai.evaluation.memory_knowledge_consumer

memory-task-eval:

	cd backend && python -m personal_ai.evaluation.memory_task_baseline

.PHONY: integrated-verification backend-test-offline

.PHONY: naming-policy-check
naming-policy-check:
	$(PLATFORM_PYTHON) -I backend/scripts/naming_policy_check.py
	$(PLATFORM_PYTHON) -I -m unittest discover -s backend/scripts -p test_naming_policy_check.py

.PHONY: real-task-eval
real-task-eval:
	$(PLATFORM_PYTHON) -m personal_ai.evaluation.real_tasks $(REAL_TASK_FLAGS)

integrated-verification:

	cd backend && python -m personal_ai.evaluation.verification

backend-test-offline:

	cd backend && python -m pytest -m 'not persistence_integration and not cloud_smoke' --ignore=tests/test_gemini_manual.py --ignore=tests/test_context_manual.py

adaptive-routing-eval:

	cd backend && python -m personal_ai.evaluation.adaptive_routing

backend-build:

	cd backend && $(UV) build --no-build-isolation --python .venv/bin/python

frontend-build:

	cd frontend && pnpm run build

backend-test:

	cd backend && python -m pytest

backend-lint:

	cd backend && python -m ruff check .

frontend-test:

	cd frontend && pnpm run test

frontend-lint:

	cd frontend && pnpm run lint

frontend-typecheck:

	cd frontend && pnpm run typecheck

run-backend:

	cd backend && python -m uvicorn personal_ai.main:app --reload --port 8000

run-frontend:

	cd frontend && pnpm run dev

context-eval:

	cd backend && python -m personal_ai.evaluation.context

planning-eval:

	cd backend && python -m personal_ai.evaluation.planning

context-plan-eval:

	cd backend && python -m personal_ai.evaluation.context_planner

memory-eval:

	cd backend && python -m personal_ai.evaluation.memory

memory-optimization-eval:

	cd backend && python -m personal_ai.evaluation.memory_optimization

memory-lifecycle-eval:

	cd backend && python -m personal_ai.evaluation.memory_lifecycle

research-eval:

	cd backend && python -m personal_ai.evaluation.research

retrieval-eval:

	cd backend && python -m personal_ai.evaluation.retrieval

decision-eval:

	cd backend && python -m personal_ai.evaluation.decision

domain-eval:
	cd backend && python -m personal_ai_reference_apps.evaluation.domain

iterative-research-eval:
	cd backend && python -m personal_ai.evaluation.iterative_research

itinerary-proposal-eval:
	cd backend && python -m personal_ai_reference_apps.evaluation.itinerary_proposals

quota-scarcity-eval:
	cd backend && python -m personal_ai.evaluation.quota_scarcity

persistence-up:
	docker compose -f docker-compose.persistence.yml up -d --wait postgres dynamodb-local

persistence-down:
	docker compose -f docker-compose.persistence.yml down

persistence-ready:
	cd backend && PERSISTENCE_POSTGRES_DSN='postgresql://personal_ai:personal_ai_local_only@127.0.0.1:54329/personal_ai' DYNAMODB_LOCAL_ENDPOINT='http://127.0.0.1:8000' AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local AWS_DEFAULT_REGION=us-east-1 python -m personal_ai.persistence.local_stack ready

persistence-bootstrap:
	cd backend && PERSISTENCE_POSTGRES_DSN='postgresql://personal_ai:personal_ai_local_only@127.0.0.1:54329/personal_ai' DYNAMODB_LOCAL_ENDPOINT='http://127.0.0.1:8000' AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local AWS_DEFAULT_REGION=us-east-1 python -m personal_ai.persistence.local_stack bootstrap

persistence-clean:
	docker compose -f docker-compose.persistence.yml down -v

persistence-test-up:
	docker compose -f docker-compose.persistence.yml --profile integration up -d --wait postgres-test dynamodb-local-test

persistence-test-down:
	docker compose -f docker-compose.persistence.yml --profile integration stop postgres-test dynamodb-local-test
	docker compose -f docker-compose.persistence.yml --profile integration rm -f postgres-test dynamodb-local-test

persistence-test:
	cd backend && PERSISTENCE_TEST_POSTGRES_DSN='postgresql://personal_ai:personal_ai_test_only@127.0.0.1:54330/personal_ai_test' PERSISTENCE_TEST_DYNAMODB_ENDPOINT='http://127.0.0.1:8001' AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local AWS_DEFAULT_REGION=us-east-1 python -m pytest -m persistence_integration tests/persistence

cascade-eval:
	cd backend && python -m pytest tests/test_cascade_evaluation.py -q -s

.PHONY: memory-control-eval
memory-control-eval:
	cd backend && python -m personal_ai.evaluation.memory_control

.PHONY: reference-build platform-independence-check

reference-build:
	cd reference-apps && $(UV) build --no-build-isolation --python ../backend/.venv/bin/python

platform-independence-check: backend-build reference-build
	$(PLATFORM_PYTHON) backend/scripts/platform_dependency_inventory.py --check
	$(PLATFORM_PYTHON) backend/scripts/core_evaluation_probe.py
	$(PLATFORM_PYTHON) backend/scripts/package_isolation_checks.py

.PHONY: consumer-build consumer-contract-check
consumer-build: backend-build reference-build
	cd examples/reading-logbook/client && $(UV) build --no-build-isolation --python ../../../backend/.venv/bin/python
	cd examples/reading-logbook/host && $(UV) build --no-build-isolation --python ../../../backend/.venv/bin/python

consumer-contract-check: consumer-build
	$(PLATFORM_PYTHON) backend/scripts/platform_dependency_inventory.py --check
	$(PLATFORM_PYTHON) backend/scripts/core_evaluation_probe.py
	$(PLATFORM_PYTHON) backend/scripts/consumer_contract_check.py --check
	$(PLATFORM_PYTHON) backend/scripts/consumer_artifact_checks.py

.PHONY: provider-isolation-check
provider-isolation-check:
	$(PLATFORM_PYTHON) backend/scripts/provider_isolation_checks.py

.PHONY: consent-check
consent-check:
	$(PLATFORM_PYTHON) backend/scripts/profile_consent_checks.py

.PHONY: retrieval-security-check
retrieval-security-check:
	$(PLATFORM_PYTHON) backend/scripts/consumer_contract_check.py --check
	$(PLATFORM_PYTHON) backend/scripts/retrieval_safety_checks.py

.PHONY: offline-benchmark-check
offline-benchmark-check: consumer-build
	$(PLATFORM_PYTHON) backend/scripts/pi6_checks.py
	$(PLATFORM_PYTHON) backend/scripts/pi6_installed_checks.py

.PHONY: installed-core-smoke standalone-consumer-smoke
installed-core-smoke:
	$(PLATFORM_PYTHON) -E -s backend/scripts/installed_core_smoke.py $(CORE_SMOKE_FLAGS)

standalone-consumer-smoke:
	$(PLATFORM_PYTHON) -E -s backend/scripts/installed_core_smoke.py --consumer $(CORE_SMOKE_FLAGS)

.PHONY: cloud-plan-check
CLOUD_PLAN_MANIFEST ?= infrastructure/gcp/cloud-plan.example.json
export CLOUD_PLAN_MANIFEST CLOUD_PLAN_BASELINE
cloud-plan-check:
	@set -- --manifest "$$CLOUD_PLAN_MANIFEST"; \
	if [ -n "$$CLOUD_PLAN_BASELINE" ]; then set -- "$$@" --baseline "$$CLOUD_PLAN_BASELINE"; fi; \
	bash infrastructure/gcp/deploy.sh plan "$$@"

.PHONY: local-store-doctor local-store-up local-store-bootstrap local-store-smoke local-store-down
LOCAL_STORE_SOCKET ?= /var/run/docker.sock
LOCAL_STORE_IMAGE_ARGS ?=
export LOCAL_STORE_SESSION LOCAL_STORE_SOCKET LOCAL_STORE_IMAGE_ARGS
local-store-doctor local-store-up local-store-bootstrap local-store-smoke local-store-down:
	$(PLATFORM_PYTHON) -I backend/scripts/local_storage_smoke.py $(@:local-store-%=%) --session "$$LOCAL_STORE_SESSION" --socket "$$LOCAL_STORE_SOCKET" $(LOCAL_STORE_IMAGE_ARGS)

.PHONY: operations-check
operations-check: cloud-plan-check
	bash -n infrastructure/gcp/deploy.sh
	env -i PATH="$$PATH" TMPDIR="$${TMPDIR:-/tmp}" LITELLM_LOCAL_MODEL_COST_MAP=True \
	  $(PLATFORM_PYTHON) -E -s backend/scripts/signed_http_checks.py -q backend/tests/test_local_operations.py backend/tests/test_deployment_script.py backend/tests/test_inference_execution.py backend/tests/test_litellm_gateway.py backend/tests/test_privacy_usage_controls.py backend/tests/test_provider_usage.py backend/tests/test_retrieval_query_planning.py

.PHONY: release-evidence-check
export RELEASE_EVIDENCE_EXPECTED_COMMIT
release-evidence-check:
	@test -n "$$RELEASE_EVIDENCE_EXPECTED_COMMIT" || { echo "Set RELEASE_EVIDENCE_EXPECTED_COMMIT to the full independently reviewed commit SHA" >&2; exit 2; }
	$(PLATFORM_PYTHON) -I backend/scripts/release_evidence_check.py --expected-commit "$$RELEASE_EVIDENCE_EXPECTED_COMMIT"
	$(PLATFORM_PYTHON) -I -m unittest discover -s backend/scripts -p test_release_evidence_check.py

.PHONY: sdk-build sdk-check
sdk-build:
	cd sdk/python && $(UV) build --no-build-isolation --python ../../backend/.venv/bin/python
	cd examples/project-checklist/client && $(UV) build --no-build-isolation --python ../../../backend/.venv/bin/python
	cd examples/project-checklist/host && $(UV) build --no-build-isolation --python ../../../backend/.venv/bin/python

sdk-check:
	$(PLATFORM_PYTHON) backend/scripts/consumer_contract_check.py --check
	PYTHONPATH=sdk/python/src:examples/project-checklist/client/src:examples/project-checklist/host/src \
	  $(PLATFORM_PYTHON) backend/scripts/offline_test_runner.py -q -m 'not loopback_http' \
	    sdk/python/tests backend/tests/test_external_consumer_http.py backend/tests/test_openapi.py \
	    backend/tests/test_planning_experiment.py backend/tests/test_pi6.py \
	    backend/tests/test_standalone_client.py backend/tests/test_retrieval_context.py \
	    backend/tests/test_retrieval_integrations.py backend/tests/test_application_lifecycle.py \
	    backend/tests/test_inference_execution.py backend/tests/test_provider_usage.py \
	    backend/tests/test_memory_control_api.py backend/tests/test_memory_control_context.py \
	    backend/tests/test_memory_knowledge.py

.PHONY: sdk-install-check
sdk-install-check: sdk-build
	$(PLATFORM_PYTHON) backend/scripts/sdk_install_smoke.py "$(UV)"

.PHONY: mcp-adapter-check
MCP_ADAPTER_PYTHON ?= adapters/mcp_source/.venv/bin/python
MCP_ADAPTER_IMPORT_PATH ?= adapters/mcp_source/src:backend/src
mcp-adapter-check:
	env -i PATH="$$PATH" TMPDIR="$${TMPDIR:-/tmp}" LITELLM_LOCAL_MODEL_COST_MAP=True \
	  PYTHONPATH="$(MCP_ADAPTER_IMPORT_PATH)" $(MCP_ADAPTER_PYTHON) -s backend/scripts/offline_test_runner.py \
	    -q adapters/mcp_source/tests

.PHONY: workflow-check workflow-postgres-check
workflow-check:
	cd backend && python -m pytest -q tests/test_workflow_contract.py tests/test_mutations.py

workflow-postgres-check:
	test -n "$$PERSISTENCE_TEST_POSTGRES_DSN"
	cd backend && python -m pytest -q tests/persistence/test_workflow_postgres.py

.PHONY: release-profile-check release-preflight release-build-report release-canary-check
release-profile-check:
	$(PLATFORM_PYTHON) -I -m unittest discover -s backend/scripts -p 'test_release_profiles.py'
	$(PLATFORM_PYTHON) -I -m unittest discover -s backend/scripts -p 'test_release_artifacts.py'

release-preflight:
	$(PLATFORM_PYTHON) -E -s backend/scripts/release_preflight.py

release-build-report:
	$(PLATFORM_PYTHON) -E -s backend/scripts/release_artifacts.py build --uv "$$(command -v $(UV))"

release-canary-check:
	$(PLATFORM_PYTHON) -E -s backend/scripts/release_preflight.py --measure-synthetic

.PHONY: memory-episode-candidate-eval memory-episode-candidate-check
memory-episode-candidate-eval:
	cd backend && python -m personal_ai.evaluation.episode_candidates

memory-episode-candidate-check:
	cd backend && python -m pytest -q tests/test_episode_candidates.py

.PHONY: memory-episode-check memory-episode-postgres-check
memory-episode-check:
	cd backend && python -m pytest -q tests/test_episode_candidates.py tests/test_episode_service.py

memory-episode-postgres-check:
	test -n "$(PERSISTENCE_TEST_POSTGRES_DSN)"
	cd backend && python -m pytest -q tests/persistence/test_episode_postgres.py

.PHONY: memory-consolidation-check memory-consolidation-eval
memory-consolidation-check:
	cd backend && python -m pytest -q tests/test_offline_consolidation.py tests/test_consolidation_adversarial.py

memory-consolidation-eval:
	cd backend && python -m personal_ai.evaluation.consolidation
	cd backend && python -m personal_ai.evaluation.consolidation_quality

.PHONY: memory-consolidation-postgres-check
memory-consolidation-postgres-check:
	test -n "$$PERSISTENCE_TEST_POSTGRES_DSN"
	cd backend && python -m pytest -q tests/persistence/test_consolidation_postgres.py

.PHONY: memory-navigation-check memory-navigation-eval memory-navigation-postgres-check
memory-navigation-check:
	cd backend && python -m pytest -q tests/test_memory_navigation.py tests/test_memory_navigation_evaluation.py

memory-navigation-eval:
	cd backend && python -m personal_ai.evaluation.memory_navigation

memory-navigation-postgres-check:
	cd backend && python -c 'import os, sys; sys.exit(0 if os.environ.get("PERSISTENCE_TEST_POSTGRES_DSN") else "BLOCKED: configure a disposable PERSISTENCE_TEST_POSTGRES_DSN")'
	cd backend && python -m pytest -q tests/persistence/test_local_persistence.py -k pgvector
	cd backend && python -m pytest -q tests/persistence/test_verified_knowledge_postgres.py
