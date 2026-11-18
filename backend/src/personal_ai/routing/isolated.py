"""Internal, source-free composition. Application factories never construct it."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from personal_ai.auth.scope import ApplicationScope

from .contracts import Sensitivity
from .decision_models import PreparationIdentity, RoutingEvent
from .owner_policy import ExactRoute, PolicyDenied, order_candidates, read_policy
from .price import PaidExposure
from .service import ISOLATED_RUN_PREFIX, RoutingFinalizationError

OPERATION = "bounded_generation"
NO_ROUTE = "no_authorized_external_inference_route"
# These are candidate-specific facts known before claim. Ambiguous authority failures stop.
ADVANCE_REASONS = frozenset(
    {
        "provider_quota_exhausted",
        "endpoint_quota_exhausted",
        "endpoint_health_unavailable",
        "quota-exhausted",
        "provider_endpoint_cooling_down",
        "inference_budget_exhausted",
        "required_quality_floor_not_met",
        "required_quality_evidence_stale_or_missing",
        "endpoint_disabled_or_unconfigured",
        "strict_free_attestation_expired",
    }
)


def _hash(value):
    return hashlib.sha256(
        json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()


@dataclass(frozen=True)
class SyntheticTransport:
    """Fixture adapter with one write entry point, without retries or network discovery."""

    write: Callable

    def __call__(self, profile, invocation, attempt, payload):
        return self.write(profile, invocation, attempt, payload)


@dataclass(frozen=True)
class _Admission:
    coordinator: "IsolatedInferenceRouting"
    root_id: UUID
    scope: ApplicationScope
    owner_id: str
    actor_id: str
    payload_sha256: str
    plan_sha256: str
    deadline: datetime
    revision: int
    candidate: int
    route: ExactRoute
    exposure: PaidExposure | None
    sensitivity: Sensitivity
    payload: bytes = field(default=b"", repr=False)

    @property
    def run_id(self):
        return f"{ISOLATED_RUN_PREFIX}{self.root_id}:{self.candidate}"

    @property
    def paid_endpoint(self):
        return self.route.profile if self.exposure is not None else None

    def root(self, connection, now, *, state="open", allow_expired=False):
        row = self.coordinator.repository.root(connection, self.root_id, self.owner_id)
        if (
            row is None
            or row[:5]
            != (
                self.payload_sha256,
                self.plan_sha256,
                self.deadline,
                self.candidate,
                state,
            )
            or (not allow_expired and now >= self.deadline)
        ):
            raise PolicyDenied("inference_request_fenced")
        return row

    def require(self, connection, now, *, decision=None, preparation=None, state="open"):
        row = self.root(connection, now, state=state)
        scope = self.coordinator.settings.verified_scope()
        if (
            (scope.owner_id, scope.acting_user_id, scope.application_id, scope.workspace_id)
            != (self.owner_id, self.actor_id, self.scope.application_id, self.scope.workspace_id)
            or (
                decision is not None
                and (
                    decision.request.run_id != self.run_id
                    or decision.selected != self.route.profile
                )
            )
            or (
                preparation is not None
                and (
                    preparation.prepared_input_sha256 != self.payload_sha256
                    or preparation.source_reference_sha256s
                )
            )
        ):
            raise PolicyDenied("inference_binding_changed")
        self.coordinator.require_authority(connection, self, now)
        return row

    def change(self, connection, *, state="open", attempt_id=None, advance=False):
        self.coordinator.repository.change_root(
            connection,
            root_id=self.root_id,
            owner_id=self.owner_id,
            candidate=self.candidate + int(advance),
            state=state,
            attempt_id=attempt_id,
        )

    def reserve(self, connection, usage, invocation, attempt_id, now):
        row = self.require(connection, now)
        if row[5] is not None:
            raise PolicyDenied("inference_request_fenced")
        if self.exposure is not None:
            usage.reserve_money_in_transaction(
                connection, invocation, attempt_id, self.root_id, self.exposure, now
            )
        self.change(connection, attempt_id=attempt_id)

    def require_reservation(self, connection, usage, invocation, attempt_id, now, *, claim=False):
        row = self.require(connection, now)
        if row[5] != attempt_id:
            raise PolicyDenied("inference_reservation_changed")
        if self.exposure is not None:
            usage.require_money_in_transaction(
                connection, invocation, attempt_id, self.root_id, self.exposure, now, claim=claim
            )
        if claim:
            self.change(connection, state="fenced", attempt_id=attempt_id)

    def before_send(self, routing, record, profile):
        with routing.observations.transaction(owner_id=self.owner_id) as connection:
            now = routing.observations.current_time(connection)
            self.require(connection, now, decision=record.decision, state="fenced")
            requirements = record.decision.request.requirements
            current = routing.registry._revalidate_selected(
                profile.ref,
                requirements,
                now=now,
                connection=connection,
                synthetic_paid=self.paid_endpoint,
            )
            if not self.route.matches(current):
                raise PolicyDenied("inference_binding_changed")
            routing._authorize(
                connection, self.owner_id, self.scope, profile.ref, record.decision.request, (), now
            )
            if routing.observations.current_time(connection) >= self.deadline:
                raise PolicyDenied("inference_deadline_expired")


@dataclass(frozen=True)
class PlanOfferEvidence:
    """Independent fixture observations for consent, program and allowance."""

    route: ExactRoute
    prepared_sha256: str
    installation_id: UUID
    connection_id: UUID
    connection_revision: int
    valid_until: datetime
    owner_plan_consent: bool
    distribution_eligible: bool
    account_model_verified: bool
    included_only_verified: bool

    def matches(self, admission, package, choice):
        return (
            self.route == admission.route
            and self.prepared_sha256 == package.fingerprint
            and self.installation_id == choice.audience
            and self.connection_id == package.connection_id
            and self.connection_revision == package.connection_revision
        )

    def eligible(self, now):
        return (
            self.valid_until.utcoffset() is not None
            and now < self.valid_until
            and self.owner_plan_consent is True
            and self.distribution_eligible is True
            and self.account_model_verified is True
            and self.included_only_verified is True
        )


@dataclass(frozen=True)
class SyntheticOffer:
    """An already prepared external turn and its trusted account eligibility check."""

    issuer: object
    conversation_id: object
    prepared: object
    choice: object


class IsolatedInferenceRouting:
    """One bounded logical request across the canonical decision/attempt lifecycle.

    The injected authority supplies exact grants and optional price facts from
    independent fixture state. It must fail closed on restore, revoke or drift.
    """

    def __init__(self, routing, settings, *, authority):
        self.routing = routing
        self.settings = settings
        self.repository = settings.repository
        self.authority = authority

    def require_authority(self, connection, admission, now):
        if self.authority.recovery_current(connection) is not True:
            raise PolicyDenied("inference_financial_reconciliation_required")
        revision, raw = self.repository.read_in_transaction(connection, admission.owner_id)
        policy, diagnostic = read_policy(raw)
        if diagnostic or revision != admission.revision or admission.route not in policy.allow:
            raise PolicyDenied("inference_policy_changed")
        grant, exposure = self.authority.current(connection, admission, now)
        if (
            grant is None
            or grant.route != admission.route
            or not grant.permits(
                owner_id=admission.owner_id,
                actor_id=admission.actor_id,
                payload_sha256=admission.payload_sha256,
                sensitivity=admission.sensitivity,
                now=now,
            )
            or exposure != admission.exposure
            or (
                exposure is not None
                and (
                    exposure.route != admission.route
                    or exposure.owner_cap_micros != policy.owner_monthly_cap_micros
                    or not exposure.price_start <= now < exposure.price_end
                    or not exposure.period.start <= now < exposure.period.end
                )
            )
        ):
            raise PolicyDenied("inference_authority_changed")
        return grant

    def _open(self, *, request, task, payload, ranked, recipient, narrowing):
        payload_sha256 = hashlib.sha256(payload).hexdigest()
        identity = self.settings.verified_scope()
        scope = ApplicationScope(
            application_id=identity.application_id, workspace_id=identity.workspace_id
        )
        if (
            request.operation not in {None, OPERATION}
            or request.source_reference_sha256s
            or request.run_id is not None
            or (request.requirements.execution_mode, request.requirements.automatic)
            != ("STRICT_FREE", True)
            or request.requirements.required_capabilities != {OPERATION}
            or request.requirements.sensitivity == "restricted"
            or request.requirements.input_tokens is None
            or request.requirements.output_tokens is None
            or not 0 < request.requirements.output_tokens
            or request.requirements.input_tokens + request.requirements.output_tokens > 200_000
            or task.cascade_policy is not None
            or task.max_auxiliary_calls != 0
            or task.max_physical_attempts != 1
            or len(ranked) > 16
        ):
            raise PolicyDenied(NO_ROUTE)
        root_id = uuid5(
            NAMESPACE_URL,
            _hash(
                [
                    "isolated-inference",
                    identity.owner_id,
                    scope.application_id,
                    OPERATION,
                    request.request_id,
                ]
            ),
        )
        with self.routing.observations.transaction(owner_id=identity.owner_id) as connection:
            now = self.routing.observations.current_time(connection)
            revision, raw = self.repository.read_in_transaction(connection, identity.owner_id)
            policy, diagnostic = read_policy(raw)
            if diagnostic:
                raise PolicyDenied(NO_ROUTE)
            if self.authority.recovery_current(connection) is not True:
                raise PolicyDenied(NO_ROUTE)
            snapshot = self.routing.registry.candidates(
                request.requirements, now=now, connection=connection
            )
            profiles = tuple(assessment.profile for assessment in snapshot.assessments)
            # The existing strategy supplies the within-class rank; the current
            # canonical routing path still rechecks eligibility, quality and capacity.
            ranked = tuple(
                route
                for route in ranked
                if any(
                    route.matches(profile) and profile.data_use_policy.status == "approved"
                    for profile in profiles
                )
            )
            facts = {}
            for route in ranked:
                probe = _Admission(
                    self,
                    root_id,
                    scope,
                    identity.owner_id,
                    identity.acting_user_id,
                    payload_sha256,
                    "",
                    now,
                    revision,
                    0,
                    route,
                    None,
                    request.requirements.sensitivity,
                )
                grant, exposure = self.authority.current(connection, probe, now)
                if grant is not None and (
                    (route.route_class == "paid_api") == (exposure is not None)
                ):
                    facts[route] = grant, exposure
            ordered = order_candidates(
                policy,
                ranked=ranked,
                grants=tuple(grant for grant, _ in facts.values()),
                owner_id=identity.owner_id,
                actor_id=identity.acting_user_id,
                scope=scope,
                recipient=recipient,
                payload_sha256=payload_sha256,
                narrowing=narrowing,
                sensitivity=request.requirements.sensitivity,
                now=now,
            )
            if not ordered:
                raise PolicyDenied(NO_ROUTE)
            plan_sha256 = _hash(
                [
                    revision,
                    identity.acting_user_id,
                    scope.model_dump(),
                    recipient,
                    request.model_dump(mode="json"),
                    task.model_dump(mode="json"),
                    [
                        [
                            route.model_dump(mode="json"),
                            facts[route][1].fingerprint if facts[route][1] else None,
                        ]
                        for route in ordered
                    ],
                ]
            )
            row = self.repository.open_root(
                connection,
                root_id=root_id,
                owner_id=identity.owner_id,
                payload=payload_sha256,
                plan=plan_sha256,
                deadline=now + timedelta(milliseconds=task.deadline_ms),
            )
            if row[4] != "open" or now >= row[2]:
                raise PolicyDenied("inference_request_fenced")
            return tuple(
                _Admission(
                    self,
                    root_id,
                    scope,
                    identity.owner_id,
                    identity.acting_user_id,
                    payload_sha256,
                    plan_sha256,
                    row[2],
                    revision,
                    index,
                    route,
                    facts[route][1],
                    request.requirements.sensitivity,
                    payload,
                )
                for index, route in enumerate(ordered)
                if index >= row[3]
            )

    def _advance(self, admission, *, permit=None):
        identity = self.settings.verified_scope()
        if (
            identity.owner_id != admission.owner_id
            or identity.acting_user_id != admission.actor_id
            or identity.application_id != admission.scope.application_id
            or identity.workspace_id != admission.scope.workspace_id
        ):
            raise PolicyDenied(NO_ROUTE)
        with self.routing.observations.transaction(owner_id=admission.owner_id) as connection:
            now = self.routing.observations.current_time(connection)
            may_advance = True
            if permit is None:
                row = admission.require(connection, now)
                if row[5] is not None:
                    raise PolicyDenied("inference_request_fenced")
            else:
                if self.authority.recovery_current(connection) is not True:
                    raise PolicyDenied("inference_financial_reconciliation_required")
                row = admission.root(connection, now, allow_expired=True)
                try:
                    admission.require(connection, now)
                except PolicyDenied:
                    # The exact unclaimed attempt can be released. Changed authority
                    # or expiry prevents progression to another candidate.
                    may_advance = False
                record = self.routing.observations.lock_root(
                    connection,
                    owner_id=admission.owner_id,
                    scope=admission.scope,
                    decision_id=permit.decision_id,
                )
                if (
                    row[5] != permit.attempt_id
                    or record.status != "authorized"
                    or record.events[-1].permit != permit
                    or record.decision.request.run_id != admission.run_id
                ):
                    raise PolicyDenied("inference_request_fenced")
                self.routing.usage.cancel_unclaimed_in_transaction(
                    connection,
                    permit,
                    root_id=admission.root_id,
                    paid=admission.exposure is not None,
                    now=now,
                )
                self.routing.observations.append_in_transaction(
                    connection,
                    scope=admission.scope,
                    record=record,
                    event=RoutingEvent(
                        kind="failed",
                        occurred_at=now,
                        reason="inference_definitive_no_send",
                        attempt_id=permit.attempt_id,
                    ),
                )
            admission.change(
                connection,
                state="open" if may_advance else "stopped",
                advance=may_advance,
            )

    def _offer(self, admission, offer):
        from personal_ai.services.external_turns.service import ExternalTurnService

        if (
            type(offer) is not SyntheticOffer
            or type(offer.issuer) is not ExternalTurnService
            or offer.prepared.connected_package is None
        ):
            raise PolicyDenied(NO_ROUTE)
        package = offer.prepared.connected_package
        reservation = offer.prepared.reservation
        if (
            package.owner_id != admission.owner_id
            or package.application_id != admission.scope.application_id
            or package.workspace_id != admission.scope.workspace_id
            or package.execution_profile.endpoint != admission.route.profile
            or package.model_id != admission.route.model
            or package.effective_sensitivity != admission.sensitivity
            or reservation.request_digest != admission.payload_sha256
            or reservation.selected_memory_ids
            or offer.issuer.local_chat is None
            or offer.issuer.local_chat.scope.actor_id != admission.actor_id
        ):
            raise PolicyDenied("inference_binding_changed")
        with self.routing.observations.transaction(owner_id=admission.owner_id) as connection:
            now = self.routing.observations.current_time(connection)
            row = admission.require(connection, now)
            grant = self.require_authority(connection, admission, now)
            evidence = self.authority.plan_offer(connection, admission, package, offer.choice, now)
            if (
                row[5] is not None
                or type(evidence) is not PlanOfferEvidence
                or not evidence.matches(admission, package, offer.choice)
            ):
                raise PolicyDenied(NO_ROUTE)
            if not evidence.eligible(now):
                admission.change(connection, advance=True)
                return None
            admission.change(connection, state="fenced")
        # The canonical issuer repeats its local-installation/source check and
        # fences the signed grant before returning it. Any error keeps this root fenced.
        return offer.issuer.dispatch(
            offer.conversation_id,
            offer.prepared,
            offer.choice,
            offer_deadline=min(admission.deadline, grant.valid_until, evidence.valid_until),
            routing_root=admission.root_id,
        )

    def prepare(
        self,
        *,
        request,
        task,
        payload,
        ranked,
        recipient,
        prepare_candidate,
        quality_evidence=(),
        routing_signals=(),
        narrowing=None,
    ):
        """Reserve a candidate or issue an executable local offer only after fencing."""
        try:
            return self._prepare(
                request=request,
                task=task,
                payload=payload,
                ranked=ranked,
                recipient=recipient,
                prepare_candidate=prepare_candidate,
                quality_evidence=quality_evidence,
                routing_signals=routing_signals,
                narrowing=narrowing,
            )
        except PolicyDenied:
            raise
        except Exception:  # noqa: BLE001 - source and provider details are private
            raise PolicyDenied(NO_ROUTE) from None

    def _prepare(
        self,
        *,
        request,
        task,
        payload,
        ranked,
        recipient,
        prepare_candidate,
        quality_evidence=(),
        routing_signals=(),
        narrowing=None,
    ):
        if type(payload) is not bytes or not 0 < len(payload) <= 262144:
            raise PolicyDenied(NO_ROUTE)
        candidates = self._open(
            request=request,
            task=task,
            payload=payload,
            ranked=ranked,
            recipient=recipient,
            narrowing=narrowing,
        )
        for admission in candidates:
            with self.routing.observations.transaction(owner_id=admission.owner_id) as connection:
                admission.require(connection, self.routing.observations.current_time(connection))
            if admission.route.route_class == "subscription":
                offer = prepare_candidate(admission.route, None)
                if offer is None:
                    self._advance(admission)
                    continue
                proof = self._offer(admission, offer)
                if proof is not None:
                    return proof
                continue
            requirements = request.requirements
            if admission.exposure is not None:
                requirements = type(requirements).model_validate(
                    {
                        **requirements.model_dump(),
                        "execution_mode": "EXPLICIT_BYOK",
                        "automatic": False,
                    }
                )
            scoped_request = type(request).model_validate(
                {
                    **request.model_dump(),
                    "request_id": f"{admission.root_id}:{admission.candidate}",
                    "run_id": admission.run_id,
                    "operation": OPERATION,
                    "requirements": requirements.model_dump(),
                }
            )
            decision = self.routing._route(
                owner_id=admission.owner_id,
                scope=admission.scope,
                task=task,
                request=scoped_request,
                quality_evidence=quality_evidence,
                routing_signals=routing_signals,
                admission=admission,
            )
            if decision.selected is None:
                reasons = {
                    code
                    for candidate in decision.candidates
                    for code in candidate.rejection_reasons
                }
                if reasons and reasons <= ADVANCE_REASONS:
                    self._advance(admission)
                    continue
                raise PolicyDenied(NO_ROUTE)
            preparation = prepare_candidate(admission.route, decision)
            if preparation is None:
                self._advance(admission)
                continue
            if not isinstance(preparation, PreparationIdentity):
                raise PolicyDenied(NO_ROUTE)
            try:
                permit = self.routing._finalize(
                    owner_id=admission.owner_id,
                    scope=admission.scope,
                    decision_id=decision.routing_decision_id,
                    preparation=preparation,
                    operation=OPERATION,
                    admission=admission,
                )
            except RoutingFinalizationError as error:
                if error.code not in ADVANCE_REASONS:
                    raise PolicyDenied(NO_ROUTE) from None
                self._advance(admission)
                continue
            return admission, permit
        raise PolicyDenied(NO_ROUTE)

    def abandon_unclaimed(self, prepared):
        admission, permit = prepared
        if admission.coordinator is not self:
            raise PolicyDenied(NO_ROUTE)
        self._advance(admission, permit=permit)

    def dispatch(self, prepared, *, transport):
        admission, permit = prepared
        if (
            admission.coordinator is not self
            or type(transport) is not SyntheticTransport
            or hashlib.sha256(admission.payload).hexdigest() != admission.payload_sha256
        ):
            raise PolicyDenied(NO_ROUTE)
        try:
            return self.routing._dispatch(
                owner_id=admission.owner_id,
                scope=admission.scope,
                permit=permit,
                operation=OPERATION,
                send=lambda profile, invocation, attempt: transport(
                    profile,
                    invocation,
                    attempt,
                    admission.payload,
                ),
                admission=admission,
            )
        except Exception:  # noqa: BLE001 - transport and authority errors stay content-free
            # Failure after commit never makes the logical root executable again.
            raise PolicyDenied("inference_execution_unavailable") from None
