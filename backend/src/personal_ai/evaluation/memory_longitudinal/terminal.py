"""Independent, bounded read-back for the hermetic Task B target."""

from threading import RLock

from personal_ai.memory.research.experiments.contracts import Digest, Identity, Record, digest


def task_b_target_id(task_id: str) -> str:
    return "task-b-" + digest([task_id, "target-v2"])[:24]


def task_b_intent(task_id: str) -> str:
    return digest([task_id, "original-intent-v2"])


def initial_state_sha256(task_id: str, target_id: str, intent: str) -> str:
    return digest(
        {
            "task_id": task_id,
            "target_id": target_id,
            "intent": intent,
            "version": 0,
            "action": None,
            "effect_id": None,
        }
    )


def changed_state_sha256(
    task_id: str, target_id: str, intent: str, action: str, effect_id: str
) -> str:
    return digest(
        {
            "task_id": task_id,
            "target_id": target_id,
            "intent": intent,
            "version": 1,
            "action": action,
            "effect_id": effect_id,
        }
    )


class TerminalReadback(Record):
    task_id: Identity
    target_id: Identity
    original_intent: Digest
    before_version: int
    before_state_sha256: Digest
    state_version: int
    state_sha256: Digest
    action: Identity | None
    effect_id: Digest | None
    effect_count: int
    effect_authorized: bool | None


class TaskBState:
    """Separate material state from the policy's command/receipt response.

    This is a synthetic single-target host. It is deliberately not an application
    repository or a production effect executor.
    """

    __slots__ = ("__before", "__effect", "__intent", "__lock", "__target_id", "__task_id")

    def __init__(self, task_id: str):
        self.__task_id = task_id
        self.__target_id = task_b_target_id(task_id)
        self.__intent = task_b_intent(task_id)
        self.__before = initial_state_sha256(task_id, self.__target_id, self.__intent)
        self.__lock = RLock()
        self.__effect = None

    @property
    def target_id(self):
        return self.__target_id

    @property
    def intent(self):
        return self.__intent

    def apply(self, intent: str, action: str, expected_version: int, authorize):
        with self.__lock:
            if intent != self.__intent:
                raise ValueError("task_b_intent_mismatch")
            if not authorize():
                raise PermissionError("task_b_authority_denied")
            effect_id = digest([self.__task_id, self.__target_id, intent, action])
            if self.__effect is not None:
                if self.__effect != (action, effect_id, True):
                    raise ValueError("task_b_duplicate_effect_conflict")
                return effect_id
            if expected_version != 0:
                raise ValueError("task_b_stale_revision")
            self.__effect = (action, effect_id, True)
            return effect_id

    def read_back(self, task_id: str, target_id: str, intent: str) -> TerminalReadback:
        with self.__lock:
            if (task_id, target_id, intent) != (self.__task_id, self.__target_id, self.__intent):
                raise ValueError("task_b_readback_identity_mismatch")
            action, effect_id, authorized = self.__effect or (None, None, None)
            version = 1 if effect_id else 0
            state_hash = (
                changed_state_sha256(task_id, target_id, intent, action, effect_id)
                if effect_id
                else self.__before
            )
            return TerminalReadback(
                task_id=task_id,
                target_id=target_id,
                original_intent=intent,
                before_version=0,
                before_state_sha256=self.__before,
                state_version=version,
                state_sha256=state_hash,
                action=action,
                effect_id=effect_id,
                effect_count=int(effect_id is not None),
                effect_authorized=authorized,
            )
