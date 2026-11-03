"""Closed PI-6 inputs and content-free observations. No executable fixture fields."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DIRECTORY = Path(__file__).parent / 'fixtures/pi6'
FAMILIES = ('one_app', 'profile', 'memory', 'branch', 'research', 'retrieval', 'provider', 'replay')


class Closed(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)


class Task(Closed):
    family: Literal['one_app', 'profile', 'memory', 'branch', 'research', 'retrieval', 'provider', 'replay']
    variant: Literal['current', 'irrelevant', 'revoke', 'edit', 'forget', 'recall', 'collision',
                     'expiry', 'conflict', 'outage', 'alternate', 'missing', 'supersede', 'long']
    subject: str = Field(pattern=r'^[a-z]{4,16}$')
    value: str = Field(pattern=r'^[a-z]{3,16}$')
    distractor: str = Field(pattern=r'^[a-z]{3,16}$')


class Oracle(Closed):
    baseline: Literal['correct', 'unknown', 'denied', 'completed', 'forgotten', 'conflict', 'failed']
    candidate: Literal['correct', 'unknown', 'denied', 'completed', 'forgotten', 'conflict', 'failed']
    forbidden_actions: tuple[Literal['external_send', 'write_tool', 'duplicate_effect', 'stale_disclosure'], ...]
    citation_required: bool


class Case(Closed):
    case_id: str = Field(pattern=r'^P6-[A-H][1-4]$')
    lineage: str = Field(pattern=r'^[a-z]{4,30}$')
    source_configuration: str = Field(pattern=r'^[a-z]{4,30}$')
    split: Literal['calibration', 'heldout']
    operation: Literal['one_turn', 'transition']
    rights_event: Literal['none', 'revoke', 'edit', 'expire']
    provenance: Literal['authored_synthetic_v1']
    task: Task
    oracle: Oracle


class Corpus(Closed):
    suite: Literal['pi6-offline-v1']
    rubric: Literal['pi6-rubric-v1']
    seed: Literal[61]
    input_cap: Literal[32768]
    output_cap: Literal[256]
    deadline_seconds: Literal[5]
    source_bytes: Literal[8192]
    cases: tuple[Case, ...] = Field(min_length=32, max_length=32)

    @model_validator(mode='after')
    def groups(self):
        if len({c.case_id for c in self.cases}) != 32:
            raise ValueError('duplicate_case')
        for attr in ('lineage', 'source_configuration'):
            groups = {}
            for c in self.cases:
                groups.setdefault(getattr(c, attr), set()).add(c.split)
            if any(len(s) != 1 for s in groups.values()):
                raise ValueError('group_split_leakage')
        for family in FAMILIES:
            cases = [c for c in self.cases if c.task.family == family]
            if len(cases) != 4 or sum(c.split == 'heldout' for c in cases) != 2:
                raise ValueError('family_split')
            if len({c.lineage for c in cases}) < 2 or {c.operation for c in cases} != {'one_turn', 'transition'}:
                raise ValueError('family_variants')
        return self


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def load_corpus() -> tuple[Corpus, dict]:
    # Paths are code-owned; neither CLI nor manifest selects imports/files/URLs.
    raw = (DIRECTORY / 'cases-v1.json').read_bytes()
    manifest = json.loads((DIRECTORY / 'manifest-v1.json').read_bytes())
    if len(raw) > 131072 or set(manifest) != {'suite', 'hashes', 'preregistration', 'frozen_before_measurement'}:
        raise ValueError('manifest_invalid')
    files = {
        'cases': raw,
        'scoring': Path(__file__).with_name('pi6_scoring.py').read_bytes(),
        'contracts': Path(__file__).read_bytes(),
    }
    if (manifest['suite'] != 'pi6-offline-v1' or manifest['frozen_before_measurement'] is not True
            or manifest['hashes'] != {k: sha(v) for k, v in files.items()}):
        raise ValueError('frozen_identity_mismatch')
    return Corpus.model_validate_json(raw), manifest


class Observation(Closed):
    outcome: Literal['correct', 'unknown', 'denied', 'completed', 'forgotten', 'conflict', 'failed']
    hard_valid: bool
    factual: bool | None = None
    citation: bool | None = None
    dispatched: int = Field(default=0, ge=0, le=8)
    expected_dispatches: int = Field(default=0, ge=0, le=8)
    duplicate_effect: bool = False
    source_dependencies: int | None = Field(default=None, ge=0)
    input_units: int | None = Field(default=None, ge=0)
    output_units: int | None = Field(default=None, ge=0)
    tool_units: int | None = Field(default=None, ge=0)
    unnecessary_context: bool | None = None
    token_confidence: Literal['authoritative_local_bytes', 'estimated', 'unknown'] = 'unknown'
    status: Literal['measured', 'blocked_capability', 'denied_policy', 'not_applicable', 'unmeasured'] = 'measured'
    error: Literal['none', 'offline_failure', 'budget_exceeded'] = 'none'
