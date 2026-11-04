"""Deterministic bounded proposals, never verification of a future task outcome."""

from datetime import timedelta

from personal_ai.memory.consolidation.contracts import DerivedProposal, edge


def proposal_current(proposal, source):
    resolved = tuple(source.resolve(proposal.scope, e) for e in proposal.edges)
    if not all(resolved):
        return False
    if any(source.clock() >= s.observed_at + timedelta(hours=24) for s in resolved):
        return False
    # Source membership alone does not prove the proposed assertion. Verify its
    # exact typed fact, authority and relation on every read and cached reuse.
    if len({(s.source_id, s.revision, s.epoch) for s in resolved}) != len(resolved):
        return False
    if proposal.kind == "conflict":
        if (
            len(resolved) != 2
            or proposal.authority != "unresolved"
            or any(s.evidence == "observed_completion" for s in resolved)
            or {s.fact.outcome for s in resolved} != {"passed", "failed"}
            or any(
                (s.fact.command, s.fact.revision) != (proposal.fact.command, proposal.fact.revision)
                for s in resolved
            )
            or proposal.fact not in tuple(s.fact for s in resolved)
        ):
            return False
    elif (
        len(resolved) != 1
        or resolved[0].fact != proposal.fact
        or resolved[0].evidence == "observed_completion"
        or proposal.kind != ("procedure" if proposal.fact.outcome == "passed" else "lesson")
        or proposal.authority
        != ("user_asserted" if resolved[0].evidence == "user_correction" else "fixture_checked")
    ):
        return False
    # An unprocessed published correction already wins over a cached suggestion.
    return not (
        any(s.evidence != "user_correction" for s in resolved)
        and source.correction_barrier(proposal.scope, proposal.fact)
    )


def extract(record, existing, source, *, generation=None):
    """Return one candidate/reason per exact source, using closed fixture facts."""
    if not source.current(record, record.scope):
        return None, "source_ineligible"
    if source.clock() >= record.observed_at + timedelta(hours=24):
        return None, "source_ineligible"
    if record.evidence == "observed_completion":
        return None, "unsupported_observation"
    if record.evidence != "user_correction" and source.correction_barrier(
        record.scope, record.fact
    ):
        return None, "user_correction_wins"
    authority = "user_asserted" if record.evidence == "user_correction" else "fixture_checked"
    options = {"generation": generation} if generation is not None else {}
    candidate = DerivedProposal(
        scope=record.scope,
        kind="procedure" if record.fact.outcome == "passed" else "lesson",
        fact=record.fact,
        authority=authority,
        edges=(edge(record),),
        **options,
    )
    for prior in sorted(existing, key=lambda p: p.key):
        if candidate.assertion_key == prior.assertion_key:
            return None, "duplicate"
        if (prior.fact.command, prior.fact.revision) != (record.fact.command, record.fact.revision):
            continue
        if prior.kind == "conflict":
            return None, "conflict"
        if prior.fact.outcome != record.fact.outcome:
            if prior.authority == "user_asserted" and authority != "user_asserted":
                return None, "user_correction_wins"
            return DerivedProposal(
                scope=record.scope,
                kind="conflict",
                fact=record.fact,
                authority="unresolved",
                edges=(*prior.edges, edge(record)),
                **options,
            ), "conflict"
    return candidate, "superseded" if record.supersedes else "proposed"
