"""Typed release recipe schema."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from sol_engine.catalog import CatalogError, ProviderRef
from sol_engine import _toml


class RecipeError(ValueError):
    """Raised when a release recipe is malformed."""


@dataclass(frozen=True)
class OptimizationRequest:
    id: str
    provider: ProviderRef
    params: Mapping[str, Any]
    stages: tuple[str, ...] = ()


@dataclass(frozen=True)
class Recipe:
    schema_version: int
    id: str
    model: str
    launch_config: str
    optimizations: tuple[OptimizationRequest, ...]
    preview_stage: str = ""
    description: str = ""
    source: str = ""

    @classmethod
    def from_toml(cls, path: str | Path) -> "Recipe":
        recipe_path = Path(path).resolve()
        try:
            data = _toml.load(recipe_path)
        except (OSError, ValueError) as exc:
            raise RecipeError(f"cannot read recipe {recipe_path}: {exc}") from exc
        if data.get("schema_version") != 1:
            raise RecipeError(
                f"{recipe_path}: unsupported schema_version "
                f"{data.get('schema_version')!r}; expected 1"
            )
        recipe_id = str(data.get("id", "")).strip()
        model = str(data.get("model", "")).strip()
        launch_config = str(data.get("launch_config", "")).strip()
        missing = [
            name
            for name, value in (("id", recipe_id), ("model", model), ("launch_config", launch_config))
            if not value
        ]
        if missing:
            raise RecipeError(f"{recipe_path}: missing required fields: {missing}")

        requests: list[OptimizationRequest] = []
        seen: set[str] = set()
        raw_items = data.get("optimization", [])
        if not isinstance(raw_items, list) or not raw_items:
            raise RecipeError(f"{recipe_path}: at least one [[optimization]] is required")
        for index, raw in enumerate(raw_items):
            if not isinstance(raw, dict):
                raise RecipeError(f"{recipe_path}: optimization #{index} must be a table")
            item_id = str(raw.get("id", "")).strip()
            if not item_id:
                raise RecipeError(f"{recipe_path}: optimization #{index} is missing id")
            if item_id in seen:
                raise RecipeError(f"{recipe_path}: duplicate optimization id {item_id!r}")
            seen.add(item_id)
            try:
                provider = ProviderRef.parse(str(raw.get("provider", "")))
            except CatalogError as exc:
                raise RecipeError(
                    f"{recipe_path}: optimization {item_id!r}: {exc}"
                ) from exc
            params = raw.get("params", {})
            if not isinstance(params, dict):
                raise RecipeError(
                    f"{recipe_path}: optimization {item_id!r} params must be a table"
                )
            raw_stages = raw.get("stages", [])
            if not isinstance(raw_stages, list):
                raise RecipeError(
                    f"{recipe_path}: optimization {item_id!r} stages must be a list"
                )
            stages = tuple(str(stage).strip() for stage in raw_stages)
            if any(not stage for stage in stages) or len(set(stages)) != len(stages):
                raise RecipeError(
                    f"{recipe_path}: optimization {item_id!r} stages must be "
                    "non-empty and unique"
                )
            requests.append(
                OptimizationRequest(
                    id=item_id,
                    provider=provider,
                    params=MappingProxyType(dict(params)),
                    stages=stages,
                )
            )

        return cls(
            schema_version=1,
            id=recipe_id,
            model=model,
            launch_config=launch_config,
            optimizations=tuple(requests),
            preview_stage=str(data.get("preview_stage", "")),
            description=str(data.get("description", "")),
            source=str(recipe_path),
        )
