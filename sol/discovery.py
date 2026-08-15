import importlib
import inspect
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from ._toml import load_toml
from .contracts import ModelInfo, ModelPlugin
from .errors import DiscoveryError

MODEL_ID = re.compile(r"^[a-z][a-z0-9_]*$")


def default_plugin_roots() -> List[Path]:
    roots = [Path(__file__).resolve().parent / "plugins"]
    extra = os.environ.get("SOL_PLUGIN_PATH", "")
    roots.extend(Path(item).expanduser() for item in extra.split(os.pathsep) if item)
    return roots


def _strings(data: object, field: str, path: Path) -> tuple:
    if not isinstance(data, list) or not all(isinstance(item, str) and item for item in data):
        raise DiscoveryError(f"{path}: {field} must be a list of non-empty strings")
    return tuple(data)


def read_manifest(path: Path) -> ModelInfo:
    try:
        data = load_toml(path)
    except (OSError, ValueError) as exc:
        raise DiscoveryError(f"cannot read {path}: {exc}") from exc

    if data.get("schema_version") != 1:
        raise DiscoveryError(f"{path}: schema_version must be 1")
    model_id = data.get("id")
    provider = data.get("provider")
    status = data.get("status")
    if not isinstance(model_id, str) or not MODEL_ID.fullmatch(model_id):
        raise DiscoveryError(f"{path}: invalid model id {model_id!r}")
    if path.parent.name != model_id:
        raise DiscoveryError(f"{path}: id must match directory name {path.parent.name!r}")
    if not isinstance(provider, str) or provider.count(":") != 1:
        raise DiscoveryError(f"{path}: provider must be 'module:attribute'")
    if status not in {"draft", "released"}:
        raise DiscoveryError(f"{path}: status must be 'draft' or 'released'")

    return ModelInfo(
        id=model_id,
        provider=provider,
        status=status,
        references=_strings(data.get("references", []), "references", path),
        backends=_strings(data.get("backends", []), "backends", path),
        targets=_strings(data.get("targets", []), "targets", path),
        presets=_strings(data.get("presets", []), "presets", path),
        manifest=path.resolve(),
    )


class PluginDiscovery:
    """Data-only discovery. Providers are imported only after explicit selection."""

    def __init__(self, roots: Optional[Sequence[Path]] = None):
        self.roots = list(roots) if roots is not None else default_plugin_roots()

    def manifests(self) -> List[ModelInfo]:
        found: Dict[str, ModelInfo] = {}
        for root in self.roots:
            if not root.is_dir():
                continue
            for path in sorted(root.glob("*/plugin.toml")):
                info = read_manifest(path)
                if info.id in found:
                    raise DiscoveryError(
                        f"duplicate model id {info.id!r}: {found[info.id].manifest} and {path}"
                    )
                found[info.id] = info
        return [found[key] for key in sorted(found)]

    def get(self, model_id: str) -> ModelInfo:
        matches = {item.id: item for item in self.manifests()}
        try:
            return matches[model_id]
        except KeyError as exc:
            known = ", ".join(matches) or "none"
            raise DiscoveryError(f"unknown model {model_id!r}; available: {known}") from exc

    def load(self, model_id: str) -> ModelPlugin:
        info = self.get(model_id)
        module_name, attribute = info.provider.split(":", 1)
        try:
            value = getattr(importlib.import_module(module_name), attribute)
            plugin = value() if inspect.isclass(value) else value
        except (ImportError, AttributeError, TypeError) as exc:
            raise DiscoveryError(f"cannot load provider {info.provider!r}: {exc}") from exc
        if getattr(plugin, "id", None) != info.id:
            raise DiscoveryError(
                f"provider {info.provider!r} declares id {getattr(plugin, 'id', None)!r}, "
                f"expected {info.id!r}"
            )
        for method in ("search_space", "build_plan"):
            if not callable(getattr(plugin, method, None)):
                raise DiscoveryError(f"provider {info.provider!r} is missing {method}()")
        return plugin
