# Lessons from the Retired Prototype

These are historical search leads distilled before the prototype was removed. They are not current presets, reproducible releases, or benchmark claims. Re-establish the reference, target, artifacts, and same-topology baseline before using any value.

## LTX-2.3

The useful decomposition was two-stage: kernel work in both stages; step cache primarily in stage 1; sparse attention and token pruning primarily in stage 2; selective NVFP4 on video feed-forward blocks. Historical leads included a step-cache window around steps 16–28, stage-2 sparsity near 0.9, and token keep ratio near 0.5 for early stage-2 steps. The old evidence lacked a comparable measured baseline, so no speedup should be carried forward.

## MiniMax Hailuo 2.3 / H3

Treat joint audio-video semantics and distributed topology as first-class. Old H100 work used four H100s with Ulysses degree four; A100, GB200, RTX 5090, and GB10 required different legal spaces. Sparse-attention leads included `tau` 0.5–1.0, diagonal or exact scoring, 10–15 dense initial steps, two dense layers, and a prefix sink. Cache leads included EasyCache and first-block cache. Cache plus sparsity was non-multiplicative. A historical same-topology H100 result recorded roughly 81.47s to 22.89s, but it must be rerun from immutable commands and artifacts.

## Wan

For Wan 2.1 14B, prior leads combined regional compilation, EasyCache threshold near 0.036, and Sol-Attn with `tau` near 1.0 plus about ten dense initial steps. For Wan 2.2 5B, leads combined an exact kernel stack, EasyCache threshold near 0.036 with retained/cooldown controls, and PISA density near 0.10 with dense step/layer guards. A14B used a similar kernel/cache/sparse decomposition. Historical aggregate results were encouraging, but component speedups must not be multiplied and all variants need fresh same-target benchmarks.

## Cosmos 3

The old four-GB200 lead used TeaCache with threshold around 1.15, start near step 10, and a small consecutive-hit cap, plus selective NVFP4 with the first and last few blocks dense. A historical 2.26x figure is only a tuning prior.

## Hunyuan Video

Prior work explored compilation, TeaCache around threshold 0.15 with warmup and a small hit cap, and sparse attention with exact text/prefix sinks and dense text queries. No old timing was sufficiently complete for release.

## Lingbot Video

The model was a two-stage MoE base/refiner pipeline. Same-topology experiments used context parallelism and FSDP; leads included a cuDNN backend, refiner PISA density around 0.10, and different EasyCache thresholds for base and refiner. A historical 2.60x aggregate result requires complete rerun and artifact verification.

## Sana Video

The useful technique families were EasyCache, BF16 linear attention, QKV merging, and compilation. An old 2.77x figure is not release evidence.

## General Warnings

- Do not preserve model-specific configuration as a global Engine schema.
- Do not treat a technique name as proof that its optimized path ran.
- Do not publish “full optimization” without ablations and interaction checks.
- Do not compare different GPU counts as an optimization ratio.
- Do not inherit thresholds across targets without tuning.
- Do not let generated artifacts, workstation paths, or mutable container tags enter a release preset.
