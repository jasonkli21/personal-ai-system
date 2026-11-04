# Personal AI SDK for Python

Provisional `personal-ai-sdk==0.1.0` supports Python 3.11+ with no runtime
dependencies and the external [consumer contract v1.2.0](../../docs/platform-independence/consumer-v1.md).
Use an operator-confirmed v1.2 or later v1 release. The constructor checks that
configured version locally. The host contract version is independent. HTTPS is
required except for explicitly opted-in numeric loopback test endpoints.
Timeouts bound socket waits, and the client caps request, response, event and
stream sizes. It disables redirects and ambient proxy configuration.

Use `UV_OFFLINE=1 make sdk-install-check` from the repository root with the
prepared backend build environment. The wheel is independently installable.
The sdist uses the pinned build backend in `pyproject.toml`.

```python
import os
from uuid import uuid4

from personal_ai_sdk import Client, Continuation, UncertainTurn

client = Client(
    "https://consumer.example.invalid",
    os.environ["CHECKLIST_USER_ID_TOKEN"],
    application="project_checklist",
    workspace="demo",
)
create_key = uuid4()  # Persist the key and title in your journal before create.
conversation = client.create("Walkthrough", create_key)
body: Continuation = {
    "content": "Draft a checklist from this explicitly shared instruction.",
    "idempotency_key": str(uuid4()),
    "choice": {"mode": "automatic"},
}
# Commit conversation ID, target scope and the entire body before sending.
client.preview(conversation["id"], body)
try:
    completed = client.continue_turn(conversation["id"], body)
except UncertainTurn:
    observation = client.status(conversation["id"], body["idempotency_key"])
```

On restart, use the same authenticated target and read status by original key.
A completed observation permits an explicit replay of the original body under
current source rights. In-progress, unknown and not-found are observations.
Preserve the journal and resolve uncertainty before creating a new intent.
A changed body for an existing key conflicts. The SDK performs no automatic
POST retries. Deltas are provisional. Completion requires a matching terminal
event, normal stream exhaustion and canonical status. Disconnect leaves the
server outcome uncertain. The protocol provides status lookup in place of
Last-Event-ID resumption.

Use `APIError.status` and the safe `APIError.code` to distinguish HTTP denials,
conflicts, throttling and service availability. `UncertainTurn` identifies an
incomplete transport or stream observation. `ContractMismatch` identifies an
unsupported configured version. Retrieval calls require explicit configuration
and operator-granted rights. Unconfigured retrieval raises
`CapabilityUnavailable`. Service denials preserve the public API's status and
safe code. The SDK accepts caller-supplied ID tokens and has no token issuer,
admin, memory control or general tool API. Diagnostics omit endpoint, token,
scope values, request and response content.

For a no-example unrelated consumer and operator-pinned native installation, use
the [release operator guide](../../docs/harness-excellence/release-operator-guide.md).
`make release-build-report` compares two committed SDK builds without downloading
build dependencies. Input authenticity and transitive build-tool licensing need
independent pins/review. `make release-profile-check` includes wheel tamper,
startup-hook, source-import and source-free synthetic protocol negatives. Native
install and signed installed server proof remain separate gates; these commands
do not promote the provisional contract or enable a capability.
