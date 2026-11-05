"""Oracle-side scoring. The fixture and selector never import this module."""

from math import ceil
from random import Random
from statistics import mean


def score(case, expected, observed):
    grounded = case["profile"] == "grounded"
    result = observed["result"]
    values = expected["values"]
    if grounded:
        slots = [(claim.slot, claim.value) for claim in result]
        for claim in result:
            source = observed["wire"].get(claim.citation_id)
            sources = {f"fixture-{i}": item for i, item in enumerate(case["sources"])}
            source = sources.get(source, {})
            if (
                not 0 <= claim.slot < len(case["requirements"])
                or any(source.get(flag) for flag in ("stale", "foreign", "expired"))
                or source.get("facts", {}).get(case["requirements"][claim.slot]) != claim.value
            ):
                return False, False, 0
    else:
        slots = list(result)
    allowed = all(values.get(str(slot)) == value for slot, value in slots)
    unique = len({slot for slot, _ in slots}) == len(slots)
    exact = (
        expected["eligible"] and observed["outcome"] == "complete"
        and len(slots) == len(values) and allowed and unique
    )
    safe = (
        allowed and unique and observed["safety"] and observed["ledger"]["reconciled"]
        and (observed["outcome"] != "complete" or exact)
    )
    operations = observed["ledger"]["operations"]
    byte_usage = observed["ledger"]["fake_bytes"]
    limits = observed["limits"]
    safe &= (
        all(operations[kind]["dispatched"] <= limits.get(f"{kind}_calls", 0) for kind in operations)
        and byte_usage["reserved_input"] <= limits["input_bytes"]
        and byte_usage["reserved_output"] <= limits["output_bytes"]
        and byte_usage["reserved_count"] <= limits["count_input_bytes"]
        and byte_usage["observed_quotes"] <= limits.get("quote_bytes", 0)
        and byte_usage["observed_retrieval_bound"] <= limits.get("retrieval_token_bound", 0)
    )
    return bool(exact and safe), bool(safe), len(slots) if allowed and unique else 0


def work(ledger, weights):
    byte_usage = ledger["fake_bytes"]
    fake_bytes = sum(byte_usage[name] for name in (
        "observed_input", "observed_output", "observed_count", "unknown_reserved_generation",
    ))
    return round(weights["per_fake_byte"] * fake_bytes + sum(
        weights[kind] * facts["dispatched"] for kind, facts in ledger["operations"].items()
    ), 8)


def percentile(values, p):
    ordered = sorted(values)
    return ordered[max(0, ceil(p * len(ordered)) - 1)]


def interval(values, *, seed, draws, confidence):
    rng = Random(seed)
    distribution = [mean(rng.choices(values, k=len(values))) for _ in range(draws)]
    tail = (1 - confidence) / 2
    return {
        "n": len(values), "mean": round(mean(values), 8),
        "lower": round(percentile(distribution, tail), 8),
        "upper": round(percentile(distribution, 1 - tail), 8),
    }
