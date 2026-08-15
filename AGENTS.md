# Agent contract

Use the repository-local `sol-adapt-model` skill for model adaptation, optimization, acceptance, or release work. The Engine state machine is authoritative.

## Start

For a new model:

```bash
sol adapt start MODEL --reference REFERENCE --backend BACKEND --target TARGET --budget RUNS
```

For existing work:

```bash
sol adapt status RUN_ID --json
sol adapt next RUN_ID --json
```

Complete only the returned task, touch only `allowed_paths`, provide every `required_evidence` key, submit once, and ask for the next task again. Do not infer or skip lifecycle stages.

## Architecture invariants

- `sol` is the only product namespace and `Engine` is the user/agent facade.
- One integration lives under `sol/plugins/<model>/` and owns its manifest, reference mapping, backends, targets, technique space, presets, and plans.
- Do not add a central registry, registration decorator, import side effect, global model switch, or duplicate config schema.
- Do not copy an upstream architecture into Sol when a maintained semantic reference can own it.
- Keep semantic references, performance backends, and target-specific optimization choices distinct.
- Hardware, GPU count, interconnect, and distributed topology are part of target identity.
- Expose only verified technique seams. Unknown dimensions and combinations fail closed.
- Keep discovery dependency-light and never import GPU frameworks just to list models.
- Keep generated artifacts and adaptation state outside Git.

## Release invariants

- Compare baseline and candidate on the same backend and topology.
- Record raw samples, immutable commands, environment, artifacts, quality, and engagement evidence.
- Do not multiply component speedups or promote historical numbers.
- A preset is draft until the state machine reaches `awaiting_approval` and a maintainer approves it.
- The agent must not approve itself, publish, deploy, push, or broaden its allowed paths without explicit authority.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  python3 -m unittest discover -s tests -v
python3 -m compileall -q sol tests
sol doctor
git diff --check
```

Add dependency-light contract tests for every control-plane change. Model work additionally follows the evidence requirements returned by `sol adapt next`.
