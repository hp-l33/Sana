"""Resolve a canonical recipe into a deterministic, executable plan."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sol_engine.catalog import Catalog, CatalogError, builtin_catalog
from sol_engine.recipe import Recipe
from sol_engine import _toml


class PlanResolutionError(ValueError):
    """Raised before launch when a recipe cannot be resolved safely."""


@dataclass(frozen=True)
class ResolvedOptimization:
    id: str
    kind: str
    provider: str
    implementation: str
    params: dict[str, Any]
    stages: tuple[str, ...]
    required_capabilities: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "provider": self.provider,
            "implementation": self.implementation,
            "params": self.params,
            "stages": list(self.stages),
            "required_capabilities": list(self.required_capabilities),
        }


@dataclass(frozen=True)
class ResolvedExecutionPlan:
    recipe_id: str
    recipe_source: str
    model_id: str
    model_provider: str
    model_profile: str
    model_spec: str
    model_spec_source: str
    capabilities: tuple[str, ...]
    launch_config: str
    preview_stage: str
    optimizations: tuple[ResolvedOptimization, ...]
    transform_order: tuple[str, ...]
    technique_order: tuple[str, ...]
    env_preview: dict[str, str]
    runtime_env: dict[str, str]
    runtime_ready: bool
    fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "recipe_id": self.recipe_id,
            "recipe_source": self.recipe_source,
            "model": {
                "id": self.model_id,
                "provider": self.model_provider,
                "profile": self.model_profile,
                "spec": self.model_spec,
                "spec_source": self.model_spec_source,
                "capabilities": list(self.capabilities),
            },
            "launch_config": self.launch_config,
            "preview_stage": self.preview_stage,
            "optimizations": [item.as_dict() for item in self.optimizations],
            "composition": {
                "transforms": list(self.transform_order),
                "techniques": list(self.technique_order),
            },
            "env_preview": dict(sorted(self.env_preview.items())),
            "runtime_env": dict(sorted(self.runtime_env.items())),
            "runtime_ready": self.runtime_ready,
            "fingerprint": self.fingerprint,
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True)


def default_repo_root() -> Path:
    root = Path(__file__).resolve().parents[1]
    if not (root / "models").is_dir():
        raise PlanResolutionError(
            "cannot locate the Sol-Engine repository; pass --repo-root or set "
            "up an editable checkout"
        )
    return root


def _read_toml(path: Path) -> dict[str, Any]:
    return _toml.load(path)


def _repo_file(repo_root: Path, relative: str, label: str) -> Path:
    path = (repo_root / relative).resolve()
    try:
        path.relative_to(repo_root)
    except ValueError as exc:
        raise PlanResolutionError(f"{label} escapes repository: {path}") from exc
    if not path.is_file():
        raise PlanResolutionError(f"{label} does not exist: {path}")
    return path


def resolve_recipe(
    recipe: Recipe,
    *,
    catalog: Catalog | None = None,
    repo_root: str | Path | None = None,
) -> ResolvedExecutionPlan:
    """Resolve and compose one recipe; import only its selected providers."""

    cat = catalog or builtin_catalog()
    root = Path(repo_root).resolve() if repo_root is not None else default_repo_root()

    try:
        model_entry = cat.require("models", recipe.model)
        profile_rel = str(model_entry.get("profile", ""))
        if not profile_rel:
            raise PlanResolutionError(
                f"model {recipe.model!r} catalog entry has no profile"
            )
        adapter_type = model_entry.load_provider()
        adapter = adapter_type(profile=profile_rel, repo_root=root)
        if adapter.id != recipe.model:
            raise PlanResolutionError(
                f"catalog model id {recipe.model!r} does not match profile id {adapter.id!r}"
            )
        spec = adapter.to_model_spec()
    except PlanResolutionError:
        raise
    except Exception as exc:
        raise PlanResolutionError(
            f"cannot resolve model adapter {recipe.model!r}: {exc}"
        ) from exc

    launch_path = _repo_file(root, recipe.launch_config, "launch_config")
    try:
        launch_data = _read_toml(launch_path)
    except (OSError, ValueError) as exc:
        raise PlanResolutionError(
            f"cannot read launch_config {launch_path}: {exc}"
        ) from exc
    if str(launch_data.get("model_profile", "")) != recipe.model:
        raise PlanResolutionError(
            f"{launch_path}: model_profile {launch_data.get('model_profile')!r} "
            f"does not match recipe model {recipe.model!r}"
        )

    # Importing techniques itself is intentionally cheap: it no longer imports
    # every concrete method/transform for registration side effects.
    from techniques import compose

    items = []
    selected = []
    resolved_items: list[ResolvedOptimization] = []
    for request in recipe.optimizations:
        try:
            entry = cat.require("optimizations", request.id)
        except CatalogError as exc:
            raise PlanResolutionError(str(exc)) from exc
        if entry.provider != request.provider:
            raise PlanResolutionError(
                f"recipe provider mismatch for {request.id!r}: "
                f"catalog pins {entry.provider.canonical!r}, recipe pins "
                f"{request.provider.canonical!r}"
            )
        try:
            provider = request.provider.load()
            item = provider(**dict(request.params))
        except Exception as exc:
            raise PlanResolutionError(
                f"cannot construct optimization {request.id!r} from "
                f"{request.provider.canonical}: {exc}"
            ) from exc
        items.append(item)
        selected.append((request, item))
        item_type = type(item)
        required = tuple(
            sorted(cap.value for cap in getattr(item, "required_capabilities", frozenset()))
        )
        resolved_items.append(
            ResolvedOptimization(
                id=request.id,
                kind=str(entry.get("kind", "")),
                provider=request.provider.canonical,
                implementation=f"{item_type.__module__}:{item_type.__qualname__}",
                params=dict(request.params),
                stages=request.stages,
                required_capabilities=required,
            )
        )

    try:
        executable = compose(items, spec)
    except Exception as exc:
        raise PlanResolutionError(
            f"recipe {recipe.id!r} is incompatible with model {recipe.model!r}: {exc}"
        ) from exc

    env_preview: dict[str, str] = {}
    try:
        executable.apply_transforms(None, stage=recipe.preview_stage, env=env_preview)
    except Exception as exc:
        raise PlanResolutionError(
            f"cannot preview recipe {recipe.id!r} at stage "
            f"{recipe.preview_stage!r}: {exc}"
        ) from exc

    render_runtime_env = getattr(adapter, "render_runtime_env", None)
    try:
        runtime_ready = render_runtime_env is not None
        runtime_env = render_runtime_env(selected, env_preview) if runtime_ready else {}
    except Exception as exc:
        raise PlanResolutionError(
            f"model adapter cannot compile recipe {recipe.id!r} to runtime config: {exc}"
        ) from exc

    payload = {
        "recipe_id": recipe.id,
        "model_id": recipe.model,
        "model_provider": model_entry.provider.canonical,
        "model_profile": profile_rel,
        "capabilities": sorted(cap.value for cap in spec.capabilities),
        "launch_config": recipe.launch_config,
        "preview_stage": recipe.preview_stage,
        "optimizations": [item.as_dict() for item in resolved_items],
        "transform_order": [item.name for item in executable.transforms],
        "technique_order": [item.name for item in executable.techniques],
        "env_preview": dict(sorted(env_preview.items())),
        "runtime_env": dict(sorted(runtime_env.items())),
        "runtime_ready": runtime_ready,
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return ResolvedExecutionPlan(
        recipe_id=recipe.id,
        recipe_source=recipe.source,
        model_id=recipe.model,
        model_provider=model_entry.provider.canonical,
        model_profile=profile_rel,
        model_spec=spec.name,
        model_spec_source=str(spec.extra.get("source", "")),
        capabilities=tuple(sorted(cap.value for cap in spec.capabilities)),
        launch_config=recipe.launch_config,
        preview_stage=recipe.preview_stage,
        optimizations=tuple(resolved_items),
        transform_order=tuple(item.name for item in executable.transforms),
        technique_order=tuple(item.name for item in executable.techniques),
        env_preview=env_preview,
        runtime_env=runtime_env,
        runtime_ready=runtime_ready,
        fingerprint=fingerprint,
    )
