"""LTX-2.3 release adapter: capability evidence plus runtime env compilation."""

from __future__ import annotations

from typing import Any, Iterable

from sol_engine.adapters.profile import ProfileModelAdapter


_KWL_RUNTIME_FLAGS = {
    "SHARE_BLOCK0_SELF_ATTN": "SGLANG_LTX2_SHARE_BLOCK0_SELF_ATTN",
    "SHARE_GUIDANCE_PREFIX": "SGLANG_LTX2_SHARE_GUIDANCE_PREFIX",
    "FUSED_QK_ROPE": "SGLANG_LTX2_FUSED_QK_ROPE",
    "FUSED_RMS_ADALN": "SGLANG_LTX2_FUSED_RMS_ADALN",
    "FUSED_ADALN": "SGLANG_LTX2_FUSED_ADALN",
    "FUSED_QKNORM_ROPE": "SGLANG_LTX2_FUSED_QKNORM_ROPE",
    "FUSED_DUAL_MODULATE": "SGLANG_LTX2_FUSED_DUAL_MODULATE",
    "FUSED_CA_DUAL_MODULATE": "SGLANG_LTX2_FUSED_CA_DUAL_MODULATE",
    "FUSED_ADA_VALUES_ALL": "SGLANG_LTX2_FUSED_ADA_VALUES_ALL",
    "FUSED_RESIDUAL_GATE": "SGLANG_LTX2_FUSED_RESIDUAL_GATE",
    "FUSED_FFN_PROJ_IN_GELU": "SGLANG_LTX2_FUSED_FFN_PROJ_IN_GELU",
    "COMPILE_GATE_TO_OUT": "SGLANG_LTX2_COMPILE_GATE_TO_OUT",
    "FUSED_AUDIO_QKVG": "SGLANG_LTX2_FUSED_AUDIO_QKVG",
    "ENABLE_FUSED_QKNORM_ROPE": "SGLANG_ENABLE_FUSED_QKNORM_ROPE",
    "COMPILE_TILED_VAE": "SGLANG_LTX2_COMPILE_TILED_VAE_DECODER",
}

_EXPECTED_STAGES = {
    "kwl_fusions": {"stage1", "stage2"},
    "nvfp4_ffn": {"stage1", "stage2"},
    "sparse_attention": {"stage2"},
    "step_cache": {"stage1"},
    "token_prune": {"stage2"},
}


def _bool(value: Any) -> str:
    return "1" if bool(value) else "0"


def _require_only(request: Any, allowed: set[str]) -> None:
    unsupported = sorted(set(request.params) - allowed)
    if unsupported:
        raise ValueError(
            f"LTX-2.3 {request.id!r} has no runtime mapping for params {unsupported}"
        )


class LTX23Adapter(ProfileModelAdapter):
    """Compile a selected generic plan into the env consumed by LTX-2.3.

    The optimized arm defaults every historical component on. Therefore this
    adapter emits explicit OFF values first and enables only recipe-selected
    components. Removing an item from a recipe now removes it from execution.
    """

    def render_runtime_env(
        self,
        selected: Iterable[tuple[Any, Any]],
        generic_env: dict[str, str],
    ) -> dict[str, str]:
        env = dict(generic_env)
        env.update(
            {
                "SGLANG_LTX2_STAGE1_CACHE_CORE_ENABLED": "0",
                "SGLANG_HQ_COMPONENT_ATTENTION_BACKENDS": (
                    "transformer=fa,transformer_2=fa"
                ),
                "SGLANG_LTX2_TE_NVFP4_VIDEO_FFN": "0",
                "SGLANG_LTX2_STAGE2_MIDPOINT_PRUNE_RATIO": "1.0",
            }
        )
        env.update({runtime_key: "0" for runtime_key in _KWL_RUNTIME_FLAGS.values()})

        for request, item in selected:
            expected_stages = _EXPECTED_STAGES.get(request.id)
            actual_stages = set(request.stages)
            if expected_stages is None:
                raise ValueError(f"LTX-2.3 has no runtime mapping for {request.id!r}")
            if actual_stages != expected_stages:
                raise ValueError(
                    f"LTX-2.3 {request.id!r} must target stages "
                    f"{sorted(expected_stages)}, got {sorted(actual_stages)}"
                )

            if request.id == "kwl_fusions":
                _require_only(request, {"kwl_adapter", "flags"})
                if getattr(item, "kwl_adapter", "") != "ltx2":
                    raise ValueError("LTX-2.3 kwl_fusions requires kwl_adapter='ltx2'")
                for flag in item.flags:
                    try:
                        env[_KWL_RUNTIME_FLAGS[flag]] = "1"
                    except KeyError as exc:
                        raise ValueError(f"unsupported LTX-2.3 KWL flag {flag!r}") from exc
            elif request.id == "nvfp4_ffn":
                _require_only(
                    request,
                    {
                        "module_scope",
                        "disable_rht",
                        "disable_stochastic_rounding",
                        "disable_2d_quantization",
                        "fused_proj_in_gelu",
                        "fused_proj_out_bias_gate",
                        "pad_m_to",
                    },
                )
                if item.module_scope != "video_ffn":
                    raise ValueError("LTX-2.3 NVFP4 supports module_scope='video_ffn'")
                env.update(
                    {
                        "SGLANG_LTX2_TE_NVFP4_VIDEO_FFN": "1",
                        "SGLANG_LTX2_TE_NVFP4_DISABLE_RHT": _bool(item.disable_rht),
                        "SGLANG_LTX2_TE_NVFP4_DISABLE_STOCHASTIC_ROUNDING": _bool(
                            item.disable_stochastic_rounding
                        ),
                        "SGLANG_LTX2_TE_NVFP4_DISABLE_2D_QUANTIZATION": _bool(
                            item.disable_2d_quantization
                        ),
                        "SGLANG_LTX2_TE_NVFP4_FUSED_PROJ_IN_GELU": _bool(
                            item.fused_proj_in_gelu
                        ),
                        "SGLANG_LTX2_TE_NVFP4_FUSED_PROJ_OUT_BIAS_GATE": _bool(
                            item.fused_proj_out_bias_gate
                        ),
                        "SGLANG_LTX2_TE_NVFP4_PAD_M_TO": str(item.pad_m_to),
                    }
                )
            elif request.id == "sparse_attention":
                _require_only(
                    request,
                    {
                        "sparsity",
                        "block_size",
                        "frame_size",
                        "only_video_self",
                        "component",
                        "stage1_dense",
                        "dense_steps",
                        "route_mode",
                        "route_bias",
                        "allow_qk_mismatch",
                        "allow_gqa",
                        "dense_fallback",
                        "stage2_dense_layers",
                        "backend",
                    },
                )
                if item.component != "transformer_2" or item.backend != "piecewise_attn":
                    raise ValueError(
                        "LTX-2.3 sparse attention requires "
                        "component='transformer_2' and backend='piecewise_attn'"
                    )
                if item.stage1_dense or item.dense_steps:
                    raise ValueError(
                        "LTX-2.3 sparse_attention is verified for stage2 only; "
                        "stage1_dense must be false and dense_steps must be 0"
                    )
                env.update(
                    {
                        "SGLANG_HQ_COMPONENT_ATTENTION_BACKENDS": (
                            "transformer=fa,transformer_2=piecewise_attn"
                        ),
                        "SGLANG_PIECEWISE_ATTN_SPARSITY": str(item.sparsity),
                        "SGLANG_PIECEWISE_ATTN_BLOCK_SIZE": str(item.block_size),
                        "SGLANG_PIECEWISE_ATTN_FRAME_SIZE": str(item.frame_size),
                        "SGLANG_PIECEWISE_ATTN_ONLY_VIDEO_SELF": str(
                            item.only_video_self
                        ).lower(),
                        "SGLANG_PIECEWISE_ATTN_STAGE1_SCHEDULE": str(
                            item.stage1_dense
                        ).lower(),
                        "SGLANG_PIECEWISE_ATTN_STAGE1_DENSE_STEPS": str(
                            item.dense_steps
                        ),
                        "SGLANG_PIECEWISE_ATTN_STAGE2_DENSE_LAYERS": str(
                            item.stage2_dense_layers
                        ),
                        "SGLANG_PIECEWISE_ATTN_ROUTE_MODE": str(item.route_mode),
                        "SGLANG_PIECEWISE_ATTN_ROUTE_BIAS": str(
                            item.route_bias
                        ).lower(),
                        "SGLANG_PIECEWISE_ATTN_ALLOW_QK_MISMATCH": str(
                            item.allow_qk_mismatch
                        ).lower(),
                        "SGLANG_PIECEWISE_ATTN_ALLOW_GQA": str(
                            item.allow_gqa
                        ).lower(),
                        "SGLANG_PIECEWISE_ATTN_DENSE_FALLBACK": str(
                            item.dense_fallback
                        ),
                    }
                )
            elif request.id == "step_cache":
                _require_only(request, {"skip", "delta_scale"})
                skip = str(request.params.get("skip", ""))
                delta_scale = float(request.params.get("delta_scale", 0.0))
                if skip != "16-28" or delta_scale != 0.0:
                    raise ValueError(
                        "LTX-2.3 runtime maps only skip='16-28', delta_scale=0 "
                        "to the verified 8of15_last_29calls preset"
                    )
                env.update(
                    {
                        "SGLANG_LTX2_STAGE1_CACHE_CORE_ENABLED": "1",
                        "SGLANG_LTX2_STAGE1_CACHE_CORE_PRESET": (
                            "8of15_last_29calls"
                        ),
                    }
                )
            elif request.id == "token_prune":
                _require_only(
                    request, {"keep_ratio", "method", "compensation", "steps"}
                )
                steps = str(request.params.get("steps", ""))
                if steps != "1-2":
                    raise ValueError("LTX-2.3 token_prune currently supports steps='1-2'")
                if str(request.params.get("compensation", "prev")) != "prev":
                    raise ValueError(
                        "LTX-2.3 token_prune currently supports compensation='prev'"
                    )
                ratio = float(request.params.get("keep_ratio", 1.0))
                if not 0.0 < ratio <= 1.0:
                    raise ValueError("LTX-2.3 token_prune keep_ratio must be in (0, 1]")
                env.update(
                    {
                        "SGLANG_LTX2_STAGE2_MIDPOINT_PRUNE_RATIO": str(ratio),
                        "SGLANG_LTX2_STAGE2_MIDPOINT_PRUNE_METHOD": str(
                            request.params.get("method", "feat_norm")
                        ),
                        "SGLANG_LTX2_STAGE2_MIDPOINT_PRUNE_STEPS": steps.replace(
                            "-", ","
                        ),
                    }
                )
        return dict(sorted(env.items()))
