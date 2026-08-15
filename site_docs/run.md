# Run

## Released presets

```bash
sol presets
sol inspect ltx23:fullopt
sol run ltx23:fullopt --dry-run
sol run ltx23:fullopt --set SGLANG_RUNTIME_ROOT=/path/to/sglang-runtime
```

Use this interface for published behavior. A preset is model-owned and has already
passed composition validation and a release-specific acceptance contract.

`--dry-run` does not create a run directory or launch a process. Add
`--persist /path/to/record.json` only when you explicitly want the planned record.

Actual run records default to `${XDG_STATE_HOME:-~/.local/state}/sol/runs`. Override
the artifact root with `--run-root PATH`.

## Laboratory manifests

The older launcher remains available for unpublished experiments:

```bash
python3 scripts/run.py experiments/<model>/<arm>.toml --print
python3 scripts/run.py experiments/<model>/<arm>.toml
```

This is a laboratory compatibility path, not the release API. An experiment becomes a
release only after its settings are expressed through a model plugin and promoted to a
model-owned preset.

## Overrides and provenance

```bash
sol run ltx23:fullopt --set KEY=VALUE --set OTHER=value
```

The plan fingerprint covers model, backend, providers, options, ordering, and compiled
runtime environment. The execution fingerprint additionally covers user overrides.
The provenance keys `SOL_PLAN_FINGERPRINT`, `SOL_EXECUTION_FINGERPRINT`, and
`SOL_PRESET` cannot be overridden.
