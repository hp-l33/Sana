"""Small, model-owned description of a released optimization stack."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from sol import _toml


class PresetError(ValueError):
    """Raised when a preset is malformed or cannot be selected safely."""


@dataclass(frozen=True)
class OptimizationUse:
    """One optimization selected by a preset.

    Provider identity and model installation stages are owned by the catalog
    and model plugin; callers select only the optimization and its options.
    """

    id: str
    options: Mapping[str, Any]
    stages: tuple[str, ...] = ()

@dataclass(frozen=True)
class Preset:
    """A user-facing, model-owned optimization preset."""

    name: str
    model: str
    launch: str
    optimizations: tuple[OptimizationUse, ...]
    backend: str = "auto"
    preview_stage: str = ""
    description: str = ""
    source: str = ""

    @property
    def id(self) -> str:
        return f"{self.model}:{self.name}"

    def launch_path(self, repo_root: str | Path) -> Path:
        raw = Path(self.launch)
        if raw.is_absolute():
            candidate = raw
        elif self.launch.startswith(("./", "../")) and self.source:
            candidate = Path(self.source).resolve().parent / raw
        else:
            candidate = Path(repo_root).resolve() / raw
        path = candidate.resolve()
        root = Path(repo_root).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise PresetError(f"preset launch path escapes repository: {path}") from exc
        if not path.is_file():
            raise PresetError(f"preset launch file does not exist: {path}")
        return path

    @classmethod
    def from_toml(cls, path: str | Path, *, model: str) -> "Preset":
        preset_path = Path(path).resolve()
        try:
            data = _toml.load(preset_path)
        except (OSError, ValueError) as exc:
            raise PresetError(f"cannot read preset {preset_path}: {exc}") from exc
        if data.get("schema_version") != 1:
            raise PresetError(
                f"{preset_path}: unsupported schema_version "
                f"{data.get('schema_version')!r}; expected 1"
            )
        name = str(data.get("name", "")).strip()
        launch = str(data.get("launch", "")).strip()
        if not name or not launch:
            raise PresetError(f"{preset_path}: name and launch are required")

        raw_items = data.get("optimization", [])
        if not isinstance(raw_items, list):
            raise PresetError(f"{preset_path}: optimization must be a list of tables")
        uses: list[OptimizationUse] = []
        seen: set[str] = set()
        for index, raw in enumerate(raw_items):
            if not isinstance(raw, dict):
                raise PresetError(f"{preset_path}: optimization #{index} must be a table")
            optimization_id = str(raw.get("id", "")).strip()
            if not optimization_id:
                raise PresetError(f"{preset_path}: optimization #{index} is missing id")
            if optimization_id in seen:
                raise PresetError(
                    f"{preset_path}: duplicate optimization {optimization_id!r}"
                )
            seen.add(optimization_id)
            raw_stages = raw.get("stages", [])
            if not isinstance(raw_stages, list):
                raise PresetError(
                    f"{preset_path}: optimization {optimization_id!r} stages must be a list"
                )
            stages = tuple(str(value).strip() for value in raw_stages)
            if any(not value for value in stages) or len(stages) != len(set(stages)):
                raise PresetError(
                    f"{preset_path}: optimization {optimization_id!r} stages must be "
                    "non-empty and unique"
                )
            options = raw.get("options", {})
            if not isinstance(options, dict):
                raise PresetError(
                    f"{preset_path}: optimization {optimization_id!r} options must be a table"
                )
            uses.append(
                OptimizationUse(
                    id=optimization_id,
                    options=MappingProxyType(dict(options)),
                    stages=stages,
                )
            )
        return cls(
            name=name,
            model=model,
            launch=launch,
            optimizations=tuple(uses),
            backend=str(data.get("backend", "auto")),
            preview_stage=str(data.get("preview_stage", "")),
            description=str(data.get("description", "")),
            source=str(preset_path),
        )
