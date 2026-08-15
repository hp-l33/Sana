import tempfile
import unittest
from pathlib import Path

from sol.discovery import PluginDiscovery
from sol.engine import Engine
from sol.errors import SolError


def write_manifest(root: Path, status: str = "released") -> None:
    directory = root / "demo"
    directory.mkdir()
    (directory / "plugin.toml").write_text(
        f'''schema_version = 1
id = "demo"
provider = "tests.fake_plugin:Plugin"
status = "{status}"
references = ["reference"]
backends = ["fake"]
targets = ["cpu"]
presets = ["balanced"]
''',
        encoding="utf-8",
    )


class EngineTests(unittest.TestCase):
    def test_space_and_plan_use_selected_plugin(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_manifest(root)
            engine = Engine(PluginDiscovery([root]))
            space = engine.search_space("demo", "fake", "cpu")
            self.assertEqual(space["target"], "cpu")
            plan = engine.inspect(
                "demo", "balanced", "cpu", ["extra"], {"cache.threshold": 0.15}
            )
            self.assertEqual(plan.command[-1], "extra")
            self.assertEqual(plan.options["cache.threshold"], 0.15)

    def test_draft_plugins_cannot_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_manifest(root, status="draft")
            engine = Engine(PluginDiscovery([root]))
            with self.assertRaisesRegex(SolError, "draft"):
                engine.inspect("demo", "balanced", "cpu")

    def test_unknown_target_fails_before_provider_load(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_manifest(root)
            engine = Engine(PluginDiscovery([root]))
            with self.assertRaisesRegex(SolError, "does not support target"):
                engine.search_space("demo", "fake", "gpu")

    def test_doctor_resolves_every_released_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_manifest(root)
            result = Engine(PluginDiscovery([root])).doctor()
            self.assertEqual(result["released_plugins"], 1)
            self.assertEqual(result["validated_plans"], 1)

    def test_unknown_or_out_of_range_options_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_manifest(root)
            engine = Engine(PluginDiscovery([root]))
            with self.assertRaisesRegex(SolError, "unknown optimization options"):
                engine.inspect("demo", "balanced", "cpu", options={"invented": True})
            with self.assertRaisesRegex(SolError, "above its maximum"):
                engine.inspect(
                    "demo", "balanced", "cpu", options={"cache.threshold": 0.9}
                )


if __name__ == "__main__":
    unittest.main()
