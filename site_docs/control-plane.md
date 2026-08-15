# Experimental control plane

The control plane is a dependency-light layer above the existing model runtimes and
launcher. It validates what will run; it does not reimplement GPU inference.

## Three boundaries

1. `sol_engine/catalog.toml` maps short model and optimization IDs to canonical
   `module:qualname` references. It contains metadata, never live Python objects.
2. `models/<id>.toml` owns capability evidence. Only seams marked `wired` or `verified`
   become capabilities; a recipe cannot grant capabilities to its own model.
3. `recipes/<model>/<preset>.toml` pins the selected providers, their parameters, stages,
   and the existing launch config that executes the verified runtime.

Listing metadata is side-effect free:

```bash
python3 -m sol_engine models
python3 -m sol_engine optimizations
```

Provider modules are imported only after a recipe selects them:

```bash
python3 -m sol_engine plan recipes/ltx23/fullopt.toml --json
```

The resolved plan records the canonical provider and concrete implementation for every
component, model capability provenance, transform/technique order, environment preview,
adapter-compiled runtime environment, and a deterministic SHA-256 fingerprint. The
LTX-2.3 adapter emits explicit OFF values for unselected components, so editing a recipe
changes the delegated run instead of merely changing its metadata.

The generic profile adapter is validation-only. `run` fails closed until a model adapter
implements `render_runtime_env`; a syntactically valid recipe is not treated as executable
when the target runtime cannot consume its settings.

## Running a release recipe

```bash
python3 -m sol_engine run recipes/ltx23/fullopt.toml --print
python3 -m sol_engine run recipes/ltx23/fullopt.toml
```

Both commands resolve the recipe first. The second command then delegates to
`scripts/run.py`, so run bundles, provenance, local execution, and artifacts still use
the existing implementation. The launcher bundle records both the immutable plan
fingerprint and an execution fingerprint that also covers user `--set` overrides.

## Extension rule

An adapter or optimization should be independently importable and should publish a
canonical provider reference plus metadata. Do not add imports to `techniques/__init__.py`
or mutate a central Python dictionary. Catalog merges reject duplicate IDs instead of
silently overwriting them.

An adaptation package does not have to edit the built-in release catalog. It can ship a
scoped catalog and opt into it explicitly:

```bash
python3 -m sol_engine --catalog path/to/my-catalog.toml models
python3 -m sol_engine --catalog path/to/my-catalog.toml plan path/to/recipe.toml
```

There is no precedence rule: two catalogs claiming the same ID are an error. This keeps
extension ownership local and makes the selected namespace visible in the command.

For advanced Python composition, import provider classes directly and pass objects to
`techniques.compose()`. The string catalog exists only at the serialization/CLI boundary.
