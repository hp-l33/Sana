---
name: sol-adapt-model
description: Adapt, optimize, validate, and prepare a model plugin for release in Sol Engine. Use when adding a new model such as MiniMax H3, continuing an existing Sol adaptation run, tuning optimization techniques for a target topology, or promoting measured results into a release preset.
---

# Sol Adapt Model

Drive model production through Sol's own adaptation state machine. Treat the Engine as the source of truth: do not invent parallel manifests, stage names, evidence formats, or release rules.

## Start or Resume

Read [workflow.md](references/workflow.md), then inspect the repository and run one of:

```bash
sol adapt start MODEL --reference diffusers --backend sglang --target TARGET --budget RUNS
sol adapt status RUN_ID --json
```

Use the reference and backend requested by the maintainer. If neither is specified, prefer a maintained semantic reference for correctness and a separate performance backend only when the target model is supported. Never silently fork model semantics into Sol.

## Execute the State Machine

Repeat:

```bash
sol adapt next RUN_ID --json
```

For the returned task:

1. Work only within `allowed_paths`.
2. Satisfy every acceptance criterion.
3. Produce a JSON evidence document containing the exact `required_evidence` keys.
4. Submit it with `sol adapt submit RUN_ID --evidence FILE`.
5. Re-read `sol adapt next`; do not infer the next stage yourself.

Before benchmarking, tuning, or promotion, read [evidence.md](references/evidence.md). Before choosing techniques or sweep dimensions, read [optimization-playbook.md](references/optimization-playbook.md). For model families represented in the retired Sol prototype, consult [legacy-model-lessons.md](references/legacy-model-lessons.md) as hypotheses only.

## Scaffold Through Sol

When the current task asks for a model surface, use:

```bash
sol adapt scaffold RUN_ID
```

Fill the generated self-owned plugin. Keep model identity, references, backends, targets, presets, and search-space construction together. Every exposed dimension must resolve through `Engine.inspect(..., options=...)` and be preserved in `ExecutionPlan.options`. Do not add a central registry, import-for-registration hook, global model switch, or a second config schema.

## Boundaries

- Keep reference semantics separate from performance integration.
- Make hardware and distributed topology part of the target identity.
- Expose techniques as composable configuration, not model-specific CLI flags.
- Reject unsupported combinations explicitly; do not silently downgrade.
- Store generated media, logs, profiles, and adaptation state outside Git.
- Preserve dense fallbacks and correctness guards for approximate techniques.
- Stop on a failed quality gate, incomparable baseline, missing artifact, exhausted budget, or unsupported backend.
- Stop at `awaiting_approval`. Only a maintainer may run `sol adapt approve`.
- Never publish, push, or overwrite a release without explicit maintainer authority.

## Finish

A model is not released merely because code runs. Completion requires a self-owned plugin, a named target, replayable baseline and candidate commands, comparable measurements, quality evidence, interaction testing, a release preset, passing repository checks, and recorded maintainer approval.
