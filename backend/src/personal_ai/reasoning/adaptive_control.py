"""Operator-owned promotion evidence and a single-machine policy pointer."""

import argparse
import fcntl
import json
import os
import secrets
import stat
from contextlib import contextmanager, suppress
from pathlib import Path
from time import time
from typing import Annotated, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import Field, model_validator

from personal_ai.contracts.delegated_tasks import canonical_bytes

from .adaptive import FINITE
from .orchestration import Digest, Limits, ReasoningRecord, _unique_fields, digest

MAX_AGE = 30 * 24 * 3600
MAX_GENERATION = 2**63 - 1
MIN_PAIRS = 64
POINTER = "reasoning-adaptive.json"
MAX_BYTES = 8192


class PromotionEvidence(ReasoningRecord):
    schema_version: Literal["adaptive-promotion-evidence-v1"] = "adaptive-promotion-evidence-v1"
    tier: Literal["E1"] = "E1"
    profile: Literal["finite_synthetic"] = "finite_synthetic"
    sensitivity: Literal["public_synthetic"] = "public_synthetic"
    capability: Literal["source-free-offline-fake.v1"] = "source-free-offline-fake.v1"
    scope_digest: Digest
    build_digest: Digest
    endpoint_digest: Digest
    policy_digest: Digest
    protocol_digest: Digest
    result_digest: Digest
    oracle_custody_digest: Digest
    family: Literal["independent", "correctable", "arithmetic"]
    effort: Literal["high", "max"]
    limits: Limits
    holdout: Literal["independent_blind"] = "independent_blind"
    matched_pairs: int = Field(ge=MIN_PAIRS, le=100_000)
    quality_lower_ppm: int = Field(gt=0, le=1_000_000)
    utility_lower_ppm: int = Field(gt=0, le=1_000_000)
    safety_vetoes: Literal[0] = 0
    unnecessary_calls: Literal[0] = 0
    unknown_fixture_effects: Literal[0] = 0
    subgroup_regressions: Literal[0] = 0
    fake_bytes_observed: int = Field(gt=0, le=10**10)
    dispatched_generations: int = Field(gt=0, le=10**6)
    observed_generations: int = Field(gt=0, le=10**6)
    observed_count_calls: int = Field(gt=0, le=10**7)
    observed_verifier_calls: int = Field(gt=0, le=10**6)
    reproduced: Literal[True] = True
    cost_class: Literal["synthetic_no_charge"] = "synthetic_no_charge"
    real_provider_tokens: None = None
    real_provider_charge: None = None
    issued_at: int = Field(gt=0)
    expires_at: int = Field(gt=0)

    @model_validator(mode="after")
    def complete(self):
        if (
            not 0 < self.expires_at - self.issued_at <= MAX_AGE
            or self.observed_generations != self.dispatched_generations
        ):
            raise ValueError("adaptive_evidence_incomplete")
        return self

    @property
    def identity(self):
        return digest(self.model_dump(mode="json"))


class SignedEvidence(ReasoningRecord):
    evidence: PromotionEvidence
    approval: Annotated[str, Field(pattern=r"^[0-9a-f]{128}$")]

    def verified(self, reviewer_key, now):
        evidence = self.evidence
        if reviewer_key is None or not evidence.issued_at <= now < evidence.expires_at:
            return False
        try:
            Ed25519PublicKey.from_public_bytes(reviewer_key).verify(
                bytes.fromhex(self.approval), canonical_bytes(evidence.model_dump(mode="json")),
            )
        except (ValueError, InvalidSignature):
            return False
        return True


class PolicyPointer(ReasoningRecord):
    schema_version: Literal["adaptive-local-pointer-v1"] = "adaptive-local-pointer-v1"
    generation: int = Field(default=0, ge=0, le=MAX_GENERATION)
    mode: Literal["disabled", "shadow", "local_fixture_canary"] = "disabled"
    policy_digest: Digest | None = None
    build_digest: Digest | None = None
    issued_at: int | None = Field(default=None, gt=0)
    expires_at: int | None = Field(default=None, gt=0)
    approval: SignedEvidence | None = None

    @model_validator(mode="after")
    def valid_state(self):
        active = self.mode != "disabled"
        if (
            any((fact is not None) != active for fact in (
                self.policy_digest, self.build_digest, self.issued_at, self.expires_at,
            ))
            or active and (
                not 0 < self.generation < MAX_GENERATION
                or not 0 < self.expires_at - self.issued_at <= MAX_AGE
            )
            or (self.approval is not None) != (self.mode == "local_fixture_canary")
        ):
            raise ValueError("adaptive_pointer_invalid")
        if self.approval is not None:
            evidence = self.approval.evidence
            if (
                self.build_digest != evidence.build_digest
                or self.policy_digest != evidence.policy_digest
                or self.policy_digest != FINITE.identity
                or self.expires_at > evidence.expires_at
            ):
                raise ValueError("adaptive_pointer_evidence_mismatch")
        return self


class StaleGeneration(ValueError):
    pass


class LocalPolicyControl:
    """Explicit private directory, fixed filename, advisory directory lock and atomic CAS."""

    def __init__(self, directory: Path):
        if not directory.is_absolute() or ".." in directory.parts or directory == Path("/"):
            raise ValueError("adaptive_control_absolute_directory_required")
        self.directory = directory

    @contextmanager
    def _directory(self, *, write=False):
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        fd = os.open("/", flags)
        try:
            for name in self.directory.parts[1:]:
                child = os.open(name, flags, dir_fd=fd)
                os.close(fd)
                fd = child
            facts = os.fstat(fd)
            if facts.st_uid != os.getuid() or stat.S_IMODE(facts.st_mode) != 0o700:
                raise ValueError("adaptive_control_private_directory_required")
            fcntl.flock(fd, fcntl.LOCK_EX if write else fcntl.LOCK_SH | fcntl.LOCK_NB)
            yield fd
        finally:
            os.close(fd)

    @staticmethod
    def _read(fd):
        try:
            handle = os.open(POINTER, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        except FileNotFoundError:
            return PolicyPointer()
        with os.fdopen(handle, "rb") as stream:
            facts = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(facts.st_mode) or facts.st_uid != os.getuid()
                or stat.S_IMODE(facts.st_mode) != 0o600 or facts.st_nlink != 1
            ):
                raise ValueError("adaptive_control_invalid_file")
            payload = stream.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise ValueError("adaptive_control_oversized")
        json.loads(payload, object_pairs_hook=_unique_fields)
        return PolicyPointer.model_validate_json(payload)

    @contextmanager
    def admission(self):
        # Keep the shared lock until the caller commits the new admission.
        with self._directory() as fd:
            yield self._read(fd)

    @staticmethod
    def _replace(fd, pointer):
        temporary = f".adaptive-{secrets.token_hex(16)}"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        with os.fdopen(os.open(temporary, flags, 0o600, dir_fd=fd), "wb") as stream:
            try:
                stream.write(pointer.model_dump_json().encode())
                stream.flush()
                os.fsync(stream.fileno())
                os.replace(temporary, POINTER, src_dir_fd=fd, dst_dir_fd=fd)
                os.fsync(fd)
            finally:
                with suppress(FileNotFoundError):
                    os.unlink(temporary, dir_fd=fd)

    def update(self, expected_generation, pointer, *, reviewer_key=None):
        pointer = PolicyPointer.model_validate_json(pointer.model_dump_json())
        # A signature authenticates the publisher, but does not prove that its
        # reported metrics were recomputed from independently held artifacts.
        # This checkout has no independent blind artifact verifier/custodian.
        if pointer.mode == "local_fixture_canary":
            raise ValueError("adaptive_control_blocked_unverified_independent_evidence")
        with self._directory(write=True) as fd:
            if self._read(fd).generation != expected_generation:
                raise StaleGeneration("adaptive_control_generation_changed")
            if pointer.generation != expected_generation + 1:
                raise ValueError("adaptive_control_generation_invalid")
            now = time()
            if pointer.mode != "disabled" and not pointer.issued_at <= now < pointer.expires_at:
                raise ValueError("adaptive_control_expired")
            if pointer.approval is not None and not pointer.approval.verified(reviewer_key, now):
                raise ValueError("adaptive_control_unapproved")
            self._replace(fd, pointer)
        return pointer

    def rollback(self):
        with self._directory(write=True) as fd:
            current = self._read(fd)
            if current.mode == "disabled":
                return False, current
            disabled = PolicyPointer(generation=current.generation + 1)
            self._replace(fd, disabled)
            return True, disabled


def main():
    parser = argparse.ArgumentParser(description="Disable new local adaptive fixture admissions.")
    parser.add_argument("directory", type=Path, nargs="?")
    args = parser.parse_args()
    if args.directory is None or args.directory == Path("."):
        print("SAFE_NO_OP no local control configured")
        return
    try:
        changed, pointer = LocalPolicyControl(args.directory).rollback()
    except FileNotFoundError:
        print("SAFE_NO_OP no local control configured")
        return
    except (OSError, ValueError):
        parser.exit(1, "LOCAL_CONTROL_UNAVAILABLE admissions use the baseline\n")
    print(f"{'ROLLED_BACK' if changed else 'SAFE_NO_OP'} generation={pointer.generation}")


if __name__ == "__main__":
    main()
