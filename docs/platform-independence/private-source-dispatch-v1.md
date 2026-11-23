# Private synthetic source dispatch

The isolated test host can explicitly install `pas-dispatch/1` for a registered Travel or Health target. It uses the shared token-budgeted context assembler, direct PAS human and client authorization, the paired local runtime and a receiving loopback fixture. The normal API, standalone bridge and ordinary bound-preview profile keep their existing behavior. The public consumer contract and installed SDK versions are unchanged.

The composition supplies the original receipt attestor, a verified create-receipt lookup, the original preview receipt expiry verifier, keyed source and memory projection commitments, and a registered in-process current-source callback. It also supplies current PAS dependency evidence for recovery, distinct preview, release and terminal key roles, and an independent continuity check. The composition must invalidate cached execution on logout and report uncertain store continuity before admission.

| Operation | Private negotiation |
| --- | --- |
| Create | Use the original private create route and receipt media and preserve the exact signed artifact. |
| Preview | POST to the existing private `context-preview` route with `Content-Type: application/vnd.pas.dispatch-v1+json` and the canonical preview intent. The response carries the original metadata and `X-Application-Plan-Receipt` alongside a separate canonical `X-PAS-Dispatch-Receipt` envelope with `claims` and `signature`. |
| Confirm | POST the frozen canonical confirmation document to the existing private `continue` route with the same vendor media type. Acknowledgment is an empty 202. |
| Status | GET `/v1/conversations/{conversation}/continuations/{original_key}` with the vendor media type in `Accept`. The body carries the original attempt and signed terminal after canonical commit. |
| Detail | GET `/v1/conversations/{conversation}` with the vendor media type in `Accept` and the previously verified original UUID in `X-PAS-Original-Key`. The response contains only the matched result. |

The prepared provider bytes expire at the earliest signed authority expiry or cache limit. Releasing a prepared buffer requires a committed PAS root, current recipient authority and the paired runtime's retained send-start fences. The fixture sends one numeric-loopback HTTP POST using the prepared bytes and validates the receiving fixture's signed, zero-usage response before signing a terminal. Confirmation never returns model output. After an ambiguous POST, use GET with the same original key. A completed GET carries `X-PAS-Committed-At` with the PAS journal commit time in Unix seconds. PAS checks the archived terminal at that time and checks current authority again before disclosure.

The Step 2 composition uses a private SQLite journal for canonical dispatch status and result. Native PAS conversation, message and consent storage, independent backup and restore, and same-process source-write ordering across the final socket boundary still require evidence. Deployed identity, providers, accounts and billing remain outside the synthetic profile.

Application callbacks receive canonical binding bytes, a phase and a fresh nonce. Each application resolves its private scope from its own records. Travel and Health require an unexpired terminal for outward disclosure. The commit-time response header alone cannot extend this deadline. Paired integration remains pending.
