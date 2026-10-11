# Evaluation

This package owns deterministic evaluators, offline fixture builders, and their static data.
JSON fixtures live under `fixtures/<area>/`; output schemas live under `schemas/`. Evaluations
exercise services through synthetic inputs and do not establish provider, cloud, or deployment
behavior.

`domains/fixtures.py` remains domain-owned because the API exposes those synthetic comparisons
as a supported demo endpoint as well as using them in offline evaluation.
