"""Executable acceptance checks for the offline Phase 13 baseline."""

import json

import pytest

from personal_ai.applications.registry import (
    ApplicationNotRegisteredError,
    default_application_registry,
)
from personal_ai.context.contracts import TokenCount
from personal_ai.evaluation import context_planner


def test_context_planner_baseline_passes_all_offline_fixtures():
    rows = context_planner.evaluate()

    assert rows
    assert all(row["result"] == "passed" for row in rows)


def test_reference_fixtures_remain_explicit_and_scored_in_core_only_profile():
    fixtures = json.loads(context_planner.FIXTURE_PATH.read_text())["fixtures"]
    rows = context_planner.evaluate()
    expected_ids = [fixture["name"] for fixture in fixtures]

    assert [row["fixture"] for row in rows] == expected_ids
    assert len(rows) == 9
    assert default_application_registry().application_ids == {"personal_ai"}
    with pytest.raises(ApplicationNotRegisteredError):
        default_application_registry().get("travel")

    reference_rows = {
        row["fixture"]: row for row in rows if row["fixture"].startswith("synthetic-")
    }
    assert set(reference_rows) == {
        "synthetic-travel-hotel-dates",
        "synthetic-shopping-saved-chair",
        "synthetic-finance-cash-position",
        "synthetic-health-medication-history",
    }
    assert all(row["result"] == "passed" and row["expected_fields"] for row in reference_rows.values())
    assert sum(row["selected_source_count"] for row in reference_rows.values()) == 4


def test_positive_memory_fixture_fails_when_source_budget_omits_support():
    fixtures = json.loads(context_planner.FIXTURE_PATH.read_text())["fixtures"]
    fixture = next(item for item in fixtures if item["name"] == "standalone-personal-recall")

    class OversizedSourceCounter:
        def count(self, messages):
            if any("Context source item" in message.content for message in messages):
                return TokenCount(100_000, "estimated")
            return context_planner._EnvelopeTokenCounter().count(messages)

    row = context_planner._run_fixture(fixture, counter=OversizedSourceCounter())

    assert row["result"] == "failed"
    assert row["answer_support_needs_planned"]
    assert not row["answer_support_needs_injected"]
    assert row["injected_support_fields"] == []


def test_positive_profile_fixture_fails_when_sharing_permission_omits_field():
    fixtures = json.loads(context_planner.FIXTURE_PATH.read_text())["fixtures"]
    fixture = next(item for item in fixtures if item["name"] == "standalone-profile-units")
    fixture = {**fixture, "shared_profile_fields": []}

    row = context_planner._run_fixture(fixture)

    assert row["result"] == "failed"
    assert not row["answer_support_needs_injected"]
    assert row["retrieved_support_fields"] == []
    assert row["injected_support_fields"] == []


def test_context_plan_evaluation_exits_nonzero_when_any_fixture_fails(monkeypatch, capsys):
    monkeypatch.setattr(context_planner, "evaluate", lambda: [{"result": "failed"}])

    assert context_planner.main() == 1
    assert '"result": "failed"' in capsys.readouterr().out
