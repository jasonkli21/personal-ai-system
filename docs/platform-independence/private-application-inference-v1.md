# Private application inference profile v1

The isolated synthetic host supports two private POST operations for a user-confirmed app inference turn. Install `personal-ai-sdk==0.2.0` and explicitly construct `ApplicationPlan(client)`. The host installs the adapter at construction using the existing application-plan service, context assembler and recipient authorities. The ordinary API and standalone bridge omit these routes. The external consumer contract remains version 1.2.0. [Private schema and wire samples](private-application-inference-v1.schema.json) · [External consumer contract](consumer-v1.md)

| Operation | Route and caller input |
| --- | --- |
| Create | `POST /v1/conversations` with the caller's original create UUID and title |
| Preview | `POST /private/application-plan/v1/conversations/{id}/context-preview` with content, original continuation UUID and `choice.mode=user_owned_plan` |
| Continue | `POST /private/application-plan/v1/conversations/{id}/continue` with the original preview intent and its exact `choice.confirmation` |
| Status | `GET /v1/conversations/{id}/continuations/{key}` with the original conversation ID and continuation UUID |
| Detail | `GET /v1/conversations/{id}` with the original conversation ID |

The versioned path selects the request shape. A profile version that the SDK cannot interpret raises `CapabilityUnavailable`. HTTP absence on the selected path also fails closed. The old fixture header carries no authority or selection effect. Private requests use a direct user bearer ID token, JSON content type and the operator-bound application and applicable workspace headers. PAS resolves the human using verified issuer and subject and checks the exact audience, effective authorized party, client registration and current workspace membership before protected reads. The source service separately checks membership and current revisions. [Application and source authority](../context-inference-integration/user-owned-application-inference.md)

Preview emits bounded destination, purpose, projected fields and categories, selected history count, an estimated input size, and an expiring confirmation. The exact assembly stays in PAS until confirmation. Continue uses the existing SSE event types and one guarded attempt. The SDK reports completion after a matching terminal, clean stream exhaustion and an agreeing original-key status. Deltas are provisional. Ambiguous requests keep their original key. Later revocation can withhold subsequent output and replay, while bytes already observed by an authorized recipient cannot be recalled.

## Install and recover

From a prepared checkout, run `UV_OFFLINE=1 make sdk-build` and install the locally built wheel into the caller's own environment. Keep the private profile bound to the operator-provided synthetic host. The client accepts HTTPS and supports explicit numeric HTTP loopback for the disposable fixture. It ignores ambient proxies and refuses redirects. [SDK setup](../../sdk/python/README.md)

The caller owns the durable journal. Store it in private application storage with bounded retention, and keep credentials in their normal secret store. Persist each intent before its POST. The following example uses an existing owner-only directory and an app-supplied synthetic identity and scope. The host retains canonical state and reauthorizes stored content separately.

```python
import json
import os
import tempfile
from pathlib import Path
from uuid import uuid4

from personal_ai_sdk import ApplicationPlan, Client, PlanPreviewRequest, UncertainTurn


def persist(path: Path, record: dict) -> None:
    fd, candidate = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(record, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(candidate, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(candidate).unlink(missing_ok=True)


def preview_intent(path, client, binding, content):
    journal = {"binding": binding, "title": "Reading discussion", "create_key": str(uuid4())}
    persist(path, journal)
    conversation = client.create(journal["title"], journal["create_key"])
    intent: PlanPreviewRequest = {
        "idempotency_key": str(uuid4()),
        "content": content,
        "choice": {"mode": "user_owned_plan"},
    }
    journal.update(conversation_id=conversation["id"], preview_intent=intent)
    persist(path, journal)
    journal["preview"] = ApplicationPlan(client).preview(conversation["id"], intent)
    persist(path, journal)
    return journal


def continue_after_explicit_approval(path, client, journal):
    request = journal["preview_intent"] | {
        "choice": {"mode": "user_owned_plan", "confirmation": journal["preview"]["confirmation"]},
    }
    journal["continuation"] = request
    persist(path, journal)
    try:
        return ApplicationPlan(client).continue_turn(journal["conversation_id"], request)
    except UncertainTurn:
        return None  # Preserve the original for GET reconciliation.


def recover(path, client: Client, verified_binding, *, recover_create=False):
    journal = json.loads(path.read_text(encoding="utf-8"))
    if journal["binding"] != verified_binding:
        raise ValueError("The original user, client and workspace binding is required.")
    if "conversation_id" not in journal and recover_create:
        # Explicit recovery of an ambiguous create, with the exact original inputs.
        conversation = client.create(journal["title"], journal["create_key"])
        journal["conversation_id"] = conversation["id"]
        persist(path, journal)
        return conversation
    if "continuation" not in journal:
        return None
    cid = journal["conversation_id"]
    observation = client.status(cid, journal["continuation"]["idempotency_key"])
    if observation["state"] != "completed":
        return None
    detail = client.detail(cid)
    return next(
        (
            message for message in detail["messages"]
            if message["id"] == observation["message_id"]
            and message["role"] == "assistant"
            and message["status"] == "completed"
        ),
        None,
    )
```

Bind the journal to the exact target URL, application, workspace, expected verified human and client. Reauthenticate to that binding before recovery. Handle current-authority denial or an absent active-branch message by withholding content. A missing or uncertain continuation observation preserves its fence and requires GET-only reconciliation. For another inference, start with a new informed user decision.

Rollback disables the private composition. Retain unknown receipts, routing roots, recovery witnesses, revocation epochs and caller journals.
