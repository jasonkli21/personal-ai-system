"""Private in-process delivery to one app-bound user runtime."""

from personal_ai.auth.dispatch_grants import ApplicationPlanScope
from personal_ai.llm.chatgpt.responses import PROVIDER
from personal_ai.local_bridge.runtime import BridgeDenied
from personal_ai.storage.async_io import sync_call


class PairedApplicationRuntime:
    """The caller session and provider credentials remain on the runtime side."""

    def __init__(self, bridge, session):
        if not isinstance(bridge.installation.scope, ApplicationPlanScope):
            raise BridgeDenied("bridge_admission_denied")
        self._bridge, self._session = bridge, session

    async def deliver(self, proof, profile, release):
        bridge, session = self._bridge, self._session
        caller = {"origin": session.origin, "authorization": session.authorization}

        def authorized_release():
            bridge.authorize_handoff(proof, profile, **caller)
            return release()

        await sync_call(bridge.authorize_handoff, proof, profile, **caller)
        if proof.claims.model_id not in {model.slug for model in await bridge.models(**caller)}:
            raise BridgeDenied("bridge_model_unavailable")
        package = await sync_call(authorized_release)
        stream = bridge.execute(package, proof, **caller)
        try:
            async for event in stream:
                if event.kind == "terminal" and event.metadata.status == "success":
                    receipt = await bridge.reconcile(
                        package.dispatch_identity,
                        package.fingerprint,
                        **caller,
                    )
                    if receipt.status != "success" or (
                        event.metadata.identity.provider_id,
                        event.metadata.identity.model_id,
                        event.metadata.identity.serializer_id,
                    ) != (PROVIDER, package.model_id, profile.serializer_id):
                        raise BridgeDenied("bridge_completion_invalid")
                yield event
        finally:
            await stream.aclose()
