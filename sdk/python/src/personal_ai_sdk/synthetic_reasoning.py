"""Opt-in source-free fixture operations on the isolated loopback protocol."""

from urllib.parse import urlsplit
from uuid import UUID

from .client import (
    CapabilityUnavailable,
    Client,
    Identity,
    JsonObject,
    UncertainTurn,
    _id,
)

CAPABILITY = "reasoning.workflow.synthetic.v1"
PREFIX = "/v1/synthetic-reasoning"
TASKS = ("sum", "pair")
EFFORTS = ("auto", "low", "medium", "high", "max")
CEILINGS = {
    "model_calls": 1,
    "verifier_calls": 1,
    "count_calls": 8,
    "count_input_bytes": 8192,
    "input_bytes": 1024,
    "output_bytes": 128,
    "result_bytes": 128,
    "deadline_ms": 6000,
    "concurrency": 1,
    "external_sources": 0,
    "provider_cost_usd": "0.00",
}


class SyntheticReasoning:
    """Keep the negotiated instance and original key for reconciliation."""

    def __init__(
        self, base_url: str, token: str, *, expected_epoch: Identity | None = None
    ) -> None:
        if urlsplit(base_url).hostname != "127.0.0.1":
            raise ValueError("synthetic_reasoning_requires_ipv4_loopback")
        self._client = Client(
            base_url,
            token,
            application="personal_ai",
            allow_loopback=True,
            timeout=8,
        )
        self._expected_epoch = (
            _id(expected_epoch) if expected_epoch is not None else None
        )
        self._instance: str | None = None

    def negotiate(self) -> JsonObject:
        descriptor = self._exchange("GET", PREFIX + "/capability")
        ceilings = descriptor.get("limits")
        pinned = self._instance or self._expected_epoch
        states = ("development_only", "disabled") if pinned else ("development_only",)
        if (
            descriptor.get("capability") != CAPABILITY
            or descriptor.get("state") not in states
            or descriptor.get("evidence_tier") != "E1"
            or descriptor.get("default_enabled") is not False
            or descriptor.get("strategy") != "direct-verified.v1"
            or descriptor.get("effective_effort") != "low"
            or descriptor.get("tasks") != list(TASKS)
            or descriptor.get("requested_efforts") != list(EFFORTS)
            or not isinstance(ceilings, dict)
            or ceilings != CEILINGS
            or any(
                type(ceilings[name]) is not type(value)
                for name, value in CEILINGS.items()
            )
            or type(descriptor.get("queue")) is not int
            or descriptor["queue"] != 0
            or type(descriptor.get("max_originals")) is not int
            or descriptor["max_originals"] != 64
        ):
            raise CapabilityUnavailable("synthetic_reasoning_unavailable")
        epoch = descriptor.get("epoch")
        if not isinstance(epoch, str):
            raise CapabilityUnavailable("synthetic_reasoning_unavailable")
        try:
            instance = _id(epoch)
        except ValueError:
            raise CapabilityUnavailable("synthetic_reasoning_unavailable") from None
        if pinned is not None and instance != pinned:
            raise UncertainTurn(
                "reasoning_epoch_changed; original operation cannot be reconciled"
            )
        self._instance = instance
        return descriptor

    def _runs(self) -> str:
        if self._instance is None:
            raise CapabilityUnavailable("synthetic_reasoning_negotiation_required")
        return f"{PREFIX}/{self._instance}/runs"

    def _exchange(self, method: str, path: str, body: object = None) -> JsonObject:
        return self._client._json(method, path, body, max_body=2048, max_response=32768)

    def submit(
        self,
        key: Identity,
        task: str,
        *,
        effort: str = "auto",
        limits: JsonObject | None = None,
    ) -> JsonObject:
        """Execute once in the foreground. A repeated original returns metadata."""
        if task not in TASKS or effort not in EFFORTS:
            raise ValueError("invalid_reasoning_task_or_effort")
        body = {
            "capability": CAPABILITY,
            "original_key": _id(key),
            "task": task,
            "effort": effort,
        }
        if limits is not None:
            for name, value in limits.items():
                ceiling = CEILINGS.get(name)
                if (
                    type(ceiling) is int
                    and type(value) is int
                    and 0 <= value <= ceiling
                ):
                    continue
                if name != "provider_cost_usd" or value != "0.00":
                    raise ValueError("invalid_reasoning_limits")
            body["limits"] = limits
        return self._receipt(self._exchange("POST", self._runs(), body), result=True)

    def status(self, key: Identity, *, cursor: int = 0) -> JsonObject:
        if type(cursor) is not int or not 0 <= cursor <= 99_999_999:
            raise ValueError("invalid_cursor")
        return self._receipt(
            self._exchange("GET", f"{self._runs()}/{_id(key)}?cursor={cursor}")
        )

    def cancel(self, key: Identity) -> JsonObject:
        return self._receipt(
            self._exchange("POST", f"{self._runs()}/{_id(key)}/cancel")
        )

    @staticmethod
    def _receipt(value: JsonObject, *, result: bool = False) -> JsonObject:
        """Fail closed on malformed success bodies from this pinned E1 protocol."""

        def invalid() -> None:
            raise UncertainTurn("invalid_reasoning_receipt; retain the original key")

        expected_keys = {"progress", "result"} if result else {"progress"}
        if not isinstance(value, dict) or value.keys() != expected_keys:
            invalid()
        progress = value["progress"]
        required = {
            "schema_version",
            "run_id",
            "state",
            "cancel_requested",
            "reason",
            "cursor",
            "gap",
            "events",
            "attempts",
            "policy",
            "catalog",
            "strategy",
            "strategy_version",
            "selection",
            "requested_effort",
            "plan_digest",
            "budget_class",
            "effort",
            "phase",
            "outcome",
        }
        if not isinstance(progress, dict) or not required <= progress.keys():
            invalid()
        try:
            if (
                not isinstance(progress["run_id"], str)
                or str(UUID(progress["run_id"])) != progress["run_id"]
            ):
                invalid()
        except (ValueError, TypeError, AttributeError):
            invalid()
        if (
            progress["schema_version"] != "reasoning-run-progress-v1"
            or progress["policy"] != "reasoning-finite-policy-v1"
            or progress["catalog"] != "reasoning-finite-catalog-v1"
            or progress["strategy"] != "direct"
            or progress["strategy_version"] != "direct-verified.v1"
            or progress["selection"]
            not in (
                "simple",
                "typed_slots",
                "effort_ceiling",
                "budget_narrowed",
                "trusted_direct_pin",
            )
            or progress["requested_effort"] not in EFFORTS
            or progress["effort"] != "low"
            or progress["budget_class"] != "bounded_synthetic_bytes"
            or progress["phase"]
            not in ("planning", "answering", "checking", "synthesizing", "terminal")
            or progress["outcome"]
            not in ("pending", "complete", "partial", "unavailable")
            or progress["state"]
            not in ("queued", "running", "succeeded", "failed", "canceled", "uncertain")
            or type(progress["cursor"]) is not int
            or not 0 <= progress["cursor"] <= 99_999_999
            or type(progress["cancel_requested"]) is not bool
            or type(progress["gap"]) is not bool
            or (
                progress["reason"] is not None
                and not isinstance(progress["reason"], str)
            )
            or not isinstance(progress["plan_digest"], str)
            or len(progress["plan_digest"]) != 64
            or any(ch not in "0123456789abcdef" for ch in progress["plan_digest"])
            or not isinstance(progress["events"], list)
            or len(progress["events"]) > 64
            or not isinstance(progress["attempts"], list)
            or len(progress["attempts"]) > 2
        ):
            invalid()
        previous_sequence = 0
        for event in progress["events"]:
            if (
                not isinstance(event, dict)
                or not {"sequence", "kind", "attempt_id"} <= event.keys()
                or type(event["sequence"]) is not int
                or not previous_sequence < event["sequence"] <= progress["cursor"]
                or event["kind"]
                not in (
                    "queued",
                    "claimed",
                    "requeued",
                    "reserved",
                    "dispatched",
                    "step_succeeded",
                    "step_failed",
                    "step_abandoned",
                    "cancel_requested",
                    "succeeded",
                    "failed",
                    "canceled",
                    "uncertain",
                )
            ):
                invalid()
            previous_sequence = event["sequence"]
            if event["attempt_id"] is not None:
                try:
                    UUID(event["attempt_id"])
                except (ValueError, TypeError, AttributeError):
                    invalid()
        state = progress["state"]
        outcome = progress["outcome"]
        if (
            (
                state in ("queued", "running")
                and (outcome != "pending" or progress["phase"] == "terminal")
            )
            or (
                state == "succeeded"
                and (outcome != "complete" or progress["phase"] != "terminal")
            )
            or (
                state in ("failed", "canceled", "uncertain")
                and (
                    outcome not in ("partial", "unavailable")
                    or progress["phase"] != "terminal"
                )
            )
        ):
            invalid()
        seen_steps = []
        for attempt in progress["attempts"]:
            if (
                not isinstance(attempt, dict)
                or not {"attempt_id", "step", "state", "operation_binding", "resources"}
                <= attempt.keys()
            ):
                invalid()
            try:
                UUID(attempt["attempt_id"])
            except (ValueError, TypeError, AttributeError):
                invalid()
            if attempt["step"] not in ("answer", "check") or attempt["state"] not in (
                "reserved",
                "dispatched",
                "succeeded",
                "failed",
                "abandoned",
                "uncertain",
            ):
                invalid()
            seen_steps.append(attempt["step"])
            binding = attempt["operation_binding"]
            expected_tool = (
                "reasoning.inference.v1"
                if attempt["step"] == "answer"
                else "reasoning.verify.v1"
            )
            if (
                not isinstance(binding, dict)
                or binding.get("tool_id") != expected_tool
                or binding.get("effect_class") != "read_only"
                or any(
                    not isinstance(binding.get(name), str)
                    or len(binding[name]) != 64
                    or any(ch not in "0123456789abcdef" for ch in binding[name])
                    for name in (
                        "step_digest",
                        "source_digest",
                        "intent_digest",
                        "plan_digest",
                    )
                )
            ):
                invalid()
            resources = attempt["resources"]
            if (
                not isinstance(resources, dict)
                or resources.get("cost_class") != "synthetic_no_charge"
            ):
                invalid()
            for name, ceiling in (
                ("physical_attempts", 1),
                ("count_calls", 8),
                ("reserved_count_input_bytes", 8192),
                ("observed_count_input_bytes", 8192),
                ("observed_count_calls", 8),
                ("reserved_input_bytes", 1024),
                ("reserved_output_bytes", 128),
                ("input_bytes", 1024),
                ("output_bytes", 128),
                ("verifier_calls", 1),
                ("elapsed_ms", None),
            ):
                item = resources.get(name)
                if item is None and name in (
                    "physical_attempts",
                    "reserved_input_bytes",
                    "reserved_output_bytes",
                    "input_bytes",
                    "output_bytes",
                    "verifier_calls",
                    "elapsed_ms",
                ):
                    continue
                if (
                    type(item) is not int
                    or item < 0
                    or (ceiling is not None and item > ceiling)
                ):
                    invalid()
            if any(
                resources.get(key) is not None
                for key in (
                    "provider_reservations",
                    "provider_settlements",
                    "provider_cost_usd",
                )
            ):
                invalid()
        if seen_steps not in ([], ["answer"], ["answer", "check"]):
            invalid()
        if result:
            pairs = value.get("result")
            if not isinstance(pairs, list) or len(pairs) > 2:
                invalid()
            seen = set()
            for pair in pairs:
                if (
                    not isinstance(pair, list)
                    or len(pair) != 2
                    or type(pair[0]) is not int
                    or pair[0] not in (0, 1)
                    or type(pair[1]) is not int
                    or pair[0] in seen
                ):
                    invalid()
                seen.add(pair[0])
        elif "result" in value:
            invalid()
        return value
