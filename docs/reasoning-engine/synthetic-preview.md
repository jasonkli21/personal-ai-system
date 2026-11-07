# Synthetic reasoning preview v1

The standalone IPv4 loopback preview is an opt-in development process. It
accepts one operator-issued bearer credential for the fixed synthetic
`personal_ai` app and its default scope. The deployed API has no preview
routes. The profile uses canonical workflow, chat continuation and context
assembly with the installed offline fake. Its two closed tasks are
`sum` (1 + 2) and `pair` (1 + 2, 2 × 3). The second fixture deliberately
produces only one verified slot. The request grammar has no prompt,
provider, source, workspace, executable step or tool selector. The [ownership
decision](../decisions/0030-synthetic-reasoning-preview.md) defines the boundary.

## Launch and disable

Use a dedicated local process with a freshly generated private credential.
Keep the token in the calling shell and pass it to the consumer out of band.

```sh
export SYNTHETIC_REASONING_TOKEN="$(backend/.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
backend/.venv/bin/python -m personal_ai.api.synthetic_reasoning &
preview_pid=$!
```

The listener is `http://127.0.0.1:8766` with one worker, proxy headers and
access logging disabled. Run it directly on loopback without a reverse proxy.
Disable new original keys with `kill -USR1 "$preview_pid"`. The capability
then reports `disabled` for the same epoch. Admitted work keeps its pinned
plan and can finish or be canceled. Status and exact replays remain available.
Disable is one-way for the lifetime of the process. Stopping or replacing the
process discards its in-memory rows and changes the epoch. Rotate the token
on replacement and reconcile old observations as unknown. Separately, use the
[adaptive rollback command](adaptive-selection.md#local-operator-control)
to disable shadow recommendations and retain fixed V1 execution.

## Wire contract

Every operation requires the bearer credential and
`X-Application-ID: personal_ai`. The preview rejects a workspace override,
an Origin header or a non-loopback peer. The SDK disables redirects and
environment proxies. All paths below are under `/v1/synthetic-reasoning`.

| Method and path | Behavior |
| --- | --- |
| `GET /capability` | Advertises `reasoning.workflow.synthetic.v1`, launch epoch, default-off E1 development posture, closed tasks, efforts, fixed strategy and exact ceilings. |
| `POST /{epoch}/runs` | Accepts JSON with `capability`, UUID `original_key`, `task`, optional `effort` and optional `limits` reductions. Runs synchronously and returns `progress` and live verified `result` slot/value pairs. Exact original replay returns metadata and an empty result. Changed canonical intent returns 409. |
| `GET /{epoch}/runs/{original_key}?cursor=0` | Returns `progress` only. Use the last sequence as the next cursor. A cursor beyond the current sequence returns 422. A gap flag accompanies an available snapshot if older events fell outside retention. |
| `POST /{epoch}/runs/{original_key}/cancel` | Returns `progress` only. Queued or reserved work is canceled. A dispatched generation without a committed observation is uncertain. A terminal receipt is returned as-is. |

The response reuses the redacted `reasoning-run-progress-v1` envelope with
state, outcome, stop reason, effort, strategy, plan digest, ordered events and
per-attempt resources. Unknown physical work remains null. Output is returned
only on the initial authorized live response. Polling, cancellation and replay
carry no result text. An interrupted response leaves the outcome unknown to the
consumer. Poll with the original epoch and key. A 409
`reasoning_epoch_changed` means that process can no longer reconcile the run.
Keep the original journal and surface uncertainty. The SDK performs one POST
per explicit call and does not automatically retry.

The request may specify `auto`, `low`, `medium`, `high` or `max`. Effective
effort is always `low` and the strategy is `direct-verified.v1`. Omitted limits
inherit the advertised ceiling. Operator, app, workspace, user, endpoint and
request ceilings intersect through the finite compiler. Per run the upper
bounds are one generation, one verifier, eight counts, 8,192 count-input bytes,
1,024 generation-input bytes, 128 output and result bytes each, six seconds
and concurrency one. Nominal step time is two seconds. External-source and
real-provider work are unavailable. Unknown fields, duplicate JSON keys and
unsupported capability versions are rejected. Submit accepts at most 2,048
bytes and two seconds to upload. The SDK caps successful JSON responses at
32 KiB with an eight-second socket timeout.

The process accepts one foreground submission at a time across its sole
scope. It rejects contention immediately with 429 `reasoning_busy` and has
no application queue. Status and cancellation can proceed during execution.
The 64-original lifetime limit preserves reconciliation without eviction and
rejects new keys with `reasoning_capacity`. This topology offers bounded
backpressure with no scheduling or fairness guarantee across credentials or
replicas. PostgreSQL recovery evidence covers the canonical lifecycle in
separate internal-host tests.

## Checks

`make synthetic-reasoning-check` exercises HTTP scope, bounds, cancellation
and disablement. `make synthetic-reasoning-install-check` builds the SDK and
the independent fixture auditor, installs only their wheels in a clean
environment, and runs against a disposable numeric-loopback server. The
[current state](../current-state.md) records the profile and release
dispositions.
