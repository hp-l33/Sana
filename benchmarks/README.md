# Benchmarks

`benchmarks/` defines evidence vocabulary and compact reference data. It does not
launch models and it does not own release configuration.

Model-specific release thresholds live beside the model plugin in
`sol/plugins/<model>/acceptance.toml`. Shared profiles, rubrics, tier definitions, and
small golden records live here.

## Required gates

| Gate | Question |
| --- | --- |
| artifacts | Did the run produce every declared artifact? |
| official config | Is the workload comparable to the semantic reference? |
| performance | Does it beat the dense same-backend baseline by the declared amount? |
| warmup | Was compile/cache warmup completed as required? |
| quality | Did quantitative and visual checks pass? |
| authenticity | Did each selected optimization actually engage? |

Acceptance is fail-closed: missing evidence is failure, not an implicit skip. A model
plugin may declare stricter, technique-specific checks such as OFF identity, numeric
tolerance, sparse-kernel statistics, or cache reuse counts.

Generated frames, videos, full logs, and local run bundles do not belong here. Store
them in the configured run artifact location and commit only compact, reviewable golden
metadata when it is required for regression tests.
