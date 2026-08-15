"""Model plugin contract: the unit maintained by people and adaptation agents."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from sol.preset import Preset


@runtime_checkable
class ModelPlugin(Protocol):
    """The complete integration boundary for one model family."""

    repo_root: Path

    @property
    def id(self) -> str: ...

    @property
    def display_name(self) -> str: ...

    def to_model_spec(self): ...

    def preset_names(self) -> tuple[str, ...]: ...

    def load_preset(self, name: str) -> Preset: ...

    def acceptance_path(self) -> Path | None: ...

    def reference_names(self) -> tuple[str, ...]: ...

    def reference(self, name: str): ...

    def backend_names(self) -> tuple[str, ...]: ...

    def backend(self, name: str = "auto"): ...

    def optimization_stages(
        self, optimization_id: str, *, backend: str = "auto"
    ) -> tuple[str, ...] | None: ...
