"""Shared expensive hermetic study fixture; no external services."""

from functools import lru_cache

import pytest


@lru_cache(maxsize=1)
def research_data():
    from personal_ai.evaluation.memory_longitudinal.campaign import campaign
    from personal_ai.evaluation.memory_longitudinal.scorer import analyze
    from personal_ai.evaluation.memory_longitudinal.study import make_run, replay

    run = make_run()
    rows = replay(run)
    report, metrics = analyze(run, rows, campaign())
    return run, rows, report, metrics


@pytest.fixture(scope="session")
def research_run():
    return research_data()
