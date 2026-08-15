# Evidence Contract

Optimization claims are release data. Fail closed when any required evidence is missing or incomparable.

## Comparability

Baseline and candidate must share:

- model revision and weights;
- prompt, seed, resolution, frame count, steps, and guidance;
- dtype and numerical mode unless the change is explicitly under test;
- GPU type, GPU count, interconnect, distributed topology, software image, and environment;
- warmup policy, synchronization points, timing boundaries, and repetition count.

Never compare one GPU against eight GPUs as an optimization speedup. Treat topology as part of the target identifier. Report throughput, latency, and resource scaling separately when topology changes.

## Required Measurement Shape

Record raw per-run samples, not only a derived speedup. At minimum include:

```json
{
  "passed": true,
  "baseline_command": ["..."],
  "candidate_command": ["..."],
  "environment_fingerprint": "...",
  "warmup_runs": 2,
  "baseline_samples_seconds": [80.9, 81.5, 81.0],
  "candidate_samples_seconds": [23.0, 22.8, 22.9],
  "artifacts": ["..."],
  "quality": {"gate": "pass", "method": "..."}
}
```

Compute summaries from recorded samples. Do not type a speedup by hand when it can be derived.

## Artifact Authenticity

- Capture commands, configs, stdout/stderr logs, dependency versions, model revision, and device inventory.
- Prove every claimed technique actually engaged using counters, structured logs, traces, or plan inspection.
- Detect silent fallback to dense execution or a different backend.
- Keep large media, logs, profiler reports, and checkpoints outside Git; evidence may reference immutable locations and hashes.

## Quality Gate

Use a deterministic prompt/seed suite appropriate to the model. Preserve the reference artifact and compare the candidate with declared metrics and a visual or task-specific rubric. Check temporal consistency for video and audio-video alignment for joint generation. A successful process exit is not a quality pass.

Approximate techniques require dense guards and adversarial cases around scene cuts, motion, prompt changes, long sequences, and stage transitions. A release preset must pass the agreed gate; failed candidates stay in the trial ledger.

## Interaction Testing

Measure important techniques alone before combining them. Cache and sparse attention frequently overlap in saved work, so their speedups are not multiplicative. Quantization can alter cache error signals. Compilation can hide graph breaks or disable dynamic guards. Record an interaction matrix for the winning stack and reject combinations that silently disable a component.

## Submission

`sol adapt next --json` returns `required_evidence`. The submitted JSON must contain `schema_version`, the current `stage`, `passed: true`, and every required key with non-empty values. The Engine copies accepted evidence into durable adaptation state and advances exactly one stage.
