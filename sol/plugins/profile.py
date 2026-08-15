"""Model plugin backed by a versioned, model-owned profile."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sol import _toml
from sol.backend import BackendError

from sol.optimizations.spec import ModelSpec
from sol.optimizations.technique import Capability


_SEAM_CAPABILITIES: dict[str, tuple[Capability, ...]] = {
    "blocks": (Capability.BLOCKS, Capability.HAS_TRANSFORMER_BLOCKS),
    "kernel_fusion": (Capability.SUPPORTS_KERNEL_FUSION,),
    "step_cache": (Capability.SUPPORTS_STEP_CACHE, Capability.HAS_DENOISE_STEPS),
    "swappable_attention": (
        Capability.SWAPPABLE_ATTENTION,
        Capability.HAS_ATTENTION_LAYERS,
        Capability.HAS_ATTENTION_BACKEND_SWITCH,
    ),
    "ffn_precision": (
        Capability.SUPPORTS_NVFP4_LINEAR,
        Capability.HAS_FFN_LINEAR_MODULES,
    ),
    "prunable_tokens": (
        Capability.PRUNABLE_TOKENS,
        Capability.HAS_TOKEN_SEQUENCE_AXIS,
        Capability.SUPPORTS_TOKEN_GATHER_SCATTER,
    ),
    "teacache_signal": (Capability.SUPPORTS_STEP_CACHE,),
}


class ProfileModelPlugin:
    """Resolve capabilities only from model-owned, ``wired`` seam evidence.

    Preset requirements are intentionally not an input. This prevents the old
    tautology where a config could claim a capability and then pass validation
    because the dry-run copied that same claim into its synthetic ModelSpec.
    """

    def __init__(self, *, profile: str, repo_root: str | Path) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.profile_path = (self.repo_root / profile).resolve()
        try:
            self.profile_path.relative_to(self.repo_root)
        except ValueError as exc:
            raise ValueError(f"model profile escapes repository: {self.profile_path}") from exc
        if not self.profile_path.is_file():
            raise ValueError(f"model profile does not exist: {self.profile_path}")
        self.profile: dict[str, Any] = _toml.load(self.profile_path)

    @property
    def id(self) -> str:
        return str(self.profile.get("id", "")).strip()

    @property
    def display_name(self) -> str:
        return str(self.profile.get("display_name") or self.id)

    @property
    def plugin_root(self) -> Path:
        return self.profile_path.parent

    def preset_names(self) -> tuple[str, ...]:
        preset_dir = self.plugin_root / "presets"
        if not preset_dir.is_dir():
            return ()
        return tuple(path.stem for path in sorted(preset_dir.glob("*.toml")))

    def load_preset(self, name: str):
        from sol.preset import Preset, PresetError

        if not name or Path(name).name != name:
            raise PresetError(f"invalid preset name {name!r}")
        path = self.plugin_root / "presets" / f"{name}.toml"
        if not path.is_file():
            available = ", ".join(self.preset_names()) or "none"
            raise PresetError(
                f"unknown preset {self.id}:{name}; available for {self.id}: {available}"
            )
        return Preset.from_toml(path, model=self.id)

    def acceptance_path(self) -> Path | None:
        path = self.plugin_root / "acceptance.toml"
        return path if path.is_file() else None

    def default_launch(self) -> str:
        value = str(self.profile.get("default_launch", "")).strip()
        if not value:
            raise ValueError(f"model plugin {self.id!r} has no default_launch")
        return value

    def default_preview_stage(self) -> str:
        return str(self.profile.get("preview_stage", ""))

    def optimization_stages(
        self, optimization_id: str, *, backend: str = "auto"
    ) -> tuple[str, ...] | None:
        """Return the model-owned installation stages, or None when unsupported."""

        del optimization_id, backend
        return None

    def backend_names(self) -> tuple[str, ...]:
        """A legacy profile is evidence, not a released execution integration."""

        return ()

    def reference_names(self) -> tuple[str, ...]:
        return ()

    def reference(self, name: str):
        raise BackendError(
            f"model {self.id!r} is profile-only: it has no released semantic "
            f"reference named {name!r}"
        )

    def backend(self, name: str = "auto"):
        raise BackendError(
            f"model {self.id!r} is profile-only: it has no released backend or preset; "
            "add a model plugin under sol/plugins before tuning or execution"
        )

    def capabilities(self) -> frozenset[Capability]:
        raw = self.profile.get("seam_status", {})
        if not isinstance(raw, dict):
            return frozenset()
        capabilities: set[Capability] = set()
        for seam, status in raw.items():
            if str(status).strip().lower() not in {"wired", "verified"}:
                continue
            capabilities.update(_SEAM_CAPABILITIES.get(str(seam), ()))
        return frozenset(capabilities)

    def to_model_spec(self) -> ModelSpec:
        seam_status = self.profile.get("seam_status", {})
        return ModelSpec(
            name=str(self.profile.get("spec") or self.id),
            capabilities=self.capabilities(),
            seq_dim=1,
            extra={
                "source": "profile_seam_status",
                "profile": str(self.profile_path.relative_to(self.repo_root)),
                "seam_status": dict(seam_status) if isinstance(seam_status, dict) else {},
            },
        )
