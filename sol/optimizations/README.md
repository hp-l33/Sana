# Optimization library

This package owns reusable optimization behavior. It does not own model discovery,
release presets, agent orchestration, or backend-specific installation knowledge.

## Layers

- `technique.py` and `transform.py`: internal runtime/build-time contracts.
- `compose.py`: capability checks, seam conflicts, and deterministic ordering.
- `parameters.py`: machine-readable tuning axes exposed by `Engine.space()`.
- `methods/`: cache and token-reduction runtime methods.
- `transforms/`: sparse attention, NVFP4 FFN, and kernel-fusion transforms.
- `sparse_backends/`: Sol-Attn kernels and portable backend package.

Public callers use the structural `sol.Optimization` protocol and select providers by
catalog alias. The older internal `Technique`/`ModelTransform` split is an implementation
detail used by composition.

## Ownership rule

An optimization may declare:

- required structural capabilities;
- parameter names, kinds, ranges, choices, and defaults;
- model-independent conflicts and ordering effects.

It must not declare which stage of a particular model to patch or how to translate an
option into one runtime's environment variables. Those mappings belong to
`sol/plugins/<model>/backends/`.

The package must remain importable without importing `sol.engine`, `sol.catalog`, or a
model plugin. Provider discovery is lazy and catalog-driven; no module registers itself
at import time.

## Verify

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  python3 -m unittest discover -s tests/control_plane -v
```

Kernel/backend tests have additional PyTorch and GPU requirements described in their
subdirectory READMEs.
