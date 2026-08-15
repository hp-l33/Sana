from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from sol import Engine
from sol.evaluation import AcceptanceSpec
from sol.preset import PresetError


ROOT = Path(__file__).resolve().parents[2]


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = Engine(repo_root=ROOT)

    def test_released_ltx_preset_resolves_deterministically(self):
        first = self.engine.inspect("ltx23:fullopt")
        second = self.engine.inspect("ltx23:fullopt")
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(first.to_json(), second.to_json())
        self.assertEqual(first.backend, "sglang")
        self.assertEqual(
            first.transform_order,
            ("nvfp4_ffn", "kwl_fusions", "sparse_attention"),
        )
        self.assertEqual(first.runtime_order, ("token_prune", "step_cache"))
        self.assertEqual(
            first.runtime_env["SGLANG_LTX2_STAGE1_CACHE_CORE_PRESET"],
            "8of15_last_29calls",
        )
        self.assertTrue(first.runtime_ready)

    def test_baseline_is_a_first_class_same_backend_preset(self):
        plan = self.engine.inspect("ltx23:baseline")
        self.assertEqual(plan.backend, "sglang")
        self.assertEqual(plan.optimizations, ())
        self.assertEqual(plan.transform_order, ())
        self.assertEqual(plan.runtime_order, ())
        self.assertEqual(plan.runtime_env["SGLANG_LTX2_TE_NVFP4_VIDEO_FFN"], "0")
        self.assertEqual(plan.runtime_env["SGLANG_LTX2_STAGE1_CACHE_CORE_ENABLED"], "0")
        self.assertTrue(plan.runtime_ready)

    def test_model_release_status_is_discoverable_without_loading_plugin(self):
        models = {model.id: model for model in self.engine.models()}
        self.assertEqual(models["ltx23"].status, "released")
        self.assertEqual(models["ltx23"].references, ("diffusers",))
        self.assertEqual(models["ltx23"].backends, ("sglang",))
        self.assertEqual(models["ltx23"].presets, ("baseline", "fullopt"))
        self.assertEqual(models["cosmos3"].status, "profile_only")
        self.assertEqual(models["cosmos3"].backends, ())

    def test_semantic_reference_is_not_misrepresented_as_execution_backend(self):
        reference = self.engine.reference("ltx23")
        self.assertEqual(reference.framework, "diffusers")
        self.assertEqual(reference.role, "semantic_reference")
        self.assertEqual(reference.model, "Lightricks/LTX-2.3")
        with self.assertRaisesRegex(ValueError, "unknown backend 'diffusers'"):
            self.engine.space("ltx23", backend="diffusers")

    def test_profile_only_model_cannot_masquerade_as_release(self):
        with self.assertRaisesRegex(ValueError, "profile-only"):
            self.engine.space("cosmos3")

    def test_model_space_hides_unintegrated_optimizations(self):
        space = self.engine.space("ltx23", backend="sglang").as_dict()
        optimizations = space["optimizations"]
        self.assertEqual(
            set(optimizations),
            {
                "kwl_fusions",
                "nvfp4_ffn",
                "sparse_attention",
                "step_cache",
                "token_prune",
            },
        )
        self.assertNotIn("teacache", optimizations)
        self.assertEqual(
            optimizations["step_cache"]["$integration"]["stages"], ["stage1"]
        )
        self.assertEqual(
            optimizations["token_prune"]["keep_ratio"]["kind"], "float"
        )

    def test_builder_is_shared_user_agent_composition_api(self):
        candidate = (
            self.engine.optimize("ltx23", backend="sglang")
            .use("step_cache", skip="16-28")
            .preset()
        )
        plan = self.engine.inspect(candidate)
        self.assertEqual(plan.preset_id, "ltx23:candidate")
        self.assertEqual(plan.runtime_order, ("step_cache",))
        self.assertEqual(plan.runtime_env["SGLANG_LTX2_TE_NVFP4_VIDEO_FFN"], "0")
        self.assertEqual(self.engine.run(candidate, dry_run=True).status, "planned")

    def test_builder_rejects_backend_or_model_knowledge_leakage(self):
        with self.assertRaisesRegex(PresetError, "not integrated"):
            self.engine.optimize("ltx23", backend="sglang").use("teacache")
        with self.assertRaisesRegex(PresetError, "stages are model-owned"):
            self.engine.optimize("ltx23", backend="sglang").use(
                "step_cache", stages=("stage2",), skip="16-28"
            )
        with self.assertRaisesRegex(ValueError, "unknown backend 'diffusers'"):
            self.engine.optimize("ltx23", backend="diffusers")

    def test_plugin_rejects_runtime_parameter_it_cannot_honor(self):
        builder = self.engine.optimize("ltx23", backend="sglang").use(
            "token_prune",
            keep_ratio=0.5,
            method="feat_norm",
            compensation="zero",
            steps="1-2",
        )
        with self.assertRaisesRegex(ValueError, "compensation='prev'"):
            builder.inspect()

    def test_dry_run_is_side_effect_free_unless_persist_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "runs"
            run = self.engine.run(
                "ltx23:fullopt", dry_run=True, run_root=root
            )
            self.assertEqual(run.status, "planned")
            self.assertFalse(root.exists())
            record = Path(tmp) / "record.json"
            self.engine.run(
                "ltx23:fullopt",
                dry_run=True,
                run_root=root,
                persist=record,
            )
            self.assertTrue(record.is_file())
            self.assertFalse(root.exists())

    def test_acceptance_is_fail_closed(self):
        path = ROOT / "sol" / "plugins" / "ltx23" / "acceptance.toml"
        spec = AcceptanceSpec.from_toml(path)
        failed = spec.evaluate({})
        self.assertFalse(failed.passed)
        evidence = {
            "artifacts": spec.required_artifacts,
            "official_config_matches": True,
            "speedup": spec.min_speedup,
            "warmup_complete": True,
            "quality_passed": True,
        }
        self.assertTrue(spec.evaluate(evidence).passed)

    def test_cli_product_surface(self):
        commands = (
            ("models",),
            ("models", "--json"),
            ("presets",),
            ("space", "ltx23", "--backend", "sglang"),
            ("inspect", "ltx23:fullopt", "--json"),
            ("run", "ltx23:fullopt", "--dry-run"),
            ("doctor",),
        )
        for args in commands:
            with self.subTest(args=args):
                process = subprocess.run(
                    [sys.executable, "-m", "sol", *args],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(process.returncode, 0, process.stderr)

    def test_invalid_cli_target_fails_clearly(self):
        process = subprocess.run(
            [sys.executable, "-m", "sol", "inspect", "ltx23:missing"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(process.returncode, 2)
        self.assertIn("unknown preset", process.stderr)


class ArchitectureTests(unittest.TestCase):
    def test_optimization_library_has_no_control_plane_dependency(self):
        root = ROOT / "sol" / "optimizations"
        offenders = []
        for path in root.rglob("*.py"):
            text = path.read_text()
            for line_number, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith(("from sol ", "import sol ")):
                    offenders.append(f"{path.relative_to(ROOT)}:{line_number}")
        self.assertEqual(offenders, [])

    def test_there_is_one_public_namespace_and_no_global_workflow_schemas(self):
        for stale in ("sol_engine", "techniques", "recipes", "search", "search_space"):
            self.assertFalse((ROOT / stale).exists(), stale)
        self.assertFalse(hasattr(Engine, "tuning_space"))
        self.assertNotIn(
            "ProfileModelAdapter", (ROOT / "sol/plugins/profile.py").read_text()
        )
        self.assertNotIn(
            "LTX23Adapter", (ROOT / "sol/plugins/ltx23/plugin.py").read_text()
        )

    def test_provider_discovery_has_no_registration_api(self):
        optimization_root = ROOT / "sol" / "optimizations"
        self.assertFalse((optimization_root / "registry.py").exists())
        offenders = []
        for path in optimization_root.rglob("*.py"):
            text = path.read_text()
            if "@register_" in text or "def register_technique" in text:
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
