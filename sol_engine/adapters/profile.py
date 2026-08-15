"""Model capability adapter backed by a versioned model profile."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sol_engine import _toml

from techniques.spec import ModelSpec
from techniques.technique import Capability


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


class ProfileModelAdapter:
    """Resolve capabilities only from model-owned, ``wired`` seam evidence.

    Recipe requirements are intentionally not an input. This prevents the old
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
