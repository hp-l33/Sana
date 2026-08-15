from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from sol.catalog import Catalog, CatalogError, ProviderRef, builtin_catalog


ROOT = Path(__file__).resolve().parents[2]


class CatalogTests(unittest.TestCase):
    def test_catalog_listing_does_not_import_providers(self):
        code = """
import sys
from sol.catalog import builtin_catalog
catalog = builtin_catalog()
assert len(catalog.entries('models')) == 10
assert len(catalog.entries('optimizations')) == 8
assert 'sol.plugins.ltx23' not in sys.modules
assert 'sol.optimizations.methods.token_prune' not in sys.modules
assert 'sol.optimizations.transforms.sparse_attention' not in sys.modules
print('ok')
"""
        proc = subprocess.run(
            [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "ok")

    def test_selected_provider_is_loaded_on_demand(self):
        code = """
import sys
from sol.catalog import builtin_catalog
entry = builtin_catalog().require('optimizations', 'step_cache')
assert 'sol.optimizations.methods.step_cache' not in sys.modules
provider = entry.load_provider()
assert provider.__name__ == 'StepCache'
assert 'sol.optimizations.methods.step_cache' in sys.modules
assert 'sol.optimizations.methods.token_prune' not in sys.modules
print('ok')
"""
        proc = subprocess.run(
            [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "ok")

    def test_catalog_merge_rejects_name_collisions(self):
        catalog = builtin_catalog()
        with self.assertRaisesRegex(CatalogError, "duplicate model id"):
            catalog.merge(catalog)

    def test_scoped_catalog_adds_alias_without_global_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "extension.toml"
            path.write_text(
                "schema_version = 1\n"
                "[optimizations.local_cache]\n"
                "kind = 'runtime_technique'\n"
                "provider = 'sol.optimizations.methods.step_cache:StepCache'\n"
            )
            base = builtin_catalog()
            merged = base.merge(Catalog.from_toml(path))
            self.assertEqual(
                merged.require("optimizations", "local_cache").provider.canonical,
                "sol.optimizations.methods.step_cache:StepCache",
            )
            with self.assertRaises(CatalogError):
                base.require("optimizations", "local_cache")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "sol",
                    "--catalog",
                    str(path),
                    "optimizations",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("local_cache", proc.stdout)

    def test_provider_reference_requires_canonical_form(self):
        with self.assertRaisesRegex(CatalogError, "module:qualname"):
            ProviderRef.parse("TokenPrune")

    def test_python39_fallback_parser_handles_catalog_and_preset_shape(self):
        # Exercise the bundled subset parser directly even on Python 3.11+.
        from sol import _toml

        parsed = _toml.loads(
            """
schema_version = 1
[[optimization]]
id = "cache"
stages = ["stage1", "stage2"]
[optimization.options]
threshold = 0.1
enabled = true
"""
        )
        self.assertEqual(parsed["optimization"][0]["options"]["threshold"], 0.1)
        self.assertTrue(parsed["optimization"][0]["options"]["enabled"])

    def test_python39_fallback_parser_handles_runtime_metadata(self):
        from sol import _toml

        parsed = _toml.loads(
            '''
note = """line one
line two"""
[cache]
policy = { "500" = { block = [2], skip_count = 2 } }
'''
        )
        self.assertEqual(parsed["note"], "line one\nline two")
        self.assertEqual(parsed["cache"]["policy"]["500"]["block"], [2])

    def test_invalid_catalog_provider_is_rejected_without_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalog.toml"
            path.write_text(
                "schema_version = 1\n[models.bad]\nprovider = 'not-canonical'\n"
            )
            with self.assertRaises(CatalogError):
                Catalog.from_toml(path)


if __name__ == "__main__":
    unittest.main()
