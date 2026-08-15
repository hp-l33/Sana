from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Protocol, Sequence, Tuple


@dataclass(frozen=True)
class ModelInfo:
    id: str
    provider: str
    status: str
    references: Tuple[str, ...]
    backends: Tuple[str, ...]
    targets: Tuple[str, ...]
    presets: Tuple[str, ...]
    manifest: Path

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "references": list(self.references),
            "backends": list(self.backends),
            "targets": list(self.targets),
            "presets": list(self.presets),
            "manifest": str(self.manifest),
        }


@dataclass(frozen=True)
class ExecutionPlan:
    model: str
    preset: str
    target: str
    backend: str
    command: Sequence[str]
    options: Mapping[str, Any] = field(default_factory=dict)
    env: Mapping[str, str] = field(default_factory=dict)
    cwd: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "preset": self.preset,
            "target": self.target,
            "backend": self.backend,
            "command": list(self.command),
            "options": dict(self.options),
            "env": dict(self.env),
            "cwd": self.cwd,
            "metadata": dict(self.metadata),
        }


class ModelPlugin(Protocol):
    id: str

    def search_space(self, backend: str, target: str) -> Mapping[str, Any]:
        """Return the bounded, target-legal technique space."""

    def build_plan(
        self,
        preset: str,
        target: str,
        options: Mapping[str, Any],
        arguments: Sequence[str],
    ) -> ExecutionPlan:
        """Resolve one published preset into an inspectable execution plan."""
