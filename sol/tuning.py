"""Internal tuning view derived from selected optimization implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sol.catalog import Catalog
from sol.plan import ExecutionPlan


@dataclass(frozen=True)
class SearchSpace:
    subject: str
    parameters: dict[str, dict[str, dict[str, Any]]]

    @classmethod
    def from_plan(cls, plan: ExecutionPlan, *, catalog: Catalog) -> "SearchSpace":
        result: dict[str, dict[str, dict[str, Any]]] = {}
        for selected in plan.optimizations:
            provider = catalog.require("optimizations", selected.id).load_provider()
            axes = getattr(provider, "parameters", {})
            result[selected.id] = {
                name: parameter.as_dict()
                for name, parameter in sorted(axes.items())
            }
        return cls(plan.preset_id, result)

    @classmethod
    def from_model(
        cls, plugin, *, backend: str = "auto", catalog: Catalog
    ) -> "SearchSpace":
        spec = plugin.to_model_spec()
        adapter = plugin.backend(backend)
        result: dict[str, dict[str, dict[str, Any]]] = {}
        for entry in catalog.entries("optimizations"):
            stages = adapter.optimization_stages(entry.id)
            if stages is None:
                continue
            provider = entry.load_provider()
            required = getattr(provider, "required_capabilities", frozenset())
            if spec.missing(required):
                continue
            axes = {
                name: parameter.as_dict()
                for name, parameter in sorted(getattr(provider, "parameters", {}).items())
            }
            axes["$integration"] = {
                "kind": "model_integration",
                "stages": list(stages),
            }
            result[entry.id] = axes
        return cls(f"{plugin.id}@{adapter.name}", result)

    def as_dict(self) -> dict[str, object]:
        return {"subject": self.subject, "optimizations": self.parameters}
