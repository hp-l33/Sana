"""LTX-2.3 model contract plus backend selection."""

from __future__ import annotations

from sol.backend import BackendError
from sol.plugins.ltx23.backends import SGLangBackend
from sol.plugins.ltx23.references import DiffusersReference
from sol.plugins.profile import ProfileModelPlugin


class LTX23Plugin(ProfileModelPlugin):
    """Keep model semantics stable while execution backends evolve independently."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        model = str(self.profile.get("official_config", {}).get("model", self.id))
        self._references = {"diffusers": DiffusersReference(model=model)}
        self._backends = {"sglang": SGLangBackend()}

    def reference_names(self) -> tuple[str, ...]:
        return tuple(self._references)

    def reference(self, name: str):
        try:
            return self._references[name]
        except KeyError as exc:
            raise BackendError(
                f"unknown semantic reference {name!r} for {self.id}; available: "
                f"{', '.join(self.reference_names())}"
            ) from exc

    def backend_names(self) -> tuple[str, ...]:
        return tuple(self._backends)

    def backend(self, name: str = "auto"):
        selected = "sglang" if name == "auto" else name
        try:
            return self._backends[selected]
        except KeyError as exc:
            raise BackendError(
                f"unknown backend {name!r} for {self.id}; available: "
                f"{', '.join(self.backend_names())}"
            ) from exc

    def optimization_stages(
        self, optimization_id: str, *, backend: str = "auto"
    ) -> tuple[str, ...] | None:
        return self.backend(backend).optimization_stages(optimization_id)
