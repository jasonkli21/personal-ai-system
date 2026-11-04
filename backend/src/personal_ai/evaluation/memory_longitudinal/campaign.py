"""Deterministic attacks on actual source, index, builder and simulator seams."""

from hashlib import sha256
from time import monotonic

from personal_ai.evaluation.knowledge_runtime import HermeticKnowledgeAuthority
from personal_ai.evaluation.memory_navigation import policy, query_for
from personal_ai.memory.knowledge_sources import KnowledgeSourceError
from personal_ai.memory.research.contracts import ResearchFailure
from personal_ai.memory.research.experiments.contracts import canonical
from personal_ai.memory.research.index import terms, validate_index
from personal_ai.settings import Settings

from .dataset import SOURCE_SHA256, load_sources, parse_sources, source_bytes
from .source import LongitudinalAuthority, LongitudinalNavigation


def campaign():
    tasks = load_sources().tasks
    chosen = next(t for t in tasks if t.profile == "navigation_fixture" and t.current_action)
    checks = []

    def check(name, operation):
        try:
            passed = operation()
        except Exception:  # noqa: BLE001 - a broken control is a failed gate, never a pass
            passed = False
        checks.append((name, "pass" if passed is True else "fail"))

    def setup(task=chosen, offset=0):
        source = LongitudinalAuthority(task.id)
        source.offset = offset
        query = query_for(
            {"query": task.query, "scope": task.scope.model_dump(), "project": task.project},
            now=source.now(),
        )
        engine = LongitudinalNavigation(source, enabled=True)
        return source, query, engine

    def denied(operation):
        try:
            operation()
        except (ResearchFailure, ValueError, KnowledgeSourceError):
            return True
        return False

    def scope():
        source, query, _ = setup()
        return all(
            denied(
                lambda field=field: source.check(
                    query.model_copy(
                        update={
                            "canonical": query.canonical.model_copy(
                                update={
                                    "scope": query.canonical.scope.model_copy(
                                        update={field: "other-synthetic"}
                                    )
                                }
                            )
                        }
                    )
                )
            )
            for field in ("owner_id", "application_id", "workspace_id", "acting_user_id")
        )

    check("scope", scope)

    def revocation():
        outcomes = []
        for boundary in ("ranked", "packed", "consume", "pre_send"):
            source, query, engine = setup()

            def hook(stage, boundary=boundary, source=source):
                if stage == boundary:
                    source.revoke_grant(chosen.scope.model_dump(), chosen.project)

            result = engine.run(query, policy(), hook=hook)
            outcomes.append(
                result.status == "denied"
                and not (result.answer or result.citations or result.packed_ids)
            )
        source, query, engine = setup()
        index = engine.index(query)
        record = source.universe(query)[0]
        dependency = source.dependency(record)
        source.revoke_grant(chosen.scope.model_dump(), chosen.project)
        source.regrant(chosen.scope.model_dump(), chosen.project)
        outcomes.append(not source.is_current(dependency))
        outcomes.append(denied(lambda: validate_index(source, index, query)))
        new_source, new_query, _ = setup()
        outcomes.append(denied(lambda: validate_index(new_source, index, new_query)))
        return all(outcomes)

    check("source_revocation", revocation)

    def forget():
        source, query, engine = setup()
        index = engine.index(query)
        record = source.universe(query)[0]
        snapshot = dict(source._records)
        source.transition("forget", record.id)
        source._records = snapshot
        return record not in source.universe(query) and denied(
            lambda: engine.pack(query, index, (record.id,), policy())
        )

    check("forget_restore", forget)

    def correction():
        task = next(
            t
            for t in tasks
            if any(r.supersedes for r in t.records) and t.current_action == "silver"
        )
        source, query, _ = setup(task)
        old, new = task.records
        before = {r.id for r in source.universe(query)}
        source.offset = 2
        query = query.model_copy(
            update={"canonical": query.canonical.model_copy(update={"as_of": source.now()})}
        )
        after = {r.id for r in source.universe(query)}
        source.transition("forget", new.id)
        withdrawn = {r.id for r in source.universe(query)}
        return (
            old.id in before
            and new.id not in before
            and old.id not in after
            and (new.id in after and old.id not in withdrawn and new.id not in withdrawn)
        )

    check("correction", correction)

    def poison():
        attacked = [
            t
            for t in tasks
            if any("Ignore system" in r.content or "unobserved" in r.content for r in t.records)
        ]
        return len(attacked) >= 5 and all(not setup(t)[0].universe(setup(t)[1]) for t in attacked)

    check("poisoning", poison)

    def replay():
        _, query, _ = setup()
        host = HermeticKnowledgeAuthority(query.canonical.scope)
        kwargs = {"expected_revision": "rev-one"}
        one = host.execute(
            query.canonical.scope, chosen.project, "original-intent", "amber", **kwargs
        )
        two = host.execute(
            query.canonical.scope, chosen.project, "original-intent", "amber", **kwargs
        )
        return (
            one == two
            and host.effect_count == 1
            and denied(
                lambda: host.execute(
                    query.canonical.scope, chosen.project, "original-intent", "cobalt", **kwargs
                )
            )
        )

    check("intent_replay", replay)

    def tamper():
        payload = source_bytes()
        changed = payload.replace(b'"memory-longitudinal-sources-v1"', b'"unknown-schema"')
        return denied(lambda: parse_sources(payload + b" ", SOURCE_SHA256)) and denied(
            lambda: parse_sources(changed, sha256(changed).hexdigest())
        )

    check("tamper", tamper)

    def cancellation():
        _, query, engine = setup()
        result = engine.run(query, policy(), cancelled=lambda: True)
        expired = query.model_copy(
            update={"canonical": query.canonical.model_copy(update={"deadline": monotonic() - 1})}
        )
        timeout = engine.run(expired, policy())
        return (
            result.status == "cancelled"
            and timeout.status == "timed_out"
            and not (result.answer or timeout.answer)
        )

    check("cancellation", cancellation)

    def bounds():
        _, query, engine = setup()
        too_large = engine.run(query, policy(global_tokens=5000))
        return (
            denied(lambda: terms(" ".join(f"v{i}" for i in range(200))))
            and denied(lambda: parse_sources(b" " * 262145, "0" * 64))
            and too_large.status == "incomplete"
        )

    check("resource_bounds", bounds)

    def isolation():
        source = load_sources()
        task = source.tasks[0].model_dump(mode="json")
        task["expected_action"] = "canary-gold-leak"
        from .dataset import SourceTask

        return denied(
            lambda: SourceTask.model_validate(task)
        ) and b"expected_action" not in canonical(source.tasks[0].manifest())

    check("scorer_isolation", isolation)

    def unchanged():
        before = Settings(_env_file=None, ai_provider="gemini", ai_model="synthetic")
        _, query, engine = setup()
        engine.run(query, policy())
        after = Settings(_env_file=None, ai_provider="gemini", ai_model="synthetic")
        names = (
            "memory_experiment_variant",
            "memory_knowledge_selection_enabled",
            "memory_knowledge_admission_enabled",
            "memory_agent_tools_enabled",
        )
        return all(getattr(before, n, None) == getattr(after, n, None) for n in names)

    check("configuration_unchanged", unchanged)
    return tuple(checks)
