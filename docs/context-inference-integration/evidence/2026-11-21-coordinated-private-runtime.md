# Coordinated private runtime fixture

**2026-11-21 · R3-A offline fixture implemented · Independent acceptance pending**

The maintainer authorized the fixture-only design escalation after the ordering diagnostic on `c96fce21ef7f31aa51cf37b709b1a347c1513351`. The implementation is the single direct child of `cfc4d7430e53a401e31327231dbb4e0fd0341ede` introducing this report. Earlier pending approvals were waived for implementation entry. They retain their prior acceptance status. [Ordering counterexample and prior ledger](2026-11-21-private-runtime-ordering.md)

## Design and threat boundary

Revocation and send-start previously used different locks. A source owner could revoke the model-recipient grant after PAS approved the send while the runtime could still commit its local fence and send the source data. TLS authenticates transport peers and protects the bytes in transit. Serialization of the mutation and the durable fence protects the authority decision.

The test launcher preconfigures one application target, one runtime process and a numeric IPv4 loopback endpoint. The independently started runtime initializes the local registration and fake credentials, reports its public binding and opaque caller identifier over its launcher pipe, and connects after the launcher supplies the start signal. The PAS signer stays with PAS. Generated TLS identities require TLS 1.3 and certificate verification in both directions, then exact DER certificate pinning. Key files use mode `0600` and are unlinked after loading and at teardown. The synthetic processes share an OS user and the test directory, so the fixture assumes launcher custody. It exposes no public route or enrollment endpoint. [Process fixture](../../../backend/tests/app_context_support/process_delivery.py) · [Plan composition](../../../backend/src/personal_ai/services/external_turns/application_plan.py)

The ownership and storage inventory in the earlier report still applies. The new transport deliberately composes the coordinated synthetic stores, with in-memory PAS preview, root, source, conversation and memory, and a separate POSIX runtime store. Fixture client-policy, source, membership, grant, owner and memory writers enter the shared authority lock. Direct synthetic authority changes use the same mutation context. The process fixture rejects unrelated HTTP mutation routes and admits one continuation writer at a time for the full ASGI response. Canonical create can add a conversation and cannot revise the current branch. Local registration changes remain serialized by `ProtectedLocalStore`. The native tests compose PostgreSQL routing and principal adapters separately and do not add uncoordinated native writers to the TLS fixture.

- **Release.** PAS claims the original turn and sends only a signed v2 proof and profile. The runtime checks handoff, model catalog and handoff again. PAS receives ready and takes the authority lock, uses the original request's release closure, and holds the lock through the runtime's acknowledgment of the original bounded package and both signed digests. Release changes that acquire the lock first prevent any plaintext delivery.
- **Send-start.** The bridge holds the local pre-send claim, then acquires the shared POSIX authority lock before entering `runtime.lock`. Inside `mark_send_started`, the existing callback asks PAS, which services the inquiry in the live generation context, to revalidate exact attempt and current rights. PAS reads authority without taking the runtime-held lock. The guard holds the shared lock through exclusive fence creation, file and directory fsync, and mutable receipt persistence. It then checks live PAS authority again before unlocking and permitting dispatch. A completed revocation must precede the decision or wait until the fence is durable.
- **Expiry and process loss.** A current wall-clock deadline is checked immediately before the fence and again after persistence. Expiry during persistence conservatively consumes the fence without dispatch. Socket calls have finite deadlines. A timeout on the PAS side closes the channel. The runtime owns its lock until the guarded operation exits or the kernel releases it on death, so PAS timeout cannot silently transfer exclusion to a writer. A process loss before authorization prevents send-start. Loss after fence creation leaves the attempt consumed and unavailable for replay. A failed or ambiguous transition retains the original key, including a possible fence with no settled receipt. Local disk fsync is a real syscall and its OS latency is outside the transport deadline guarantee.
- **Completion.** PAS verifies one matching reconciled terminal followed by TLS close-notify and revalidates current rights before returning it. Deltas are provisional. Replay and status/detail use the original canonical identity and current authority. Provider mock POST counts are independent of application status and runtime package counts.

The fixture accepts one attached channel and one confirmed transport attempt. Limits are 2 seconds for TLS handshake, frame, lock acquisition and injected barrier waits; 45 seconds idle awaiting the first offer byte; 5 seconds for channel activity after the offer starts; 8,192 bytes per frame before decoding; 65,536 aggregate frame bytes including headers; 512 frames per direction; one active continuation and backlog one. Provider output is bounded by the original package's 100-byte and 100-character ceiling. Teardown closes the channel, waits one second and kills a stalled synthetic process if needed. It never starts or connects a replacement automatically.

## Result ledger

The prior ledger's acceptance conditions still apply. Local observations below were reproduced by the implementer. E1 requires independent review and E3 remains `NO_GO`. Node names refer to [process delivery cases](../../../backend/tests/test_application_plan_process_delivery.py) unless specified. The result SHA is obtained with `git log -1 --diff-filter=A --format=%H -- docs/context-inference-integration/evidence/2026-11-21-coordinated-private-runtime.md`.

| ID | Result and tier | Observation and limits |
| --- | --- | --- |
| R3-01 | REVIEW_REQUIRED · Git | Prior pinned ancestry and waiver recorded. The design escalation and its limited composition are explicit above. |
| R3-02 | REVIEW_REQUIRED · inspection | PAS owns all release authority, runtime owns credential and fence state, and the caller owns its journal. Only enumerated participants join the fixture. |
| R3-03 | REVIEW_REQUIRED · synthetic | The existing private HTTP fixture opts into the test-only process seam. Normal startup stays outside it. |
| R3-04 | REVIEW_REQUIRED · synthetic | Separate process IDs, strict TLS 1.3 and both substitution directions verified. Kernel packet capture observes TLS records, with a positive plaintext control. Runtime counts decrypted package bytes separately. |
| R3-05 | REVIEW_REQUIRED · synthetic | Trusted launcher binds scope and opaque runtime/session facts before TLS. Runtime reconciles exact local account and registration. Existing scoped binding tests remain relevant. |
| R3-06 | REVIEW_REQUIRED · synthetic | One accepted connection, monotonic frame sequence and one delivery. Competing continue, invalid proof and wire out-of-order cases deny. Runtime/installation rotation requires a new fixture. |
| R3-07 | REVIEW_REQUIRED · synthetic | Runtime has completed TLS before preview and sees zero package bytes or POSTs until confirmation. |
| R3-08 | REVIEW_REQUIRED · synthetic | Existing release callback executes once after exact confirmation and claim. Positive case observes one package and one fake POST. |
| R3-09 | REVIEW_REQUIRED · synthetic | V2, package fingerprint, provider payload digest and profile checked before package acknowledgment. Invalid signature and frame-order cases exercised. |
| R3-10 | REVIEW_REQUIRED · synthetic | Revoke, forget and owner deletion before ready produce zero runtime package bytes and zero mock POSTs. Existing in-process tests cover source revisions, memberships and related rights. |
| R3-11 | REVIEW_REQUIRED · synthetic and POSIX | Actual local-lock callback asks live PAS. Kernel contention is observed in the post-decision barrier. Stalled and channel-loss cases deny dispatch. Expiry checks are inspected; a clock crossing inside fsync was not forced. |
| R3-12 | REVIEW_REQUIRED · synthetic | Completed revoke before decision yields one released package and zero fences/POSTs. The post-decision contender cannot commit before the fence. An already durable fence stays consumed after revoke. |
| R3-13 | REVIEW_REQUIRED · inspection and synthetic | Runtime creates and uses fake provider credentials and its bridge authorization locally. The pipe has public binding/facts and no bearer tokens; trace records labels and byte counts. |
| R3-14 | REVIEW_REQUIRED · inspection and synthetic | Existing bridge creates the only send fence and receipt. Kill after fence proves it persists before settlement. |
| R3-15 | REVIEW_REQUIRED · synthetic | Competing caller cannot attach, one runtime per fixture and one mock POST. Existing baseline races cover shared local fence workers. |
| R3-16 | REVIEW_REQUIRED · synthetic | 429, truncated provider stream, duplicate terminal, post-fence kill and channel loss retain uncertainty without another physical mock POST. |
| R3-17 | REVIEW_REQUIRED · synthetic | Original-key canonical status and active detail agree. Failed exchanges remain unknown. Installed HTTP tests separately exercise the fsynced caller journal and lost continue. |
| R3-18 | REVIEW_REQUIRED · synthetic | Sequence, kind and encoded-size validation; duplicate terminal rejected during EOF check; only matching reconciled success survives. |
| R3-19 | REVIEW_REQUIRED · synthetic | Revoked source suppresses subsequent success; current checks gate stream events and replay. Full interprocess per-delta revocation timing remains unobserved. |
| R3-20 | REVIEW_REQUIRED · synthetic | Deadline and disconnect checks fail closed, fence survives connection loss. Existing bridge account/session revision cases cover local changes. |
| R3-21 | PASS_E2_SCOPED_NATIVE · PostgreSQL routing/principal · independent review pending | Four native cases exercise root restores, per-claim witness agreement, distinct claim processes, process death before and after the independent write, and stale root/witness agreement under a retained independent checkpoint. Provider I/O remains synthetic. |
| R3-22 | REVIEW_REQUIRED · POSIX and synthetic | Runtime kills before and after the fence, and channel loss after fence, produce no second POST. Native PAS claim-worker death verified separately. Full PAS/runtime restart with restored files remains unobserved. |
| R3-23 | NOT_RUN · E2 · named omissions | DynamoDB conversation, message and branch; native domain/source and installation; native memory/consent/lifecycle adapters; and separate caller journal restore were not exercised. The PostgreSQL tests still use in-memory conversation and source/memory fixture stores. |
| R3-24 | REVIEW_REQUIRED · diff | No migrations or persisted schema changes. File restore and retention obligations remain scoped to their actual existing owners. |
| R3-25 | REVIEW_REQUIRED · synthetic | Frame boundary and boundary plus one, sequence, contention, and stalled fence deadline exercised. Total-stream and frame-count maxima are implemented and inspected. |
| R3-26 | REVIEW_REQUIRED · synthetic | Existing installed client and foreign owner/app/workspace cases remain in scope. Both substituted transport identities and invalid signed proof deny release. No provider is contacted. |
| R3-27 | REVIEW_REQUIRED · synthetic | Linux loopback-only network namespace, independent packet capture and DNS denial control. Network audit reports zero unexpected operations. |
| R3-28 | REVIEW_REQUIRED · compatibility | Installed 0.2.0 wheel and rebuilt sdist, 0.1.0 legacy automatic path, direct consumer contract and existing foreground cases. Inherited Make failures below. |
| R3-29 | REVIEW_REQUIRED · diff | No service enablement, deployment, daemon, provider calls or product claims. |
| R3-30 | REVIEW_REQUIRED · execution logs | Recorded commands, exits and baseline comparison below. |
| R3-31 | BLOCKED_EXTERNAL · provider and product eligibility | Existing mode-specific blockers and R4, Health, and R7 ownership apply. No provider readiness matrix was implemented. |
| R3-32 | REVIEW_REQUIRED · fixture teardown | Disable by omitting the fixture. Close and drain the channel and retain any durable fence, roots, witnesses, unknown receipts and original caller keys. |

## Reproduction and checks

Run in the locked backend environment. The TLS cases require Linux, POSIX flock, `CAP_NET_RAW` in the isolated user/network namespace for the packet observer, and numeric loopback. Python 3.12.14, Linux 6.18.57 on overlayfs and OpenSSL 3.5.7 were used. The signed HTTP test runner counts unexpected network operations. The child process separately audits its endpoint and DNS calls. The packet observer reads packets from the kernel and first verifies capture of known plaintext on a separate loopback connection. It emits no packet bytes. Provable containment comes from the namespace, whose only interface is loopback.

```sh
env -i PATH="$PATH" LITELLM_LOCAL_MODEL_COST_MAP=True PRIVATE_PROCESS_DELIVERY_TEST=1 \
  unshare -Urn bash -c '
    ip link set lo up &&
    scratch=$(mktemp -d /var/tmp/pas-process.XXXXXX) &&
    backend/.venv/bin/python -B backend/scripts/signed_http_checks.py -q -rA \
      --basetemp "$scratch/test" backend/tests/test_application_plan_process_delivery.py'
```

The PostgreSQL adapter was exercised with the repository's disposable pgvector 0.8.1 image pinned to PostgreSQL 17.8, published only on numeric IPv4 loopback with temporary data, then removed. Set the disposable `PERSISTENCE_TEST_POSTGRES_DSN` and use the signed test runner with `-q -rA --basetemp "$scratch/native" backend/tests/persistence/test_application_plan_postgres.py`. The nodes were `test_native_ambiguous_plan_fence_and_owner_deletion_survive_restore_boundary`, `test_worker_loss_after_native_claim_preserves_original_key_and_prevents_resend[after-witness]`, the same with `[before-witness]`, and `test_concurrent_native_claim_witnesses_survive_restore`. The before-witness child exits after the database transaction commits and before the independent callback writes. The stale-pair case keeps the live owner/claim evidence outside both stale copies. A matching stale pair alone cannot establish freshness.

| Check | Exit | Observation |
| --- | --- | --- |
| Coordinated loopback suite | 0 | 21 passed. Zero unexpected network attempts. |
| Disposable PostgreSQL suite | 0 | Four passed. Zero unexpected Python network attempts. |
| `make backend-lint` and `git diff --check` | 0 each | Passed. |
| `make sdk-install-check` | 0 | Client-only install passed for wheel and rebuilt sdist. |
| Installed private-profile HTTP suites | 0 each | Six passed per 0.2.0 artifact, one automatic 0.1.0 control passed, and one intentional DNS denial passed separately. Same nodes and invocation as prior review. |
| `backend/.venv/bin/python backend/scripts/consumer_contract_check.py --check` | 0 | Consumer 1.2.0 schema check passed. |
| `make naming-policy-check` | 2 | Same two R0 handoff references as baseline. |
| `make source-contract-check` | 2 | Existing planning and offline information-handling drift, with new private application plan source identity to review. |
| `make consumer-contract-check` | 2 | Existing portable planning source identity gate stops the target before its subsequent contract and artifact steps. |
| `make hermetic-capability-check` | 2 | Existing grounded sealed evaluation failure. |
| Broad offline selection from prior report | 1 | 542 passed. The same three baseline tests failed: two future-issued rooted grants and one permissions case under the executor umask. |

The paid-accounting gate remains the production composition's missing charge-receipt authority. Existing provider, source-owner and deployment approvals remain with their owners. A future live design would require a serialization and independent recovery proof over every live writer, including stores that cannot join the fixture's POSIX lock. [Eligibility and custody matrix](../runtime-r0/R0-eligibility-matrix.md) · [Baseline commands and results](2026-11-21-private-runtime-ordering.md)
