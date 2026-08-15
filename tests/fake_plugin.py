from typing import Any, Mapping, Sequence

from sol.contracts import ExecutionPlan


class Plugin:
    id = "demo"

    def search_space(self, backend: str, target: str) -> Mapping[str, Any]:
        return {
            "schema_version": 1,
            "backend": backend,
            "target": target,
            "dimensions": {"cache.threshold": {"type": "float", "min": 0.1, "max": 0.2}},
        }

    def build_plan(
        self,
        preset: str,
        target: str,
        options: Mapping[str, Any],
        arguments: Sequence[str],
    ) -> ExecutionPlan:
        return ExecutionPlan(
            model=self.id,
            preset=preset,
            target=target,
            backend="fake",
            command=["python", "-c", "pass", *arguments],
            options=options,
            metadata={"tested": True},
        )
