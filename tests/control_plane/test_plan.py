from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from types import MappingProxyType

from sol_engine.catalog import ProviderRef, builtin_catalog
from sol_engine.cli import _execution_metadata
from sol_engine.plan import PlanResolutionError, resolve_recipe
from sol_engine.recipe import OptimizationRequest, Recipe


ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "recipes" / "ltx23" / "fullopt.toml"


class PlanTests(unittest.TestCase):
    def test_ltx_fullopt_resolves_from_profile_capabilities(self):
        from sol_engine.recipe import Recipe

        plan = resolve_recipe(Recipe.from_toml(RECIPE), repo_root=ROOT)
        self.assertEqual(plan.model_id, "ltx23")
        self.assertEqual(plan.model_spec_source, "profile_seam_status")
        self.assertEqual(
            plan.transform_order,
            ("nvfp4_ffn", "kwl_fusions", "sparse_attention"),
        )
        self.assertEqual(plan.technique_order, ("token_prune", "step_cache"))
        self.assertIn("supports_kernel_fusion", plan.capabilities)
        self.assertIn("supports_step_cache", plan.capabilities)
        self.assertEqual(len(plan.fingerprint), 64)
        self.assertEqual(
            plan.env_preview["SGLANG_HQ_ENABLE_TE_NVFP4_FFN"], "1"
        )
        self.assertIn(
            "transformer_2=piecewise_attn",
            plan.env_preview["SGLANG_HQ_COMPONENT_ATTENTION_BACKENDS"],
        )
        self.assertEqual(
            plan.runtime_env["SGLANG_LTX2_STAGE1_CACHE_CORE_PRESET"],
            "8of15_last_29calls",
        )
        self.assertEqual(
            plan.runtime_env["SGLANG_LTX2_STAGE2_MIDPOINT_PRUNE_STEPS"], "1,2"
        )
        self.assertEqual(plan.runtime_env["SGLANG_LTX2_TE_NVFP4_VIDEO_FFN"], "1")
        self.assertTrue(plan.runtime_ready)

    def test_ltx_adapter_explicitly_disables_unselected_components(self):
        request = OptimizationRequest(
            id="step_cache",
            provider=ProviderRef.parse("techniques.methods.step_cache:StepCache"),
            params=MappingProxyType({"skip": "16-28"}),
            stages=("stage1",),
        )
        recipe = Recipe(
            schema_version=1,
            id="ltx-cache-only",
            model="ltx23",
            launch_config="config/ltx23/fullopt.toml",
            optimizations=(request,),
            preview_stage="stage2",
        )
        plan = resolve_recipe(recipe, repo_root=ROOT)
        self.assertEqual(plan.runtime_env["SGLANG_LTX2_STAGE1_CACHE_CORE_ENABLED"], "1")
        self.assertEqual(plan.runtime_env["SGLANG_LTX2_TE_NVFP4_VIDEO_FFN"], "0")
        self.assertEqual(plan.runtime_env["SGLANG_LTX2_STAGE2_MIDPOINT_PRUNE_RATIO"], "1.0")
        self.assertEqual(
            plan.runtime_env["SGLANG_HQ_COMPONENT_ATTENTION_BACKENDS"],
            "transformer=fa,transformer_2=fa",
        )

    def test_ltx_adapter_rejects_a_parameter_the_runtime_cannot_honor(self):
        request = OptimizationRequest(
            id="token_prune",
            provider=ProviderRef.parse("techniques.methods.token_prune:TokenPrune"),
            params=MappingProxyType(
                {
                    "keep_ratio": 0.5,
                    "method": "feat_norm",
                    "compensation": "zero",
                    "steps": "1-2",
                }
            ),
            stages=("stage2",),
        )
        recipe = Recipe(
            schema_version=1,
            id="ltx-unconsumed-parameter",
            model="ltx23",
            launch_config="config/ltx23/fullopt.toml",
            optimizations=(request,),
            preview_stage="stage2",
        )
        with self.assertRaisesRegex(PlanResolutionError, "compensation='prev'"):
            resolve_recipe(recipe, repo_root=ROOT)

    def test_recipe_cannot_grant_missing_model_capability(self):
        # Wan-5B currently has no model-owned [seam_status] evidence. Selecting
        # step_cache must fail even though the component asks for that capability.
        request = OptimizationRequest(
            id="step_cache",
            provider=ProviderRef.parse(
                "techniques.methods.step_cache:StepCache"
            ),
            params=MappingProxyType({"skip": "1-2"}),
            stages=("stage1",),
        )
        recipe = Recipe(
            schema_version=1,
            id="unsupported-wan-cache",
            model="wan22_ti2v_5b",
            launch_config="config/wan22_ti2v_5b/baseline.toml",
            optimizations=(request,),
        )
        with self.assertRaisesRegex(
            PlanResolutionError, "supports_step_cache.*not provided"
        ):
            resolve_recipe(recipe, catalog=builtin_catalog(), repo_root=ROOT)

    def test_recipe_provider_must_match_release_catalog(self):
        request = OptimizationRequest(
            id="step_cache",
            provider=ProviderRef.parse(
                "techniques.methods.teacache:TeaCache"
            ),
            params=MappingProxyType({}),
        )
        recipe = Recipe(
            schema_version=1,
            id="provider-confusion",
            model="ltx23",
            launch_config="config/ltx23/fullopt.toml",
            optimizations=(request,),
        )
        with self.assertRaisesRegex(PlanResolutionError, "provider mismatch"):
            resolve_recipe(recipe, repo_root=ROOT)

    def test_resolved_fingerprint_is_deterministic(self):
        from sol_engine.recipe import Recipe

        recipe = Recipe.from_toml(RECIPE)
        first = resolve_recipe(recipe, repo_root=ROOT)
        second = resolve_recipe(recipe, repo_root=ROOT)
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(first.to_json(), second.to_json())

    def test_execution_fingerprint_covers_user_overrides(self):
        plan = resolve_recipe(Recipe.from_toml(RECIPE), repo_root=ROOT)
        no_overrides, base = _execution_metadata(plan, [])
        overrides, changed = _execution_metadata(plan, ["SEED=7"])
        self.assertEqual(no_overrides, {})
        self.assertEqual(overrides, {"SEED": "7"})
        self.assertNotEqual(base, changed)

    def test_cli_plan_json(self):
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "sol_engine",
                "plan",
                str(RECIPE),
                "--json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('"fingerprint"', proc.stdout)
        self.assertIn('"profile_seam_status"', proc.stdout)


if __name__ == "__main__":
    unittest.main()
