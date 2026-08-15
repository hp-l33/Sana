from pathlib import Path
from typing import Any, Dict

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]


def load_toml(path: Path) -> Dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)
