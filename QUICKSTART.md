# Quickstart

This guide separates control-plane use from GPU execution. Discovery, customization,
and dry-run work on a CPU-only machine. Generation needs the model's declared runtime,
GPU, and weights.

## 1. Install the engine

```bash
git clone -b sol-engine https://github.com/NVlabs/Sana.git
cd Sana
python3 -m pip install --upgrade "pip>=24" "setuptools>=69"
python3 -m pip install -e .
```

Verify the release metadata without loading PyTorch or model code:

```bash
sol models
sol presets
sol doctor
```

The current end-to-end migrated release is LTX-2.3. Other entries are displayed as
`profile_only` until their model plugins are complete.

## 2. Inspect before running

```bash
sol inspect ltx23:baseline
sol inspect ltx23:fullopt --json
sol space ltx23 --backend sglang
sol run ltx23:fullopt --dry-run
```

These commands validate model capabilities, provider identity, optimization conflicts,
model-owned stages, backend option mappings, and launch paths. Dry-run does not create a
run directory.

## 3. Prepare the LTX-2.3 runtime

The LTX execution backend uses an SGLang checkout containing the LTX-2.3 multimodal
runtime. Create its environment and install its diffusion dependencies according to the
SGLang checkout's own instructions. The default launcher expects its interpreter at:

```text
<SGLANG_RUNTIME_ROOT>/.conda/ltx23/bin/python
```

You may instead pass `PYTHON_BIN=/absolute/path/to/python` as a run override.

Download `Lightricks/LTX-2.3`, the official distilled LoRA, and the spatial upscaler.
The launcher accepts explicit locations through `MODEL_PATH`, `DISTILLED_LORA`, and
`SPATIAL_UPSAMPLER`. Keeping these paths explicit is recommended on a new machine.

## 4. Run the same-backend control and optimized preset

```bash
COMMON=(
  --set SGLANG_RUNTIME_ROOT=/path/to/sglang-runtime
  --set MODEL_PATH=/path/to/LTX-2.3
  --set DISTILLED_LORA=/path/to/distilled-lora.safetensors
  --set SPATIAL_UPSAMPLER=/path/to/spatial-upscaler.safetensors
)

sol run ltx23:baseline "${COMMON[@]}"
sol run ltx23:fullopt  "${COMMON[@]}"
```

Both presets use the same SGLang backend, topology, model settings, prompts, and launch
body. `fullopt` changes only the backend environment compiled from its five selected
optimizations. This is the correct pair for an optimization speedup claim.

Actual artifacts default to `${XDG_STATE_HOME:-~/.local/state}/sol/runs`. Use
`--run-root /path/with/space` to choose another location.

## 5. Customize

```python
from sol import Engine

engine = Engine()
candidate = (
    engine.optimize("ltx23", backend="sglang")
    .use("step_cache", skip="16-28")
    .preset(name="cache-only")
)

print(engine.inspect(candidate).to_json())
engine.run(candidate, dry_run=True)
```

Start from `engine.space("ltx23", backend="sglang").as_dict()` rather than guessing
available optimizations or options.

## Legacy model experiments

Historical, not-yet-migrated manifests remain under `experiments/` and can be inspected
with `python3 scripts/run.py ... --print`. They are laboratory paths, not released Sol
presets. Their older per-model READMEs may have additional hardware and environment
requirements.
