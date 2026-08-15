# Models

`models/` contains upstream/runtime snapshots, launch shims, and historical profiles.
It is data consumed by model plugins and legacy experiments; it is not the public model
integration API.

New integration ownership belongs under `sol/plugins/<model>/`. That plugin points to
the relevant runtime material here or to an externally pinned backend checkout. Sol does
not copy an entire model architecture into its core package.

## Two states

- A **profile-only** model has historical workload and seam evidence but no released
  backend/preset. It can be migrated, but `Engine.space()` and execution fail clearly.
- A **released** model has a cohesive plugin, at least one execution backend, a
  model-owned preset, and a fail-closed acceptance contract.

Use `sol models` to see the distinction. Do not infer release status from the presence
of a directory or an old optimized script.

## Legacy experiment contracts

Some `models/<id>/model.toml` files define a minimal copy closure used by
`scripts/create_model_experiment.py`. The bridge is implemented in
`sol/_internal/legacy_manifest.py` and remains private. New product features should not
depend on that schema.

Generated runs, search output, caches, environments, and weights must stay outside this
tree. Reusable optimization code belongs in `sol/optimizations/`; benchmark contracts
belong in `benchmarks/`.
