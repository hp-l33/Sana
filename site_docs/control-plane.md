# Engine API

`Engine` is the only public facade. It covers discovery, composition, validation,
inspection, and execution.

## Discovery

```bash
sol models
sol models --json
sol presets
sol optimizations
```

Catalog listing is lazy. `sol models` shows release status, semantic references,
executable backends, and presets without importing model plugins. A `profile_only`
entry is migration evidence, not a runnable release. A reference is never listed as an
execution backend.

## Inspect a released preset

```bash
sol inspect ltx23:fullopt
sol inspect ltx23:fullopt --json
```

The plan records:

- model profile and provider;
- selected backend;
- model capabilities and their profile provenance;
- canonical optimization providers and concrete implementations;
- composition order and backend-compiled environment;
- a deterministic plan fingerprint.

Resolution fails before launch if a capability is missing, two optimizations conflict,
a stage is wrong, an option cannot be honored, or a launch manifest is inconsistent.

## Inspect the legal customization domain

```bash
sol space ltx23 --backend sglang
```

The JSON is derived from model capabilities, backend integrations, and optimization
parameter schemas. It is the supported input domain for both an advanced user and a
tuning agent.

## Compose

```python
from sol import Engine

engine = Engine()
candidate = (
    engine.optimize("ltx23", backend="sglang")
    .use("step_cache", skip="16-28")
    .preset(name="cache-only")
)
plan = engine.inspect(candidate)
```

Callers select optimization options. The model plugin owns installation stages and
the backend owns translation to runtime settings.

## Run

```bash
sol run ltx23:fullopt --dry-run
sol run ltx23:fullopt --set SGLANG_RUNTIME_ROOT=/path/to/sglang-runtime
```

Dry-run is in-memory unless `--persist PATH` is explicitly supplied. A real run adds
the immutable plan fingerprint and an execution fingerprint covering user overrides,
then delegates to the existing launcher.

## Scoped extensions

An external package may provide a scoped catalog:

```bash
sol --catalog /path/to/extension.toml models
```

Catalogs do not have a precedence order. Claiming an existing ID is an error. This
makes the active namespace explicit and prevents silent provider replacement.
