"""Validate the frozen corpus and protocol against a version-specific anchor."""

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

from .reasoning_contracts import Corpus

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures/reasoning"
MANIFEST_SHA256 = "2749b02f37b32571e913bbd2240942cfbe3e1032f424823e3f950219f6a888a9"


def bounded_read(path: Path, limit: int) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("source_too_large")
    return data


def load() -> tuple[Corpus, dict]:
    raw = bounded_read(FIXTURES / "manifest-v1.json", 16_384)
    if sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("manifest_identity_mismatch")
    manifest = json.loads(raw)
    for relative, expected in manifest["files"].items():
        if sha256(bounded_read(HERE / relative, 131_072)).hexdigest() != expected:
            raise ValueError("source_identity_mismatch")
    corpus = Corpus.model_validate_json(bounded_read(FIXTURES / "cases-v1.json", 131_072))
    cases = corpus.cases
    if (
        [(case.id, case.task.family, case.split) for case in cases]
        != [tuple(row) for row in manifest["cohort"]]
        or len({case.id for case in cases}) != 32
        or set(Counter(case.task.family for case in cases).values()) != {4}
        or set(Counter(case.task.family for case in cases if case.split == "holdout").values())
        != {1}
        or len({case.task.family for case in cases if case.split == "holdout"}) != 8
    ):
        raise ValueError("invalid_cohort")
    return corpus, manifest
