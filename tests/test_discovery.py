import tempfile
import unittest
from pathlib import Path

from sol.discovery import PluginDiscovery
from sol.errors import DiscoveryError


MANIFEST = """\
schema_version = 1
id = "demo"
provider = "does.not.exist:Plugin"
status = "draft"
references = ["reference"]
backends = ["backend"]
targets = ["target"]
presets = []
"""


class DiscoveryTests(unittest.TestCase):
    def test_manifest_discovery_does_not_import_provider(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "demo"
            directory.mkdir()
            (directory / "plugin.toml").write_text(MANIFEST, encoding="utf-8")
            items = PluginDiscovery([root]).manifests()
            self.assertEqual([item.id for item in items], ["demo"])

    def test_duplicate_ids_fail_closed(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            for root in (Path(first), Path(second)):
                directory = root / "demo"
                directory.mkdir()
                (directory / "plugin.toml").write_text(MANIFEST, encoding="utf-8")
            with self.assertRaisesRegex(DiscoveryError, "duplicate model id"):
                PluginDiscovery([Path(first), Path(second)]).manifests()

    def test_directory_is_the_identity_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "wrong"
            directory.mkdir()
            (directory / "plugin.toml").write_text(MANIFEST, encoding="utf-8")
            with self.assertRaisesRegex(DiscoveryError, "must match directory"):
                PluginDiscovery([Path(temporary)]).manifests()


if __name__ == "__main__":
    unittest.main()
