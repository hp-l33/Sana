# Adaptation Workflow

Sol separates semantic truth, execution, optimization, evidence, and release. The agent advances through the Engine-owned state machine; the skill supplies operating discipline, not a competing workflow.

## Lifecycle

| Stage | Purpose | Typical output |
| --- | --- | --- |
| `scoped` | Freeze model, reference, backend, target, and experiment budget | Adaptation state |
| `scaffolded` | Create one self-owned model plugin | `sol/plugins/<model>/` |
| `reference_verified` | Prove the reference path is reproducible | Reference command and artifacts |
| `dense_backend_verified` | Match performance-backend semantics before approximations | Dense parity evidence |
| `seams_wired` | Expose stable optimization insertion points | Technique seams and guards |
| `space_ready` | Define a bounded, target-legal search space | Search-space summary |
| `tuned` | Run staged, budgeted experiments | Trial ledger and best candidate |
| `accepted` | Re-run baseline and candidate under one protocol | Performance and quality evidence |
| `release_candidate` | Encode the measured candidate as a preset | Preset and replay commands |
| `awaiting_approval` | Pass repository checks and request human review | Validation report |
| `released` | Record maintainer approval | Approved release state |

The CLI returns the precise task, allowed paths, acceptance criteria, and required evidence for the current stage. Those fields override examples in this document.

## Command Sequence

```bash
sol adapt start minimax_h3 \
  --reference diffusers \
  --backend sglang \
  --target h100_sxm_80gb_x4 \
  --budget 40

sol adapt next RUN_ID --json
sol adapt scaffold RUN_ID
sol adapt submit RUN_ID --evidence evidence/reference_verified.json
sol adapt status RUN_ID --json
```

Continue `next -> work -> submit` until the approval gate. To resume after interruption, use the run ID with `status` and `next`; the state is durable and does not depend on agent memory.

## Ownership

Sol owns:

- the plugin contract and lazy discovery;
- backend adapters and optimization seams;
- target-specific search spaces and presets;
- execution plans, evidence requirements, and release gates.

The upstream reference owns model semantics. The performance backend owns serving or distributed runtime mechanics. The agent connects these surfaces without copying an entire model zoo into Sol.

## Plugin Shape

Each model is a vertical, self-owned slice:

```text
sol/plugins/<model>/
├── plugin.toml       # identity and provider pointer
├── plugin.py         # references, backends, targets, presets, plans
└── presets/          # optional larger target-specific preset data
```

Discovery scans these manifests without importing providers. The provider is loaded only when that model is selected. A plugin must reject unknown targets, presets, and technique combinations before execution.

## Human Gate

The agent prepares `awaiting_approval`; it does not approve itself. The maintainer reviews evidence and runs:

```bash
sol adapt approve RUN_ID --by MAINTAINER
```

Approval records the decision. Publishing or pushing remains a separate, explicitly authorized operation.
