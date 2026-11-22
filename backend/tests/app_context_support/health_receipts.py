"""Candidate transaction and Ed25519 receipt vectors for the offline Health host."""

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from threading import Lock
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import Request

from personal_ai.api.private_application_plan import PROFILE_PREFIX
from personal_ai.auth.application_clients import require_current_client_authority
from personal_ai.auth.scope import current_verified_principal
from personal_ai.context.providers import ContextPreparationError
from personal_ai.services.external_turns.application_plan import PlanPreview, PlanTarget
from tests.app_context_support.health_preview import (
    CATEGORY,
    DENIED,
    FIELDS,
    PROVIDER,
    HealthSource,
    Selection,
    canonical,
    digest,
    unique,
)

TITLE = "Health preference preview"
ISSUER = "urn:fixture:pas:health-preview"
AUDIENCE = "urn:fixture:health:preview-receipt"
KEY_ID = "offline-preview-key"
LIFETIME = 30
NONCE_HEADER = "x-fixture-health-transaction"


@dataclass(frozen=True)
class Enrollment:
    enrollment_id: UUID
    generation: int
    installation_id: UUID
    health_owner_id: UUID
    pas_owner_id: str
    actor: str
    client_namespace: str
    selected: Selection
    source_epoch: str
    policy_epoch: str

    @property
    def target_id(self):
        return "health-preview:" + digest(self.claims())

    def claims(self):
        return {
            "enrollment_id": str(self.enrollment_id),
            "enrollment_generation": self.generation,
            "installation_id": str(self.installation_id),
            "health_owner_id": str(self.health_owner_id),
            "pas_owner_id": self.pas_owner_id,
            "actor": self.actor,
            "client_namespace": self.client_namespace,
            "application_id": "health",
            "workspace_id": None,
            "selection": {
                "category": CATEGORY,
                "object_type": "profile_item",
                "object_id": str(self.selected.object_id),
                "revision": self.selected.revision,
                "fields": list(FIELDS),
            },
            "source_epoch": self.source_epoch,
            "policy_epoch": self.policy_epoch,
        }


@dataclass(frozen=True)
class Operation:
    enrollment: Enrollment
    key: UUID
    create_key: UUID
    request_digest: str
    conversation_id: UUID | None
    frozen_target: str
    branch_digest: str | None
    expires: int

    @property
    def purpose(self):
        return "create" if self.conversation_id is None else "preview"

    @property
    def path(self):
        if self.conversation_id is None:
            return PROFILE_PREFIX
        return f"{PROFILE_PREFIX}/{self.conversation_id}/context-preview"

    @property
    def intent(self):
        return (
            self.enrollment,
            self.key,
            self.create_key,
            self.request_digest,
            self.conversation_id,
            self.frozen_target,
            self.branch_digest,
        )


def encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def decode(segment):
    decoded = base64.b64decode(segment + "=" * (-len(segment) % 4), altchars=b"-_", validate=True)
    if encode(decoded) != segment:
        raise ValueError("invalid encoding")
    return decoded


def receipt_fields(operation, conversation, body, now):
    return {
        "schema_version": f"health-application-plan-{operation.purpose}-receipt-v1",
        "alg": "Ed25519",
        "kid": KEY_ID,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": min(now + LIFETIME, operation.expires),
        "purpose": operation.purpose,
        "method": "POST",
        "path": operation.path,
        "original_key": str(operation.key),
        "original_create_key": str(operation.create_key),
        "request_digest": operation.request_digest,
        "response_digest": sha256(body).hexdigest(),
        "conversation_id": str(conversation),
        "target_fingerprint": operation.frozen_target,
        **operation.enrollment.claims(),
    }


class ReceiptAuthority:
    """Private in-process state stands in for the unresolved live C1 hop."""

    def __init__(self, key: Ed25519PrivateKey, current_enrollment, current_branch):
        self.key = key
        self.current_enrollment = current_enrollment
        self.current_branch = current_branch
        self.pending = {}
        self.creates = {}
        self.preview_keys = set()
        self.lock = Lock()

    def _require_current(self, operation, target):
        require_current_client_authority()
        principal = current_verified_principal()
        enrolled = operation.enrollment
        scope = target.scope
        now = int(datetime.now(UTC).timestamp())
        if (
            principal is None
            or not principal.authenticated
            or principal.authenticated_at is None
            or not now - 300 <= principal.authenticated_at <= now
            or principal.owner_id != enrolled.pas_owner_id
            or f"{principal.issuer}|{principal.subject}" != enrolled.actor
            or (scope.application_id, scope.workspace_id, scope.client_namespace)
            != ("health", None, enrolled.client_namespace)
            or target.preview_source
            != HealthSource.selection(enrolled.target_id, enrolled.selected)
            or self.current_enrollment(enrolled.enrollment_id) != enrolled
            or not 0 < operation.expires - now <= LIFETIME
        ):
            raise ContextPreparationError(DENIED)

    def __call__(
        self, request: Request, target: PlanTarget, conversation_id: UUID | None, raw: bytes
    ):
        nonces = request.headers.getlist(NONCE_HEADER)
        if len(nonces) != 1:
            raise ContextPreparationError(DENIED)
        # Only a capability deposited out of band by the synthetic initiating caller is accepted.
        request_body = json.loads(raw, object_pairs_hook=unique)
        with self.lock:
            operation = self.pending.get(nonces[0])
            if operation is None:
                raise ContextPreparationError(DENIED)
            self._require_current(operation, target)
            binding = target.preview_binding(
                current_verified_principal(), conversation_id or UUID(int=0)
            )
            if (
                request.method != "POST"
                or request.url.path != operation.path
                or conversation_id != operation.conversation_id
                or request_body.get("idempotency_key") != str(operation.key)
                or digest(request_body) != operation.request_digest
                or binding.target_fingerprint != operation.frozen_target
            ):
                raise ContextPreparationError(DENIED)
            self.pending.pop(nonces[0])
            enrollment_key = operation.enrollment.enrollment_id, operation.create_key
            if operation.purpose == "create":
                if request_body.get("title") != TITLE or operation.key != operation.create_key:
                    raise ContextPreparationError(DENIED)
                saved, _ = self.creates.setdefault(enrollment_key, (operation, None))
                if saved.intent != operation.intent:
                    raise ContextPreparationError(DENIED)
            else:
                saved = self.creates.get(enrollment_key)
                preview_key = operation.enrollment.enrollment_id, operation.key
                if (
                    saved is None
                    or saved[0].enrollment != operation.enrollment
                    or saved[0].frozen_target != operation.frozen_target
                    or saved[1] != operation.conversation_id
                    or operation.create_key == operation.key
                    or preview_key in self.preview_keys
                ):
                    raise ContextPreparationError(DENIED)
                self.preview_keys.add(preview_key)

        def attest(conversation, body, frozen: PlanPreview | None):
            self._require_current(operation, target)
            statement = receipt_fields(
                operation, conversation, body, int(datetime.now(UTC).timestamp())
            )
            if frozen is not None:
                if self.current_branch(operation.enrollment.pas_owner_id, conversation) != (
                    operation.branch_digest
                ):
                    raise ContextPreparationError(DENIED)
                statement.update(self._preview_claims(operation, conversation, body, frozen))
                statement["exp"] = min(statement["exp"], int(frozen.expires_at.timestamp()))
                if statement["exp"] <= statement["iat"]:
                    raise ContextPreparationError(DENIED)
            encoded = canonical(statement)
            signature = self.key.sign(encoded)
            if frozen is None:
                with self.lock:
                    original, prior_id = self.creates[enrollment_key]
                    if prior_id is not None and prior_id != conversation:
                        raise ContextPreparationError(DENIED)
                    self.creates[enrollment_key] = original, conversation
            return f"{encode(encoded)}.{encode(signature)}"

        return attest

    @staticmethod
    def _preview_claims(operation, conversation, body, frozen):
        source = next(snapshot for snapshot in frozen.snapshots if snapshot.provider_id == PROVIDER)
        memory = next(
            snapshot for snapshot in frozen.snapshots if snapshot.provider_id == "ai_memory"
        )
        authority = source.application_plan_authority
        manifest = json.loads(body)
        if (
            authority is None
            or authority.binding.target_fingerprint != operation.frozen_target
            or authority.binding.conversation_id != conversation
            or frozen.original_key != operation.key
            or source.source_version != str(operation.enrollment.selected.revision)
            or frozen.context.branch_digest != operation.branch_digest
            or frozen.context.inference.policy_version != operation.enrollment.policy_epoch
            or len(manifest["selected_context"]) != 3
            or manifest["selected_context"][0]["turns"] < 1
        ):
            raise ContextPreparationError(DENIED)
        return {
            "branch_digest": frozen.context.branch_digest,
            "actual_revision": int(source.source_version),
            "permission_version": source.permission_dependencies[0].version,
            "source_sensitivity": authority.source_sensitivity,
            "source_grants": {grant.purpose: grant.version for grant in authority.grants},
            "memory_grants": {dep.purpose: dep.version for dep in memory.permission_dependencies},
            "inventory_digest": digest(manifest["selected_context"]),
            "confirmation": frozen.confirmation,
            "destination": manifest["destination"],
        }


def verify_receipt(header, *, keys, expected, response, now):
    """Strict candidate receiver. Expected context comes from its original binding."""
    if len(header) > 8192:
        raise ValueError("receipt too large")
    try:
        statement_segment, signature_segment = header.split(".")
        raw = decode(statement_segment)
        claims = json.loads(raw.decode(), object_pairs_hook=unique)
        if not isinstance(claims, dict) or canonical(claims) != raw:
            raise ValueError("invalid statement encoding")
        iat, exp = claims["iat"], claims["exp"]
        pinned = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "alg": "Ed25519",
            "kid": KEY_ID,
            "response_digest": sha256(response).hexdigest(),
        }
        if (
            type(iat) is not int
            or type(exp) is not int
            or not iat <= now < exp
            or not 0 < exp - iat <= LIFETIME
            or canonical(claims) != canonical({**expected, **pinned, "iat": iat, "exp": exp})
        ):
            raise ValueError("receipt does not match")
        keys[claims["kid"]].verify(decode(signature_segment), raw)
        return claims
    except (KeyError, InvalidSignature, UnicodeError, RecursionError) as error:
        raise ValueError("invalid receipt") from error
