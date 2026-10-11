"""Budget snapshot construction and reservation-ledger calculations."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

from personal_ai.agents.research.contracts import ResearchError
from personal_ai.agents.research.iterative.contracts import (
    BudgetLedgerEntry,
    BudgetSnapshot,
    BudgetUsage,
    ResearchRun,
    RunState,
)
from personal_ai.settings import Settings


def build_budget(settings: Settings) -> BudgetSnapshot:
    return BudgetSnapshot(
        max_iterations=settings.iterative_max_iterations,
        max_queries=settings.iterative_max_queries,
        max_sources=settings.iterative_max_sources,
        max_elapsed_seconds=settings.iterative_max_elapsed_seconds,
        max_tokens=settings.iterative_max_tokens,
        max_provider_cost_usd=settings.iterative_max_provider_cost_usd,
        allowed_domains=settings.iterative_allowed_domains,
        synthesis_reserve_tokens=settings.iterative_synthesis_reserve_tokens,
        synthesis_reserve_seconds=settings.iterative_synthesis_reserve_seconds,
        synthesis_reserve_cost_usd=settings.iterative_synthesis_cost_usd,
        search_cost_usd=settings.iterative_search_cost_usd,
        provider_timeout_seconds=settings.research_provider_timeout_seconds,
        attempt_limit=settings.research_attempt_limit,
        synthesis_output_tokens=min(
            settings.max_response_tokens,
            settings.iterative_synthesis_reserve_tokens,
        ),
    )


def pending(run: ResearchRun, dimension: str) -> Decimal:
    return sum(
        (
            entry.reserved
            for entry in run.ledger
            if entry.dimension == dimension and entry.status == "reserved"
        ),
        Decimal(0),
    )


def reserved_or_used(run: ResearchRun, dimension: str) -> Decimal:
    return sum(
        (
            entry.settled if entry.settled is not None else entry.reserved
            for entry in run.ledger
            if entry.dimension == dimension
        ),
        Decimal(0),
    )


def remaining_elapsed(run: ResearchRun, now: datetime) -> float:
    wall_used = max(0.0, (now - run.created_at).total_seconds())
    reserved_synthesis = (
        0 if run.state == RunState.SYNTHESIZING else run.budget.synthesis_reserve_seconds
    )
    return max(0.0, run.budget.max_elapsed_seconds - wall_used - reserved_synthesis)


def settle_pending_for_stop(
    run: ResearchRun, *, clock: Callable[[], datetime], uncertain: bool
) -> tuple[list[BudgetLedgerEntry], BudgetUsage]:
    new_ledger = []
    totals = Counter()
    for entry in run.ledger:
        if entry.status != "reserved":
            new_ledger.append(entry)
            if entry.settled is not None:
                totals[entry.dimension] += entry.settled
            continue
        if entry.idempotency_key == "reserve:run:elapsed":
            settled = Decimal(str(max(0.0, (clock() - run.created_at).total_seconds())))
            updated = entry.model_copy(update={"settled": settled, "status": "settled"})
            new_ledger.append(updated)
            totals[entry.dimension] += settled
            continue
        affected = uncertain and (
            entry.idempotency_key.startswith("attempt:")
            and run.state in {RunState.SEARCHING, RunState.EXTRACTING}
            or entry.idempotency_key.startswith("reserve:synthesis:")
            and run.state == RunState.SYNTHESIZING
        )
        if affected:
            settled, status = entry.reserved, "uncertain"
        else:
            settled, status = Decimal(0), "released"
        updated = entry.model_copy(update={"settled": settled, "status": status})
        new_ledger.append(updated)
        totals[entry.dimension] += settled
    usage = run.usage.model_copy(
        update={
            "iterations": int(totals["iterations"]),
            "queries": int(totals["queries"]),
            "sources": int(totals["sources"]),
            "tokens": int(totals["tokens"]),
            "provider_cost_usd": totals["provider_cost_usd"],
            "elapsed_seconds": totals["elapsed_seconds"],
            "allowed_domains": int(totals["allowed_domains"]),
        }
    )
    return new_ledger, usage


def settle(
    ledger: tuple[BudgetLedgerEntry, ...] | list[BudgetLedgerEntry],
    idempotency_key: str,
    settled: Decimal,
) -> list[BudgetLedgerEntry]:
    result = []
    matched = False
    for entry in ledger:
        if entry.idempotency_key != idempotency_key:
            result.append(entry)
            continue
        if entry.status != "reserved" or matched:
            raise ResearchError("research_conflict", 409)
        matched = True
        status = "settled" if settled else "released"
        result.append(entry.model_copy(update={"settled": settled, "status": status}))
    if not matched:
        raise ResearchError("research_conflict", 409)
    return result
