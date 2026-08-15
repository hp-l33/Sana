# LTX-2.3 runtime material

This directory contains the two SGLang launch arms and their shared official workload.
The public integration is the cohesive plugin at `sol/plugins/ltx23/`.

```text
sol/plugins/ltx23/
  profile.toml
  references/diffusers.py
  backends/sglang.py
  presets/{baseline,fullopt}.toml
  acceptance.toml
  launch/{baseline,fullopt}.toml

models/ltx23/
  run_ltx23_common.sh
  prompts/{default,negative}.txt
  baseline/{env.sh,scripts/run_ltx23_gpu.sh}
  optimized/{env.sh,scripts/run_ltx23_gpu.sh}
```

Both released presets use the SGLang backend and the same shared launch body. The
baseline adapter emits every acceleration knob as OFF. The full-opt preset enables KWL
fusion, stage-1 step cache, stage-2 PISA, NVFP4 video FFNs, and stage-2 token pruning.

Inspect and run through the engine:

```bash
sol inspect ltx23:baseline
sol inspect ltx23:fullopt
sol run ltx23:fullopt --dry-run
```

GPU execution requires `SGLANG_RUNTIME_ROOT` plus LTX-2.3 model, distilled LoRA, and
spatial-upscaler paths. See the repository `QUICKSTART.md`.

The model architecture and optimized multimodal runtime remain in the pinned SGLang
checkout. They are referenced through `SGLANG_RUNTIME_ROOT`, not copied into the Sol
package. Diffusers is retained as the semantic reference; performance claims use the
dense SGLang baseline so model, topology, and framework stay fixed.

Historical `model.toml` and `models/ltx23.toml` data remain for legacy experiment
materialization. New users and agents should not build release logic on those schemas.
