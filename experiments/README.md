# Experiments

This directory contains unpublished laboratory manifests. They are useful for baseline
bring-up, probes, ablations, and migration of older model paths, but they are not the
user-facing product API.

```bash
python3 scripts/run.py experiments/<model>/<arm>.toml --print
```

The legacy launcher validates paths and prepares a bundle before execution. Manifests
must not contain model weights, environments, generated media, or large logs.

Promotion is explicit:

1. move structural knowledge into `sol/plugins/<model>/`;
2. expose legal options through the backend-derived `Engine.space()`;
3. reproduce the candidate through `Engine.optimize()`;
4. pass the model-owned acceptance contract;
5. serialize the accepted candidate as a model-owned preset.

Do not add a second recipe schema or search registry here. If an experiment needs a new
reusable parameter, define it on the optimization provider. If it needs model-specific
installation knowledge, define it on the backend adapter.
