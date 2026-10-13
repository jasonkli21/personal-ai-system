# Evaluation

This package owns deterministic evaluators, offline fixture builders, and their static data.
JSON fixtures live under `fixtures/<area>/`; output schemas live under `schemas/`. Evaluations
exercise services through synthetic inputs and do not establish provider, cloud, or deployment
behavior.

Phase 36's `verification/` program indexes existing executable contracts and
original acceptance obligations in a strict versioned matrix. `make
integrated-verification` executes offline rows, captures exact parametrized case
receipts, and generates matrix results, a blocker ledger, and a Markdown report
in the ignored root `artifacts/phase36/` directory. A nonzero exit means the local
execution failed; zero does not mean release-ready. Missing external evidence
keeps affected capabilities unavailable. Reports contain synthetic identifiers
and numeric observations, never prompts, credentials or provider output bodies.

The declared fault scenarios refer to owning regression tests; the runner does
not add a parallel runtime or duplicate lifecycle authority. Use `make
backend-test-offline` for the full environment-independent suite. Native-store,
cloud, live provider, domain and browser gates remain separate. Read the
[verification model](../../../../docs/personal-ai-chapter-2/phase-36/architecture.md)
before interpreting results or adding evidence classes.

`domains/fixtures.py` remains domain-owned because the API exposes those synthetic comparisons
as a supported demo endpoint as well as using them in offline evaluation.
