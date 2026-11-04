# Independent consolidation evaluation plan

Status: **design only**. The current v1/v2 corpora and the additive challenge
manifest are synthetic, author-visible regression inputs. None is an independent
holdout, natural-language utility result, or production acceptance evidence.

## Freeze before any trial

An evaluator who did not implement the consolidation code must recruit a separate
task writer and freeze a new additive manifest before model execution. Keep the
writer's labels and expected answers hidden from the implementer and model runner
until scoring is complete. Pin the source corpus, task manifest, code revision,
model/build, prompt, context assembler, scoring rules, and analysis script by digest.
Do not modify or rebind the existing v1/v2 hashes, prior receipts, scoring rules,
or the planning v35 lock.

The task set must cover multi-session task transfer, exact and unsupported facts,
poisoned claims, natural-language ambiguity, scope collisions, user corrections,
source withdrawal/regrant, expiry, and exact source attribution. Include tasks the
current fixed-memory schema cannot represent; report those as an unsupported
denominator for that comparator instead of dropping them from the study.

## Matched arms and attempt handling

For each eligible task family, compare:

1. No consolidation.
2. Current canonical fixed-memory retrieval, where the task type is representable.
3. Deterministic pending consolidation context.
4. Full eligible source context under the same source and permission rules.
5. Optional model-assisted extraction, only if separately admitted and preregistered.

Every supported arm must use the same pinned model/build, device, source grants,
context assembler, system instructions, token ceilings, output ceiling and deadline.
The eligible-source arm must contain exactly the authorized source revisions for
the task. Record the source IDs and fingerprints used by each arm. An unsupported
arm is recorded with its reason and does not become an abstention or a failed model
attempt.

Retain every attempt, including dispatch failures, timeouts, refusals, denials,
unknown outcomes, retries and safety failures. Do not rerun a failed row under a new
intent or omit it from the denominator. Separate observed effects (physical calls,
tokens, token confidence, latency, cost class and source attribution) from rubric
results (task success, unsupported answer, false support, conflict handling and
scope leakage). Use paired task-level comparisons and report confidence intervals,
variance and every arm denominator. Do not infer provider cost from tokens; local
no-charge and hosted cost are distinct measured fields.

## Safety and acceptance boundary

Run only after the trusted producer, current grant/withdrawal authority and
canonical owner lifecycle are independently accepted. Keep MEM-3 reads disabled
until that gate closes. No task may use private history or send hosted-provider
context under the synthetic development authorization. Local pilots must pass the
existing private socket, model identity, admission, usage and no-fallback checks.

An independent reviewer must inspect the blind split, attempt ledger, scorer,
source attribution and all failures. A clean scripted or local result is still not
E5 by itself. Integrated memory enablement, model-assisted promotion, production
release, external erase, replica/backup recovery and full-authority cold-restore
claims require their separate evidence gates.
