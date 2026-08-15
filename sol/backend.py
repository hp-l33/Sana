"""Execution backend boundary below model semantics and optimization APIs."""

from __future__ import annotations

from typing import Any, Iterable, Protocol, runtime_checkable


@runtime_checkable
class BackendAdapter(Protocol):
    name: str
    role: str
    executable: bool

    def optimization_stages(self, optimization_id: str) -> tuple[str, ...] | None: ...

    def render_runtime_env(
        self,
        selected: Iterable[tuple[Any, Any]],
        generic_env: dict[str, str],
    ) -> dict[str, str]: ...


class BackendError(ValueError):
    """Raised when a model/backend pair cannot satisfy a requested operation."""
