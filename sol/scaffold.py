import json
from pathlib import Path
from typing import Dict, List

from .errors import AdaptationError


def scaffold_plugin(
    repo_root: Path, model: str, reference: str, backend: str, target: str
) -> List[str]:
    plugin_dir = repo_root / "sol" / "plugins" / model
    test_dir = repo_root / "tests" / "plugins" / model
    if plugin_dir.exists() or test_dir.exists():
        raise AdaptationError(f"refusing to overwrite an existing scaffold for {model!r}")
    if not (repo_root / "sol" / "plugins").is_dir():
        raise AdaptationError(f"{repo_root} is not a Sol Engine repository")

    plugin_dir.mkdir(parents=True)
    test_dir.mkdir(parents=True)
    values = {
        "model": json.dumps(model),
        "reference": json.dumps(reference),
        "backend": json.dumps(backend),
        "target": json.dumps(target),
    }
    files: Dict[Path, str] = {
        plugin_dir / "__init__.py": '"""Self-owned Sol plugin for ' + model + '."""\n',
        plugin_dir / "plugin.toml": (
            "schema_version = 1\n"
            f"id = {values['model']}\n"
            f"provider = \"sol.plugins.{model}.plugin:Plugin\"\n"
            'status = "draft"\n'
            f"references = [{values['reference']}]\n"
            f"backends = [{values['backend']}]\n"
            f"targets = [{values['target']}]\n"
            "presets = []\n"
        ),
        plugin_dir / "plugin.py": f'''from typing import Any, Mapping, Sequence

from sol.contracts import ExecutionPlan
from sol.errors import SolError


class Plugin:
    id = {values['model']}

    def search_space(self, backend: str, target: str) -> Mapping[str, Any]:
        if backend != {values['backend']} or target != {values['target']}:
            raise SolError("unsupported backend/target combination")
        return {{
            "schema_version": 1,
            "model": self.id,
            "backend": backend,
            "target": target,
            "dimensions": {{}},
            "constraints": ["dense-only until optimization seams are verified"],
        }}

    def build_plan(
        self,
        preset: str,
        target: str,
        options: Mapping[str, Any],
        arguments: Sequence[str],
    ) -> ExecutionPlan:
        raise SolError("no released preset has been implemented")
''',
        test_dir / "__init__.py": "",
        test_dir / "test_plugin.py": f'''import unittest

from sol.plugins.{model}.plugin import Plugin


class PluginContractTests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(Plugin().id, {values['model']})


if __name__ == "__main__":
    unittest.main()
''',
    }
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")
    return [str(path.relative_to(repo_root)) for path in files]
