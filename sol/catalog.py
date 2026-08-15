"""Immutable provider metadata and on-demand provider loading.

The catalog deliberately stores import references, never live Python objects.
Listing a catalog therefore has no model/optimization import side effects.  A
provider module is imported only after a caller explicitly selects its entry.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from sol import _toml


class CatalogError(ValueError):
    """Raised when catalog metadata is invalid or ambiguous."""


class ProviderLoadError(ImportError):
    """Raised when a selected provider cannot be imported or resolved."""


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


@dataclass(frozen=True)
class ProviderRef:
    """A canonical ``module:qualname`` reference."""

    module: str
    qualname: str

    @classmethod
    def parse(cls, raw: str) -> "ProviderRef":
        value = str(raw).strip()
        module, separator, qualname = value.partition(":")
        if not separator or not module or not qualname:
            raise CatalogError(
                f"provider must be a canonical 'module:qualname' reference, got {raw!r}"
            )
        if any(not part.isidentifier() for part in module.split(".")):
            raise CatalogError(f"invalid provider module in {raw!r}")
        if any(not part.isidentifier() for part in qualname.split(".")):
            raise CatalogError(f"invalid provider qualname in {raw!r}")
        return cls(module=module, qualname=qualname)

    @property
    def canonical(self) -> str:
        return f"{self.module}:{self.qualname}"

    def load(self) -> Any:
        try:
            obj: Any = importlib.import_module(self.module)
            for part in self.qualname.split("."):
                obj = getattr(obj, part)
            return obj
        except (ImportError, AttributeError) as exc:
            raise ProviderLoadError(
                f"cannot load provider {self.canonical!r}: {exc}"
            ) from exc


@dataclass(frozen=True)
class CatalogEntry:
    """One immutable, data-only catalog entry."""

    kind: str
    id: str
    provider: ProviderRef
    metadata: Mapping[str, Any]
    source: str

    def get(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)

    def load_provider(self) -> Any:
        return self.provider.load()

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "provider": self.provider.canonical,
            "source": self.source,
            **{key: _thaw(value) for key, value in self.metadata.items()},
        }


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return value


def _normalize_kind(kind: str) -> str:
    value = str(kind).strip().lower()
    aliases = {
        "model": "models",
        "models": "models",
        "optimization": "optimizations",
        "optimizations": "optimizations",
        "technique": "optimizations",
        "transform": "optimizations",
    }
    try:
        return aliases[value]
    except KeyError as exc:
        raise CatalogError(f"unknown catalog kind {kind!r}") from exc


class Catalog:
    """A scoped, immutable mapping from user-facing IDs to import metadata."""

    def __init__(self, entries: Iterable[CatalogEntry], *, source: str = "") -> None:
        by_kind: dict[str, dict[str, CatalogEntry]] = {
            "models": {},
            "optimizations": {},
        }
        for entry in entries:
            kind = _normalize_kind(entry.kind)
            if entry.id in by_kind[kind]:
                previous = by_kind[kind][entry.id]
                raise CatalogError(
                    f"duplicate {kind[:-1]} id {entry.id!r}: "
                    f"{previous.source} and {entry.source}"
                )
            by_kind[kind][entry.id] = entry
        self._entries = MappingProxyType(
            {kind: MappingProxyType(values) for kind, values in by_kind.items()}
        )
        self.source = source

    @classmethod
    def from_toml(cls, path: str | Path) -> "Catalog":
        catalog_path = Path(path).resolve()
        try:
            data = _toml.load(catalog_path)
        except (OSError, ValueError) as exc:
            raise CatalogError(f"cannot read catalog {catalog_path}: {exc}") from exc
        if data.get("schema_version") != 1:
            raise CatalogError(
                f"{catalog_path}: unsupported schema_version "
                f"{data.get('schema_version')!r}; expected 1"
            )
        entries: list[CatalogEntry] = []
        for kind in ("models", "optimizations"):
            table = data.get(kind, {})
            if not isinstance(table, dict):
                raise CatalogError(f"{catalog_path}: [{kind}] must be a table")
            for entry_id, raw in table.items():
                if not isinstance(raw, dict):
                    raise CatalogError(
                        f"{catalog_path}: [{kind}.{entry_id}] must be a table"
                    )
                provider = ProviderRef.parse(str(raw.get("provider", "")))
                metadata = {key: value for key, value in raw.items() if key != "provider"}
                entries.append(
                    CatalogEntry(
                        kind=kind,
                        id=str(entry_id),
                        provider=provider,
                        metadata=_freeze(metadata),
                        source=str(catalog_path),
                    )
                )
        return cls(entries, source=str(catalog_path))

    def entries(self, kind: str) -> tuple[CatalogEntry, ...]:
        normalized = _normalize_kind(kind)
        return tuple(self._entries[normalized][key] for key in sorted(self._entries[normalized]))

    def require(self, kind: str, entry_id: str) -> CatalogEntry:
        normalized = _normalize_kind(kind)
        try:
            return self._entries[normalized][str(entry_id)]
        except KeyError as exc:
            available = sorted(self._entries[normalized])
            raise CatalogError(
                f"unknown {normalized[:-1]} {entry_id!r}; available: {available}"
            ) from exc

    def merge(self, *others: "Catalog") -> "Catalog":
        entries: list[CatalogEntry] = []
        for catalog in (self, *others):
            entries.extend(catalog.entries("models"))
            entries.extend(catalog.entries("optimizations"))
        sources = ", ".join(c.source for c in (self, *others) if c.source)
        return Catalog(entries, source=sources)


def builtin_catalog() -> Catalog:
    """Load a fresh built-in catalog without creating global mutable state."""

    return Catalog.from_toml(Path(__file__).with_name("catalog.toml"))
