"""Sol-Engine's side-effect-free control-plane API."""

from sol_engine.catalog import (
    Catalog,
    CatalogEntry,
    CatalogError,
    ProviderLoadError,
    ProviderRef,
    builtin_catalog,
)
from sol_engine.plan import (
    PlanResolutionError,
    ResolvedExecutionPlan,
    resolve_recipe,
)
from sol_engine.recipe import OptimizationRequest, Recipe, RecipeError

__all__ = [
    "Catalog",
    "CatalogEntry",
    "CatalogError",
    "ProviderLoadError",
    "ProviderRef",
    "builtin_catalog",
    "OptimizationRequest",
    "Recipe",
    "RecipeError",
    "ResolvedExecutionPlan",
    "PlanResolutionError",
    "resolve_recipe",
]
