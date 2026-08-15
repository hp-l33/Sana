"""Sol: one engine for released video-generation acceleration presets."""

from sol.backend import BackendAdapter, BackendError
from sol.catalog import (
    Catalog,
    CatalogEntry,
    CatalogError,
    ProviderLoadError,
    ProviderRef,
    builtin_catalog,
)
from sol.engine import Engine, ModelInfo, PresetBuilder, PresetInfo
from sol.evaluation import AcceptanceSpec, Verdict
from sol.optimization import Optimization
from sol.plan import (
    ExecutionPlan,
    PlanResolutionError,
    resolve_preset,
)
from sol.plugin import ModelPlugin
from sol.preset import OptimizationUse, Preset, PresetError
from sol.reference import SemanticReference
from sol.run import Run

__all__ = [
    "Engine",
    "ModelPlugin",
    "BackendAdapter",
    "BackendError",
    "Optimization",
    "SemanticReference",
    "Preset",
    "Run",
    "ExecutionPlan",
    "ModelInfo",
    "PresetInfo",
    "PresetBuilder",
    "OptimizationUse",
    "PresetError",
    "AcceptanceSpec",
    "Verdict",
    "Catalog",
    "CatalogEntry",
    "CatalogError",
    "ProviderLoadError",
    "ProviderRef",
    "builtin_catalog",
    "PlanResolutionError",
    "resolve_preset",
]
