import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .contracts import ExecutionPlan, ModelInfo
from .discovery import PluginDiscovery
from .errors import SolError


class Engine:
    def __init__(self, discovery: Optional[PluginDiscovery] = None):
        self.discovery = discovery or PluginDiscovery()

    def models(self, include_drafts: bool = False) -> List[ModelInfo]:
        items = self.discovery.manifests()
        return items if include_drafts else [item for item in items if item.status == "released"]

    def search_space(self, model: str, backend: str, target: str) -> Dict[str, Any]:
        info = self.discovery.get(model)
        if backend not in info.backends:
            raise SolError(f"model {model!r} does not support backend {backend!r}")
        if target not in info.targets:
            raise SolError(f"model {model!r} does not support target {target!r}")
        space = dict(self.discovery.load(model).search_space(backend, target))
        if space.get("schema_version") != 1:
            raise SolError("plugin search space schema_version must be 1")
        if not isinstance(space.get("dimensions"), dict):
            raise SolError("plugin search space must contain a dimensions object")
        return space

    def doctor(self) -> Dict[str, Any]:
        items = self.models(include_drafts=True)
        plans = 0
        for info in items:
            if info.status != "released":
                continue
            for field, values in (
                ("references", info.references),
                ("backends", info.backends),
                ("targets", info.targets),
                ("presets", info.presets),
            ):
                if not values:
                    raise SolError(f"released model {info.id!r} has no {field}")
            self.discovery.load(info.id)
            for preset in info.presets:
                for target in info.targets:
                    self.inspect(info.id, preset, target)
                    plans += 1
        return {
            "healthy": True,
            "model_plugins": len(items),
            "released_plugins": sum(item.status == "released" for item in items),
            "validated_plans": plans,
            "message": "blank Engine is healthy" if not items else "all plugin contracts are valid",
        }

    def inspect(
        self,
        model: str,
        preset: str,
        target: str,
        arguments: Sequence[str] = (),
        options: Optional[Mapping[str, Any]] = None,
    ) -> ExecutionPlan:
        info = self.discovery.get(model)
        if info.status != "released":
            raise SolError(f"model {model!r} is draft and cannot be run")
        if preset not in info.presets:
            raise SolError(f"unknown preset {preset!r} for model {model!r}")
        if target not in info.targets:
            raise SolError(f"model {model!r} does not support target {target!r}")
        requested_options = dict(options or {})
        plan = self.discovery.load(model).build_plan(
            preset, target, requested_options, arguments
        )
        if (plan.model, plan.preset, plan.target) != (model, preset, target):
            raise SolError("plugin returned a plan for a different model, preset, or target")
        if plan.backend not in info.backends:
            raise SolError(f"plugin returned undeclared backend {plan.backend!r}")
        if requested_options:
            self._validate_options(
                requested_options,
                self.search_space(model, plan.backend, target),
            )
        if dict(plan.options) != requested_options:
            raise SolError("plugin did not preserve the requested optimization options")
        if not plan.command or not all(isinstance(item, str) and item for item in plan.command):
            raise SolError("plugin returned an empty or invalid command")
        return plan

    def run(
        self,
        model: str,
        preset: str,
        target: str,
        arguments: Sequence[str] = (),
        options: Optional[Mapping[str, Any]] = None,
    ) -> subprocess.CompletedProcess:
        plan = self.inspect(model, preset, target, arguments, options)
        environment = os.environ.copy()
        environment.update(plan.env)
        cwd = Path(plan.cwd).expanduser() if plan.cwd else None
        return subprocess.run(list(plan.command), cwd=cwd, env=environment, check=True)

    @staticmethod
    def _validate_options(options: Mapping[str, Any], space: Mapping[str, Any]) -> None:
        dimensions = space["dimensions"]
        unknown = sorted(set(options) - set(dimensions))
        if unknown:
            raise SolError(f"unknown optimization options: {', '.join(unknown)}")
        for key, value in options.items():
            spec = dimensions[key]
            if not isinstance(spec, dict):
                raise SolError(f"search dimension {key!r} must be an object")
            kind = spec.get("type")
            valid = {
                "bool": isinstance(value, bool),
                "int": isinstance(value, int) and not isinstance(value, bool),
                "float": isinstance(value, (int, float)) and not isinstance(value, bool),
                "string": isinstance(value, str),
                "categorical": value in spec.get("values", []),
            }.get(kind, False)
            if not valid:
                raise SolError(f"invalid value {value!r} for optimization option {key!r}")
            if kind in {"int", "float"}:
                if "min" in spec and value < spec["min"]:
                    raise SolError(f"optimization option {key!r} is below its minimum")
                if "max" in spec and value > spec["max"]:
                    raise SolError(f"optimization option {key!r} is above its maximum")
