# Optimization Playbook

Use these families to define a bounded search space. Start dense, isolate each family, then test interactions. Technique availability and legal ranges belong to the selected model, backend, and target—not a global registry.

## Cache

Examples include step cache, TeaCache, EasyCache, and first-block cache. Search threshold, warmup/start step, retained context, cooldown, maximum consecutive hits, and stage scope. Emit hit/miss counters and fall back to recomputation when the error signal is unsafe. Re-tune after quantization or architecture changes.

## Sparse Attention

Examples include block or query-adaptive attention such as Sol-Attn/PISA. Search density or sparsity, threshold (`tau`), exact versus diagonal scoring, dense initial steps, dense layers, and prefix/text sinks. Preserve dense guards for early steps, sensitive layers, short sequences, and unsupported shapes. Prove the sparse kernel engaged.

## Quantization

Search precision by component rather than quantizing everything uniformly. Keep numerically sensitive first/last blocks, modulation, normalization, and output projections dense when needed. Record calibration assumptions and hardware support. Compare quality on the same artifacts and re-evaluate cache thresholds.

## Token Pruning

Search keep ratio, stage and step window, selection signal, normalization, and compensation/reconstruction. Guard scene changes and small token counts. Measure the selection overhead and verify positional/index correctness.

## Kernels and Compilation

Candidates include regional compilation, QKV merging, fused modulation/norm/residual paths, invariant K/V reuse, and target-specific attention kernels. Inspect graph breaks, compile amortization, dynamic-shape recompiles, memory growth, and numerical parity. Keep target-specific kernel selection behind a stable backend seam.

## Search Strategy

1. Reproduce the semantic reference.
2. Establish a dense backend baseline.
3. Profile and expose only justified seams.
4. Run single-family probes with small budgets.
5. Promote promising dimensions into a bounded joint search.
6. Re-run the best candidate from a clean process.
7. Encode only measured, target-specific settings as a named preset.

Use coarse-to-fine ranges and stop unproductive branches. The adaptation budget is a hard constraint. Keep rejected trials and reasons so the next agent does not repeat them.
