# Agent contract

This repository uses agents to adapt and tune models through the product architecture,
not through unbounded repository-wide patching.

## Objective

For a model adaptation, reduce the working domain to:

```text
verified model seams + backend mappings
    -> Engine.space(model, backend)
    -> optimization composition and tuning
    -> acceptance
    -> model-owned released preset
```

The resulting preset must be the same entry point documented for users.

## Architecture rules

- Public code lives under the single `sol` namespace.
- `Engine` is the public facade. Do not add another CLI or agent-only API.
- A complete model integration lives under `sol/plugins/<model>/` and owns its
  profile, backends, presets, launch metadata, and acceptance contract.
- Diffusers is the preferred semantic reference; SGLang is the preferred performance
  backend. Do not introduce a third full model/architecture implementation in `sol`.
- Reusable methods, transforms, and kernels live under `sol/optimizations/` and must not
  import the engine, catalog, or model plugins.
- No registration decorators or import-for-registration. Discovery uses lazy canonical
  `module:qualname` references in `sol/catalog.toml`.
- Do not create global `recipes/`, `search/`, or `search_space/` schemas. A release
  composition is a model-owned preset; a tuning domain is derived by `Engine.space()`;
  search is an interchangeable policy over that API.
- Model installation stages belong to the backend adapter. A caller or search agent
  tunes options only.
- Unknown options, missing capabilities, unsupported stages, and catalog collisions
  fail closed.

## Adaptation order

1. Freeze official semantic settings and reference artifacts.
2. Inspect and encode only verified model seams in the model profile.
3. Implement a dense execution path and backend option mappings.
4. Inspect `Engine.space()`; fix ownership at the profile, backend, or optimization
   provider if an axis is missing.
5. Build candidates exclusively through `Engine.optimize()`.
6. Benchmark against a dense same-backend, same-topology baseline.
7. Apply the model-owned acceptance contract, including authenticity checks.
8. Publish only the accepted candidate under the model plugin's `presets/` directory.
9. Mark the catalog entry `released` only when the preset and acceptance contract pass.

## Repository lifecycle

- `models/`: runtime snapshots and historical profiles, not the public integration API.
- `experiments/`: unstable lab manifests, not released behavior.
- `benchmarks/`: shared rubrics, profiles, and compact golden evidence.
- `runs/`: local generated artifacts; never commit videos, full logs, weights, caches,
  or environments.
- `site_docs/optimizations/search-guides/`: human guidance only; never treat it as the
  executable tuning domain.

## Required verification

Run the dependency-light contract suite for every control-plane change:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  python3 -m unittest discover -s tests/control_plane -v
sol doctor
git diff --check
```

Add tests for lazy loading, legal-space filtering, deterministic resolution, rejected
unsupported options, and dry-run side-effect behavior. GPU integration work additionally
requires same-config baseline/optimized evidence and the plugin's acceptance gates.

## Completion bar

Do not call a model adapted because one script ran. It is complete when an ordinary
user can discover and run a preset, an advanced user can inspect/customize it in a few
lines, and a weaker agent can reproduce its legal tuning space without understanding
unrelated model or architecture code.
