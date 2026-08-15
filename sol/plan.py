"""Resolve a model-owned preset into a deterministic executable plan."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sol.catalog import Catalog, CatalogError, builtin_catalog
from sol.preset import OptimizationUse, Preset, PresetError


class PlanResolutionError(ValueError):
    """Raised before launch when a preset cannot be resolved safely."""


@dataclass(frozen=True)
class ResolvedOptimization:
    id: str
    kind: str
    provider: str
    implementation: str
    options: dict[str, Any]
    stages: tuple[str, ...]
    required_capabilities: tuple[str, ...]

    @property
    def params(self) -> dict[str, Any]:
        return self.options

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "provider": self.provider,
            "implementation": self.implementation,
            "options": self.options,
            "stages": list(self.stages),
            "required_capabilities": list(self.required_capabilities),
        }


@dataclass(frozen=True)
class ExecutionPlan:
    preset_id: str
    preset_source: str
    model_id: str
    model_provider: str
    backend: str
    model_profile: str
    model_spec: str
    model_spec_source: str
    capabilities: tuple[str, ...]
    launch_config: str
    preview_stage: str
    optimizations: tuple[ResolvedOptimization, ...]
    transform_order: tuple[str, ...]
    runtime_order: tuple[str, ...]
    env_preview: dict[str, str]
    runtime_env: dict[str, str]
    runtime_ready: bool
    fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "preset": {
                "id": self.preset_id,
                "source": self.preset_source,
            },
            "model": {
                "id": self.model_id,
                "provider": self.model_provider,
                "profile": self.model_profile,
                "spec": self.model_spec,
                "spec_source": self.model_spec_source,
                "capabilities": list(self.capabilities),
            },
            "backend": self.backend,
            "launch": self.launch_config,
            "preview_stage": self.preview_stage,
            "optimizations": [item.as_dict() for item in self.optimizations],
            "order": {
                "prepare": list(self.transform_order),
                "runtime": list(self.runtime_order),
            },
            "environment": dict(sorted(self.runtime_env.items())),
            "environment_preview": dict(sorted(self.env_preview.items())),
            "runtime_ready": self.runtime_ready,
            "fingerprint": self.fingerprint,
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True)


def default_repo_root() -> Path:
    root = Path(__file__).resolve().parents[1]
    if not (root / "models").is_dir():
        raise PlanResolutionError(
            "cannot locate the Sol repository; pass repo_root or use an editable checkout"
        )
    return root


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def _load_plugin(model_id: str, catalog: Catalog, root: Path):
    try:
        entry = catalog.require("models", model_id)
        profile = str(entry.get("profile", ""))
        if not profile:
            raise PlanResolutionError(f"model {model_id!r} has no profile")
        plugin_type = entry.load_provider()
        plugin = plugin_type(profile=profile, repo_root=root)
        if plugin.id != model_id:
            raise PlanResolutionError(
                f"catalog model {model_id!r} does not match plugin id {plugin.id!r}"
            )
        return entry, plugin
    except PlanResolutionError:
        raise
    except Exception as exc:
        raise PlanResolutionError(f"cannot load model plugin {model_id!r}: {exc}") from exc


def resolve_preset(
    preset: Preset,
    *,
    catalog: Catalog | None = None,
    repo_root: str | Path | None = None,
) -> ExecutionPlan:
    """Resolve and compose one preset, importing only selected providers."""

    cat = catalog or builtin_catalog()
    root = Path(repo_root).resolve() if repo_root is not None else default_repo_root()
    model_entry, plugin = _load_plugin(preset.model, cat, root)
    try:
        spec = plugin.to_model_spec()
        backend = plugin.backend(preset.backend)
        launch_path = preset.launch_path(root)
    except (PresetError, OSError, ValueError) as exc:
        raise PlanResolutionError(str(exc)) from exc

    from sol import _toml

    try:
        launch_data = _toml.load(launch_path)
    except (OSError, ValueError) as exc:
        raise PlanResolutionError(f"cannot read launch file {launch_path}: {exc}") from exc
    launch_model = str(launch_data.get("model_profile", ""))
    if launch_model and launch_model != preset.model:
        raise PlanResolutionError(
            f"{launch_path}: model_profile {launch_model!r} does not match "
            f"preset model {preset.model!r}"
        )

    from sol.optimizations import compose

    items: list[Any] = []
    selected: list[tuple[OptimizationUse, Any]] = []
    resolved: list[ResolvedOptimization] = []
    for request in preset.optimizations:
        try:
            entry = cat.require("optimizations", request.id)
        except CatalogError as exc:
            raise PlanResolutionError(str(exc)) from exc
        try:
            provider = entry.load_provider()
            item = provider(**dict(request.options))
        except Exception as exc:
            raise PlanResolutionError(
                f"cannot construct optimization {request.id!r} from "
                f"{entry.provider.canonical}: {exc}"
            ) from exc
        items.append(item)
        selected.append((request, item))
        item_type = type(item)
        required = tuple(
            sorted(
                capability.value
                for capability in getattr(item, "required_capabilities", frozenset())
            )
        )
        resolved.append(
            ResolvedOptimization(
                id=request.id,
                kind=str(entry.get("kind", "")),
                provider=entry.provider.canonical,
                implementation=f"{item_type.__module__}:{item_type.__qualname__}",
                options=dict(request.options),
                stages=request.stages,
                required_capabilities=required,
            )
        )

    try:
        composed = compose(items, spec)
    except Exception as exc:
        raise PlanResolutionError(
            f"preset {preset.id!r} is incompatible with model {preset.model!r}: {exc}"
        ) from exc

    env_preview: dict[str, str] = {}
    try:
        composed.apply_transforms(None, stage=preset.preview_stage, env=env_preview)
    except Exception as exc:
        raise PlanResolutionError(
            f"cannot preview preset {preset.id!r} at stage "
            f"{preset.preview_stage!r}: {exc}"
        ) from exc

    render_runtime_env = getattr(backend, "render_runtime_env", None)
    try:
        runtime_ready = bool(getattr(backend, "executable", False)) and callable(
            render_runtime_env
        )
        runtime_env = render_runtime_env(selected, env_preview) if runtime_ready else {}
    except Exception as exc:
        raise PlanResolutionError(
            f"model plugin cannot compile preset {preset.id!r}: {exc}"
        ) from exc

    profile_path = Path(getattr(plugin, "profile_path", ""))
    payload = {
        "preset_id": preset.id,
        "model_id": preset.model,
        "model_provider": model_entry.provider.canonical,
        "backend": backend.name,
        "model_profile": _relative(profile_path, root),
        "capabilities": sorted(capability.value for capability in spec.capabilities),
        "launch": _relative(launch_path, root),
        "preview_stage": preset.preview_stage,
        "optimizations": [item.as_dict() for item in resolved],
        "transform_order": [item.name for item in composed.transforms],
        "runtime_order": [item.name for item in composed.techniques],
        "env_preview": dict(sorted(env_preview.items())),
        "runtime_env": dict(sorted(runtime_env.items())),
        "runtime_ready": runtime_ready,
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ExecutionPlan(
        preset_id=preset.id,
        preset_source=preset.source,
        model_id=preset.model,
        model_provider=model_entry.provider.canonical,
        backend=backend.name,
        model_profile=payload["model_profile"],
        model_spec=spec.name,
        model_spec_source=str(spec.extra.get("source", "")),
        capabilities=tuple(payload["capabilities"]),
        launch_config=payload["launch"],
        preview_stage=preset.preview_stage,
        optimizations=tuple(resolved),
        transform_order=tuple(payload["transform_order"]),
        runtime_order=tuple(payload["runtime_order"]),
        env_preview=env_preview,
        runtime_env=runtime_env,
        runtime_ready=runtime_ready,
        fingerprint=fingerprint,
    )
