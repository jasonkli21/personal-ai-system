"""Author-locked protocol, complete grids and source-pinned reproducibility."""

import importlib.metadata
import platform
import random
import subprocess
from collections import Counter
from hashlib import sha256
from pathlib import Path

from personal_ai.memory.research.experiments.artifacts import (
    parse_json,
    validate_grid,
    verify_sources,
)
from personal_ai.memory.research.experiments.contracts import (
    ARMS,
    Contrast,
    DatasetManifest,
    EnvironmentManifest,
    MemoryPolicyManifest,
    ModelManifest,
    Protocol,
    RunManifest,
    SourceHash,
    digest,
)

from .dataset import SCORER_SHA256, SOURCE_SHA256, load_sources, source_bytes
from .driver import run_trajectory
from .support import support_digest, support_matrix

ROOT = Path(__file__).resolve().parents[5]
LEGACY_SOURCE_LOCK_SHA256 = "4a19369b4eb997b3dbda7a37f1febd9a2e8e5165a1cc53c6a2584b1ada92d95f"
OLDEST_SOURCE_LOCK_SHA256 = "9f3f3777af3716b1fb40a1b5af365233250f6197fa81e965b5b77403212812cc"
HISTORICAL_V3_SOURCE_LOCK_SHA256 = "10b46a3a08ef8123e882673b710e44e8d65580ab4bb1739ba8e4de9f3a99cfb0"
PREVIOUS_SOURCE_LOCK_SHA256 = "5a9169b9a71209f20533f9ddcb25d702c85eaf6da9045ef06fa84cc222de989d"


def protocol():
    return Protocol(
        primary=Contrast(baseline="no_memory", candidate="lexical"),
        secondary=(
            Contrast(baseline="lexical", candidate="topic_hierarchical"),
            Contrast(baseline="lexical", candidate="adaptive"),
            Contrast(baseline="lexical", candidate="full_history"),
            Contrast(baseline="no_memory", candidate="verified_knowledge"),
            Contrast(baseline="verified_knowledge", candidate="tool_lookup"),
        ),
        repetition_seeds=(719, 719),
    )


def dependency_paths():
    source = ROOT / "backend/src/personal_ai"
    paths = set()
    for directory in ("memory", "context", "auth", "contracts", "entities"):
        paths.update(source.joinpath(directory).rglob("*.py"))
    paths.update(Path(__file__).parent.glob("*.py"))
    paths.discard(Path(__file__).parent / "seal.py")
    for relative in (
        "llm/client.py",
        "settings.py",
        "storage/errors.py",
        "evaluation/knowledge_runtime.py",
        "evaluation/memory_knowledge.py",
        "evaluation/memory_navigation.py",
    ):
        paths.add(source / relative)
    paths.update((ROOT / "backend/pyproject.toml", ROOT / "backend/uv.lock"))
    return tuple(sorted(paths))


def current_source_hashes():
    return tuple(
        SourceHash(path=str(p.relative_to(ROOT)), sha256=sha256(p.read_bytes()).hexdigest())
        for p in dependency_paths()
    )


def source_lock():
    from .seal import LOCK_SHA256

    path = Path(__file__).parent / "source-lock-v5.json"
    payload = path.read_bytes()
    if len(payload) > 65536 or sha256(payload).hexdigest() != LOCK_SHA256:
        raise ValueError("study_lock_identity_changed")
    data = parse_json(payload, limit=65536)
    if (
        set(data) != {"version", "sources", "protocol_sha256", "supersedes_sha256"}
        or data["version"] != "memory-longitudinal-source-lock-v3"
    ):
        raise ValueError("study_lock_schema")
    previous = path.with_name("source-lock-v4.json")
    if (
        data["supersedes_sha256"] != PREVIOUS_SOURCE_LOCK_SHA256
        or sha256(previous.read_bytes()).hexdigest() != PREVIOUS_SOURCE_LOCK_SHA256
        or sha256(path.with_name("source-lock-v3.json").read_bytes()).hexdigest()
        != HISTORICAL_V3_SOURCE_LOCK_SHA256
        or sha256(path.with_name("source-lock-v2.json").read_bytes()).hexdigest()
        != LEGACY_SOURCE_LOCK_SHA256
        or sha256(path.with_name("source-lock-v1.json").read_bytes()).hexdigest()
        != OLDEST_SOURCE_LOCK_SHA256
    ):
        raise ValueError("historical_source_lock_changed")
    expected = tuple(SourceHash.model_validate(x) for x in data["sources"])
    if expected != current_source_hashes() or data["protocol_sha256"] != digest(protocol()):
        raise ValueError("study_source_changed_requires_new_generation")
    return expected


def _git_output(*args, cwd=ROOT):
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def _git_blob_sha(revision, path, root=ROOT):
    try:
        payload = subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=root)
    except subprocess.CalledProcessError:
        return None
    return sha256(payload).hexdigest()


def verify_git_provenance(run, root=ROOT):
    """Bind the historical revision and dirty bit to the pinned research inputs."""
    root = Path(root).resolve()
    revision = _git_output("rev-parse", "--verify", f"{run.revision}^{{commit}}", cwd=root)
    tree = _git_output("rev-parse", f"{revision}^{{tree}}", cwd=root)
    source_snapshot = digest([source.model_dump(mode="json") for source in run.source_hashes])
    dirty = any(
        _git_blob_sha(revision, source.path, root) != source.sha256 for source in run.source_hashes
    )
    provenance = digest([revision, tree, dirty, source_snapshot])
    if (
        revision != run.revision
        or tree != run.revision_tree
        or dirty != run.dirty
        or source_snapshot != run.source_snapshot_sha256
        or provenance != run.provenance_sha256
    ):
        raise ValueError("run_git_provenance_mismatch")
    return True


def make_run():
    source_hashes = source_lock()
    # The anchor is outside its own hash recursion, but is included in each run.
    anchor = Path(__file__).parent / "seal.py"
    lock = Path(__file__).parent / "source-lock-v5.json"
    predecessor = Path(__file__).parent / "source-lock-v4.json"
    historical_v3 = Path(__file__).parent / "source-lock-v3.json"
    source_hashes += (
        SourceHash(
            path=str(anchor.relative_to(ROOT)), sha256=sha256(anchor.read_bytes()).hexdigest()
        ),
        SourceHash(path=str(lock.relative_to(ROOT)), sha256=sha256(lock.read_bytes()).hexdigest()),
        SourceHash(path=str(predecessor.relative_to(ROOT)), sha256=PREVIOUS_SOURCE_LOCK_SHA256),
        SourceHash(
            path=str(historical_v3.relative_to(ROOT)), sha256=HISTORICAL_V3_SOURCE_LOCK_SHA256
        ),
        SourceHash(
            path=str(lock.with_name("source-lock-v2.json").relative_to(ROOT)),
            sha256=LEGACY_SOURCE_LOCK_SHA256,
        ),
        SourceHash(
            path=str(lock.with_name("source-lock-v1.json").relative_to(ROOT)),
            sha256=OLDEST_SOURCE_LOCK_SHA256,
        ),
    )
    revision = _git_output("rev-parse", "HEAD")
    tree = _git_output("rev-parse", f"{revision}^{{tree}}")
    source_snapshot = digest([source.model_dump(mode="json") for source in source_hashes])
    dirty = any(_git_blob_sha(revision, source.path) != source.sha256 for source in source_hashes)
    provenance = digest([revision, tree, dirty, source_snapshot])
    corpus = load_sources()
    protocol_manifest = protocol()
    policies = tuple(
        MemoryPolicyManifest(
            policy_id="memory-study-" + arm,
            arm=arm,
            selection=arm,
            parameter_sha256=digest({"arm": arm, "budget": protocol_manifest.budgets.model_dump()}),
        )
        for arm in ARMS
    )
    eligibility = support_matrix(corpus.tasks, policies, protocol_manifest.budgets)
    dataset = DatasetManifest(
        dataset_id="memory-longitudinal-study-v3",
        fixture_sha256=digest([SOURCE_SHA256, SCORER_SHA256]),
        source_sha256=sha256(source_bytes()).hexdigest(),
        scorer_sha256=SCORER_SHA256,
        source_snapshot="public-synthetic-v1",
        scoring_seal=SCORER_SHA256,
        splits=("development", "validation_author_visible", "challenge_author_visible"),
        families=("transfer", "revision", "correction", "rights", "poison", "resources"),
        cases=len(corpus.tasks),
    )
    return RunManifest(
        revision=revision,
        dirty=dirty,
        revision_tree=tree,
        source_snapshot_sha256=source_snapshot,
        provenance_sha256=provenance,
        source_hashes=source_hashes,
        dataset=dataset,
        model=ModelManifest(configuration_sha256=digest({"scripted": True}), seed=719),
        support_matrix_sha256=support_digest(eligibility),
        policies=policies,
        protocol=protocol_manifest,
        environment=EnvironmentManifest(
            python=platform.python_version(),
            platform=platform.system() + "-" + platform.release(),
            machine=platform.machine(),
            pydantic=importlib.metadata.version("pydantic"),
        ),
    )


def replay(run):
    run = RunManifest.model_validate(run.model_dump())
    verify_sources(run, ROOT)
    verify_git_provenance(run, ROOT)
    # Imported manifests cannot select a different model space, flags or cohort.
    expected = make_run()
    for name in ("dataset", "model", "policies", "protocol", "environment", "source_hashes"):
        if getattr(run, name) != getattr(expected, name):
            raise ValueError("replay_environment_or_policy_mismatch")
    corpus = load_sources()
    rows = []
    for repetition in range(2):
        trials = [(task.id, p.arm) for task in corpus.tasks for p in run.policies]
        random.Random(run.protocol.repetition_seeds[repetition] + repetition).shuffle(trials)
        for task_id, arm in trials:
            rows.extend(run_trajectory(task_id, arm, digest(run), run.protocol, repetition))
    rows.sort(key=lambda r: (r.task_id, r.arm, r.repetition, r.time_step))
    validate_grid(run, rows, corpus.tasks)
    verify_sources(run, ROOT)
    return tuple(rows)


def render_report(run, report, metrics, decision):
    lines = [
        "# Memory longitudinal research",
        "",
        "E1 author-visible scripted action proxy.",
        "",
        "Protocol v2 preregisters an oracle-free no-memory discover→apply baseline under the same two-call cap; apply rechecks current authority for both baseline and memory policies.",
        "",
        "The historical v1 +20 pp lexical contrast is strategy-confounded because its no-memory policy spent a tool call checking an absent hint. It is retained as historical evidence and is not a causal memory-benefit estimate.",
        "",
        f"Decision: **{decision.status}**. Effective policy: unchanged; live promotion forbidden.",
        f"Run SHA-256: `{digest(run)}`.",
        f"Git revision: `{run.revision}`; tree: `{run.revision_tree}`; research inputs dirty: `{run.dirty}`.",
        f"Source snapshot: `{run.source_snapshot_sha256}`; provenance: `{run.provenance_sha256}`.",
        f"Semantic replay: `{report.semantic_replay_sha256}`; match: {report.replay_match}.",
        f"Attempted rows: {report.attempted_rows}; statuses: {dict(report.status_counts)}.",
        f"Support matrix SHA-256: `{report.support_matrix_sha256}`; unexpected unsupported rows: {report.supported_runtime_unsupported_rows}; boundary mismatches: {report.boundary_mismatch_rows}.",
        "",
        "| Contrast | Requested | Structurally eligible | Started | Terminal complete | Scored | Wins / losses / ties | Delta pp | 95% interval pp |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for c in report.comparisons:
        lines.append(
            f"| {c.candidate} vs {c.baseline} | {c.attempted_scenarios} | "
            f"{c.structurally_eligible_scenarios} | {c.started_pairs} | "
            f"{c.terminal_completed_pairs} | {c.scored_pairs} | "
            f"{c.wins}/{c.losses}/{c.ties} | {c.delta_pp} | {c.interval_pp} |"
        )
    lines += [
        "",
        (
            "Scenario-clustered fixed-seed percentile bootstrap; repetitions and setup steps "
            "are not independent samples. Secondary contrasts are descriptive. No significance claim."
        ),
        "",
        "| Arm | Attempted rows | Complete terminal rows | Task successes | Unsupported rows |",
        "| --- | --- | --- | --- | --- |",
    ]
    for arm, m in metrics.items():
        lines.append(
            f"| {arm} | {m['attempted_rows']} | {m['complete_terminal_denominator']} | "
            f"{m['terminal_successes']} | {m['statuses'].get('unsupported', 0)} |"
        )
    lines += [
        "",
        (
            "All splits, including validation and challenge slots, were inspected by the author. "
            "Policy runtime receives no scoring file. Unknown model tokens, billed costs and native "
            "resources remain null. Local latency includes failed/unsupported attempts and setup; "
            "fixture tokens are word estimates. No independent review, native durability, deployed "
            "recovery, private source rights, physical send or real model utility is established. Git provenance and content hashes establish local integrity relative to retained objects, not an external signature."
        ),
        "",
        "Phase exit: **BLOCKED**. Production: **NO_GO**.",
        "",
        "Decision reasons: " + ", ".join(decision.reasons) + ".",
        "",
    ]
    return "\n".join(lines)


def row_summary(rows):
    return dict(Counter(row.status for row in rows))
