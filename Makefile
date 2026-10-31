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
	$(PLATFORM_PYTHON) backend/scripts/pi1_core_evaluation_probe.py
	$(PLATFORM_PYTHON) backend/scripts/pi1_artifact_checks.py

.PHONY: pi2-build pi2-check
pi2-build: backend-build reference-build
	cd examples/reading-logbook/client && $(UV) build --no-build-isolation --python ../../../backend/.venv/bin/python
	cd examples/reading-logbook/host && $(UV) build --no-build-isolation --python ../../../backend/.venv/bin/python

pi2-check: pi2-build
	$(PLATFORM_PYTHON) backend/scripts/platform_dependency_inventory.py --check
	$(PLATFORM_PYTHON) backend/scripts/pi1_core_evaluation_probe.py
	$(PLATFORM_PYTHON) backend/scripts/pi2_contract.py --check
	$(PLATFORM_PYTHON) backend/scripts/pi2_artifact_checks.py

.PHONY: pi3-check
pi3-check:
	$(PLATFORM_PYTHON) backend/scripts/pi3_checks.py

.PHONY: pi4-check
pi4-check:
	$(PLATFORM_PYTHON) backend/scripts/pi4_checks.py
