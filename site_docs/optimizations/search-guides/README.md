# Optimization search guides

These pages are human research and implementation guidance. They describe method
families worth considering; they are not an executable registry, a recipe archive, or a
fixed hyperparameter grid.

The authoritative domain for a model/backend pair is always:

```python
Engine().space(model, backend=backend)
```

That result is derived from verified model capabilities, implemented backend mappings,
and provider parameter schemas. A guide can be broader than the current engine; an
option appears in the executable domain only after those three owners agree.

## Guides

- [Cache](01_cache.md)
- [Token pruning](02_token_pruning.md)
- [Quantization](03_quantization.md)
- [Sparse attention](04_sparse_attention.md)
- [Kernel fusion](05_kernel_fusion.md)
- [Parallel topology](06_parallel_topology.md)

A tuning agent may use any search policy over the derived domain. Its accepted output
must be reproducible through `Engine.optimize()` and promoted as a model-owned preset.
