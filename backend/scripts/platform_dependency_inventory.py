"""Read-only AST inventory of core -> example imports; never imports application code.

This is a bounded static guard, not a dynamic import or installation audit. See
docs/platform-independence/pi-0-dependency-inventory.md for policy and blind spots.
"""

from __future__ import annotations

import argparse
import ast
import json
from importlib.util import resolve_name
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_PREFIXES = (
    "personal_ai_reference_apps",
    "personal_ai.domains.providers",
    "personal_ai.domains.service",
    "personal_ai.persistence.postgres.capabilities",
    "personal_ai.api.booking_extractions",
    "personal_ai.api.itinerary_proposals",
    "personal_ai.booking_extractions",
    "personal_ai.context.finance",
    "personal_ai.context.health",
    "personal_ai.context.health_federation",
    "personal_ai.context.shopping",
    "personal_ai.context.travel",
    "personal_ai.domains.shopping",
    "personal_ai.domains.travel",
    "personal_ai.itinerary_proposals",
    "personal_ai.mutations.shopping",
)
EXAMPLE_FACADE_PREFIXES = (
    "personal_ai.api.domains",
    "personal_ai.domains.fixtures",
    "personal_ai.domains.registry",
)
WAIVER_FIELDS = {"from", "to", "rationale", "phase", "review_status"}


def under(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def is_example(module: str) -> bool:
    return any(under(module, prefix) for prefix in EXAMPLE_PREFIXES)


def is_example_facade(module: str) -> bool:
    return any(under(module, prefix) for prefix in EXAMPLE_FACADE_PREFIXES)


def module_name(path: Path, source_root: Path) -> str:
    parts = path.relative_to(source_root).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def inventory(source_root: Path) -> dict:
    """Include nested/TYPE_CHECKING imports and resolve relative/package imports.

    Only internal imports into explicit example prefixes are in guard scope.
    Evaluation code is diagnostic, so it may consume examples. All other
    non-example production modules are conservatively treated as core importers.
    """
    files = sorted((source_root / "personal_ai").rglob("*.py"))
    if not files:
        raise ValueError("no personal_ai Python sources found")
    modules = {module_name(path, source_root): path for path in files}
    edges = {}
    facade_edges = {}
    for path in files:
        importer = module_name(path, source_root)
        if is_example(importer) or under(importer, "personal_ai.evaluation"):
            continue
        package = importer if path.name == "__init__.py" else importer.rpartition(".")[0]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    base = resolve_name("." * node.level + base, package)
                targets = [base]
                # `from package import submodule` also creates a module edge.
                targets.extend(
                    f"{base}.{alias.name}"
                    for alias in node.names
                    if f"{base}.{alias.name}" in modules
                    or f"{base}.{alias.name}" in (*EXAMPLE_PREFIXES, *EXAMPLE_FACADE_PREFIXES)
                )
            for target in targets:
                if is_example_facade(target):
                    key = (importer, target)
                    facade_edges.setdefault(key, set()).add(node.lineno)
                if is_example(target):
                    key = (importer, target)
                    edges.setdefault(key, set()).add(node.lineno)
    return {
        "schema_version": 1,
        "scope": "AST core-to-example imports, including nested and type-only imports",
        "example_prefixes": list(EXAMPLE_PREFIXES),
        "example_facade_prefixes": list(EXAMPLE_FACADE_PREFIXES),
        "excluded_importer_prefixes": ["personal_ai.evaluation"],
        "edges": [
            {
                "from": importer,
                "to": target,
                "kind": "static_import",
                "evidence": {
                    "path": modules[importer].relative_to(source_root).as_posix(),
                    "lines": sorted(lines),
                },
            }
            for (importer, target), lines in sorted(edges.items())
        ],
        "facade_edges": [
            {
                "from": importer,
                "to": target,
                "kind": "static_facade_import",
                "evidence": {
                    "path": modules[importer].relative_to(source_root).as_posix(),
                    "lines": sorted(lines),
                },
            }
            for (importer, target), lines in sorted(facade_edges.items())
        ],
    }


def check(current: dict, baseline: dict) -> list[str]:
    """Reject new edges, stale waivers and incomplete/unreviewed exact waivers."""
    if (
        type(baseline) is not dict
        or set(baseline) != {"review_date", "review_scope", "schema_version", "source_revision", "waivers", "facade_waivers"}
        or type(baseline.get("schema_version")) is not int
        or baseline["schema_version"] != 1
        or not isinstance(baseline.get("waivers"), list)
        or not isinstance(baseline.get("facade_waivers"), list)
        or not all(type(baseline.get(key)) is str and baseline[key].strip() for key in ("review_date", "review_scope", "source_revision"))
    ):
        raise ValueError("invalid waiver schema")

    def exact_waivers(records, predicate):
        allowed = set()
        for waiver in records:
            if type(waiver) is not dict or set(waiver) != WAIVER_FIELDS:
                raise ValueError("invalid waiver record fields")
            importer, target = waiver["from"], waiver["to"]
            rationale = waiver["rationale"]
            if (
                type(importer) is not str
                or type(target) is not str
                or not importer.startswith("personal_ai.")
                or "*" in importer
                or "*" in target
                or not predicate(target)
                or (predicate is is_example and is_example(importer))
                or under(importer, "personal_ai.evaluation")
                or type(rationale) is not str
                or not rationale.strip()
                or rationale != rationale.strip()
                or type(waiver["phase"]) is not str
                or waiver["phase"] != "PI-1"
                or type(waiver["review_status"]) is not str
                or waiver["review_status"] != "implementation-reviewed; independent-pending"
            ):
                raise ValueError("invalid or unreviewed exact waiver")
            key = (importer, target)
            if key in allowed:
                raise ValueError("duplicate waiver")
            allowed.add(key)
        return allowed

    allowed = exact_waivers(baseline["waivers"], is_example)
    allowed_facades = exact_waivers(baseline["facade_waivers"], is_example_facade)
    actual = {(edge["from"], edge["to"]) for edge in current["edges"]}
    actual_facades = {(edge["from"], edge["to"]) for edge in current.get("facade_edges", [])}
    return (
        [f"unexpected: {a} -> {b}" for a, b in sorted(actual - allowed)]
        + [f"stale waiver: {a} -> {b}" for a, b in sorted(allowed - actual)]
        + [f"unexpected facade: {a} -> {b}" for a, b in sorted(actual_facades - allowed_facades)]
        + [f"stale facade waiver: {a} -> {b}" for a, b in sorted(allowed_facades - actual_facades)]
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=ROOT / "backend/src")
    parser.add_argument("--check", action="store_true", help="check exact reviewed migration debt")
    parser.add_argument(
        "--baseline",
        type=Path,
        default=(ROOT / "docs/platform-independence/pi-0-import-waivers.json"),
    )
    args = parser.parse_args(argv)
    try:
        current = inventory(args.source_root)
        if args.check:
            issues = check(current, json.loads(args.baseline.read_text(encoding="utf-8")))
            print(
                json.dumps(
                    {"schema_version": 1, "edge_count": len(current["edges"]), "facade_edge_count": len(current["facade_edges"]), "issues": issues},
                    indent=2,
                    sort_keys=True,
                )
            )
            return int(bool(issues))
        print(json.dumps(current, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, SyntaxError, KeyError, TypeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
