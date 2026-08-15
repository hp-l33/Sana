"""The single public control-plane entry point."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sol.catalog import Catalog, builtin_catalog
from sol.plan import ExecutionPlan, default_repo_root, resolve_preset
from sol.preset import OptimizationUse, Preset, PresetError
from sol.run import Run


@dataclass(frozen=True)
class ModelInfo:
    id: str
    display_name: str
    status: str
    references: tuple[str, ...]
    backends: tuple[str, ...]
    default_backend: str
    presets: tuple[str, ...]
    provider: str


@dataclass(frozen=True)
class PresetInfo:
    model: str
    name: str

    @property
    def id(self) -> str:
        return f"{self.model}:{self.name}"


class PresetBuilder:
    """Shared fluent API for advanced users and production agents."""

    def __init__(self, engine: "Engine", model: str, backend: str = "auto") -> None:
        self.engine = engine
        self.model = model
        self._plugin = engine.plugin(model)
        self.backend = self._plugin.backend(backend).name
        self._uses: list[OptimizationUse] = []

    def use(
        self,
        optimization: str,
        *,
        stages: tuple[str, ...] | list[str] | None = None,
        **options: Any,
    ) -> "PresetBuilder":
        self.engine.catalog.require("optimizations", optimization)
        owned_stages = self._plugin.optimization_stages(
            optimization, backend=self.backend
        )
        if owned_stages is None:
            raise PresetError(
                f"optimization {optimization!r} is not integrated with model {self.model!r}"
            )
        requested = tuple(stages) if stages is not None else owned_stages
        if requested != owned_stages:
            raise PresetError(
                f"{self.model}:{optimization} stages are model-owned: "
                f"expected {list(owned_stages)}, got {list(requested)}"
            )
        if any(use.id == optimization for use in self._uses):
            raise PresetError(f"optimization {optimization!r} was selected twice")
        self._uses.append(
            OptimizationUse(id=optimization, options=dict(options), stages=requested)
        )
        return self

    def preset(self, *, name: str = "candidate") -> Preset:
        if not self._uses:
            raise PresetError("candidate preset must select at least one optimization")
        return Preset(
            name=name,
            model=self.model,
            launch=self._plugin.default_launch(),
            optimizations=tuple(self._uses),
            backend=self.backend,
            preview_stage=self._plugin.default_preview_stage(),
            description="In-memory candidate built through Engine.optimize().",
        )

    def inspect(self, *, name: str = "candidate") -> ExecutionPlan:
        return resolve_preset(
            self.preset(name=name),
            catalog=self.engine.catalog,
            repo_root=self.engine.repo_root,
        )


class Engine:
    """Discover, validate, inspect, and run released model presets."""

    def __init__(
        self,
        *,
        catalog: Catalog | None = None,
        repo_root: str | Path | None = None,
    ) -> None:
        self.catalog = catalog or builtin_catalog()
        self.repo_root = (
            Path(repo_root).resolve() if repo_root is not None else default_repo_root()
        )

    def models(self) -> tuple[ModelInfo, ...]:
        return tuple(
            ModelInfo(
                id=entry.id,
                display_name=str(entry.get("display_name") or entry.id),
                status=str(entry.get("status") or "profile_only"),
                references=tuple(
                    str(value) for value in entry.get("references", ())
                ),
                backends=tuple(str(value) for value in entry.get("backends", ())),
                default_backend=str(entry.get("default_backend") or ""),
                presets=tuple(str(value) for value in entry.get("presets", ())),
                provider=entry.provider.canonical,
            )
            for entry in self.catalog.entries("models")
        )

    def presets(self, model: str | None = None) -> tuple[PresetInfo, ...]:
        values: list[PresetInfo] = []
        for item in self.models():
            if model is not None and item.id != model:
                continue
            values.extend(PresetInfo(item.id, name) for name in item.presets)
        if model is not None and not any(item.id == model for item in self.models()):
            self.catalog.require("models", model)
        return tuple(values)

    @staticmethod
    def parse_target(target: str) -> tuple[str, str]:
        normalized = target.strip().replace("/", ":", 1)
        model, separator, preset = normalized.partition(":")
        if not separator or not model or not preset:
            raise PresetError(
                f"preset target must be MODEL:PRESET, got {target!r}; "
                "for example ltx23:fullopt"
            )
        return model, preset

    def plugin(self, model: str):
        entry = self.catalog.require("models", model)
        provider = entry.load_provider()
        plugin = provider(profile=str(entry.get("profile", "")), repo_root=self.repo_root)
        if plugin.id != model:
            raise PresetError(
                f"catalog model {model!r} does not match plugin id {plugin.id!r}"
            )
        return plugin

    def preset(self, target: str) -> Preset:
        model, preset_name = self.parse_target(target)
        return self.plugin(model).load_preset(preset_name)

    def reference(self, model: str, name: str = "diffusers"):
        return self.plugin(model).reference(name)

    def inspect(self, target: str | Preset) -> ExecutionPlan:
        if isinstance(target, Preset):
            return resolve_preset(
                target, catalog=self.catalog, repo_root=self.repo_root
            )
        return resolve_preset(
            self.preset(target), catalog=self.catalog, repo_root=self.repo_root
        )

    def optimize(self, model: str, *, backend: str = "auto") -> PresetBuilder:
        return PresetBuilder(self, model, backend)

    def space(self, model: str, *, backend: str = "auto"):
        from sol.tuning import SearchSpace

        return SearchSpace.from_model(
            self.plugin(model), backend=backend, catalog=self.catalog
        )

    def run(
        self,
        target: str | Preset,
        *,
        overrides: Mapping[str, str] | None = None,
        dry_run: bool = False,
        persist: str | Path | None = None,
        run_root: str | Path | None = None,
    ) -> Run:
        run = Run.prepare(
            self.inspect(target),
            repo_root=self.repo_root,
            overrides=overrides,
            run_root=run_root,
        )
        if persist is not None:
            run.save(persist)
        if dry_run:
            return run
        completed = run.execute(cwd=self.repo_root)
        if persist is not None:
            completed.save(persist)
        return completed
