# `techniques/`

Model-agnostic efficiency config code for video-generation inference.

The package owns the reusable algorithm/policy layer. A model adapter supplies
the runtime seams: denoise-step loop, transformer-block loop, token layout,
attention backend, FFN linear modules, and any model-specific CFG/RoPE/text
prefix details.

## Entry Flow

```text
config/<dimension>/<config>.toml
  -> scripts/launch_config.py --mode dry-run
  -> techniques.config_manifest.dry_run_manifest()
  -> catalog alias -> canonical provider (loaded on demand)
  -> selected model adapter -> profile-owned wired capabilities
  -> compose(items, adapter-derived ModelSpec)
  -> transform env preview or runtime Technique plan
  -> model runtime hook consumes that plan
```

Public-reference and soundness gates live in `scripts/audit_*.py` and
`scripts/probe_*.py`. Their Markdown reports are generated on demand and are
not required repo state.

## Core Framework

- `technique.py`: `Technique`, `Capability`, `Seam`, `Phase`,
  `TechniqueContext`.
- `transform.py`: build/load-time `ModelTransform`.
- `compose.py`: capability checks, seam-conflict checks, and ordered `Plan`.
- `schedule.py`: step/stage schedule DSL.
- `registry.py`: compatibility facade over the immutable provider catalog; it
  owns no process-global registration dictionaries.
- `config_manifest.py`: TOML schema checks, capability resolution, and
  manifest-derived dry-run specs.

## Runtime Techniques

- `techniques/step_cache.py`: whole-step skip/reuse and delta forecast.
- `techniques/teacache.py`: TeaCache rel-L1/poly controller, whole-step
  TeaCache, and block-residual TeaCache replay.
- `techniques/payload_cache.py`: PAB-style attention/MLP payload cache
  controller.
- `techniques/token_prune.py`: feature-norm pruning, region-density pruning,
  CAT-style cluster/stale selection, ToMe merge/unmerge, ToMeSD random-2D
  merge/unmerge, and gather/scatter compensation.

## Build/Load Transforms

- `transforms/sparse_attention.py`: sparse-attention route/backend env policy.
- `sparse_attention_policies.py`: PISA/SVG/SpargeAttn/MInference route masks,
  SAP dynamic map/permutation helpers, and block-index conversion.
- `transforms/nvfp4_ffn.py`: NVFP4 FFN load-time policy.
- `nvfp4_profile.py`: profiled NVFP4 layer selection and dense guards.
- `transforms/kwl_fusions.py`: generic KWL backend and compile/capture policy.

## Model Capability Contract

`sol_engine.adapters.profile.ProfileModelAdapter` derives a `ModelSpec` from
the selected model profile. Only `[seam_status]` entries marked `wired` or
`verified` become capabilities. `[requirements].capabilities` is checked
against that model-owned contract; it is never copied into the contract.

## Verify

```bash
# Release configs resolve and their repo-side paths exist. A frontier config
# whose model profile has no wired seam is expected to fail closed here.
for c in config/*/*.toml; do python3 scripts/run.py "$c" --print >/dev/null || echo "REJECTED $c"; done

# The lazy provider catalog and composition layer agree:
PYTHONNOUSERSITE=1 python3 techniques/selftest.py
```
