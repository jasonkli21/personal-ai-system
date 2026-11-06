"""Opt-in source-free fixture operations on the isolated loopback protocol."""

from urllib.parse import urlsplit

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
        return self._receipt(self._exchange("POST", self._runs(), body))

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
    def _receipt(value: JsonObject) -> JsonObject:
        progress = value.get("progress")
        if (
            not isinstance(progress, dict)
            or progress.get("schema_version") != "reasoning-run-progress-v1"
            or progress.get("state")
            not in ("queued", "running", "succeeded", "failed", "canceled", "uncertain")
            or type(progress.get("cursor")) is not int
        ):
            raise UncertainTurn("invalid_reasoning_receipt; retain the original key")
        return value
