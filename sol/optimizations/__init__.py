# Copyright 2025 SGLang authors
#
# Model-agnostic inference-acceleration framework.
#
# A small typed/effect-checked composition layer for efficiency sol.optimizations:
#   * Schedule[T]  -- time-varying params (per step/stage), the time sub-DSL.
#   * Technique    -- a composable primitive with a phase + effect set (reads/
#                     writes) + Schedule[bool] enable; OFF == byte-identical.
#   * ModelSpec    -- a model's declaration of structural seams (capabilities).
#   * compose()    -- type-checks capabilities, rejects structural conflicts
#                     (effect system), orders by phase -> an executable Plan.
#   * catalog      -- immutable provider metadata + lazy import references.
#
# Model capabilities come from selected model plugins. Importing this package
# does not import concrete optimization providers; the catalog loads a selected
# provider directly by canonical reference.

from __future__ import annotations

from sol.optimizations.compose import (
    CompositionError,
    Plan,
    check_conflicts,
    compose,
)
from sol.optimizations.transform import (
    ModelTransform,
    TransformContext,
    TransformPhase,
)
from sol.optimizations.schedule import (
    Schedule,
    as_schedule,
    at_steps,
    before,
    by_stage,
    const,
    predicate,
    parse_steps,
)
from sol.optimizations.spec import ModelSpec
from sol.optimizations.technique import (
    Capability,
    Phase,
    Seam,
    Technique,
    TechniqueContext,
)

__all__ = [
    "Schedule", "as_schedule", "at_steps", "before", "by_stage", "const",
    "predicate", "parse_steps",
    "Technique", "TechniqueContext", "Phase", "Seam", "Capability",
    "ModelTransform", "TransformContext", "TransformPhase",
    "ModelSpec",
    "compose", "Plan", "CompositionError", "check_conflicts",
]
