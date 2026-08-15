"""Compatibility facade over the immutable, lazy Sol-Engine catalog.

Historically this module owned three process-global dictionaries populated by
decorator/import side effects. Built-ins now resolve through data-only catalog
entries. The old decorators remain identity decorators so existing provider
modules keep importing, but they no longer mutate process-global state.
"""

from __future__ import annotations

from typing import Callable

from sol_engine.catalog import CatalogError, ProviderRef, builtin_catalog
from techniques.spec import ModelSpec
from techniques.technique import Technique


def register_technique(name: str):
    """Deprecated identity decorator; publish providers in catalog.toml."""

    del name

    def deco(factory: Callable[..., Technique]):
        return factory

    return deco


def register_transform(name: str):
    """Deprecated identity decorator; publish providers in catalog.toml."""

    del name

    def deco(factory: Callable[..., object]):
        return factory

    return deco


def register_model_spec(*keys: str):
    """Deprecated identity decorator; model specs now come from adapters."""

    del keys

    def deco(factory: Callable[[], ModelSpec]):
        return factory

    return deco


def _optimization_entry(name: str, expected_kind: str):
    entry = builtin_catalog().require("optimizations", name)
    actual = str(entry.get("kind", ""))
    if actual != expected_kind:
        raise KeyError(
            f"optimization {name!r} is {actual!r}, not {expected_kind!r}"
        )
    return entry


def build_transform(name: str, **kwargs):
    try:
        provider = _optimization_entry(name, "build_transform").load_provider()
    except CatalogError as exc:
        raise KeyError(str(exc)) from exc
    return provider(**kwargs)


def registered_transforms() -> list[str]:
    return [
        entry.id
        for entry in builtin_catalog().entries("optimizations")
        if entry.get("kind") == "build_transform"
    ]


def build_technique(name: str, **kwargs) -> Technique:
    try:
        provider = _optimization_entry(name, "runtime_technique").load_provider()
    except CatalogError as exc:
        raise KeyError(str(exc)) from exc
    return provider(**kwargs)


def get_model_spec(transformer_or_key) -> ModelSpec | None:
    """Resolve only an explicit ``module:qualname`` ModelSpec provider.

    Transformer class-name lookup was tied to a process-global registry and is
    intentionally no longer supported. Release recipes use model catalog IDs;
    advanced Python callers should pass a ModelSpec object directly to compose.
    """

    if isinstance(transformer_or_key, ModelSpec):
        return transformer_or_key
    if not isinstance(transformer_or_key, str) or ":" not in transformer_or_key:
        return None
    provider = ProviderRef.parse(transformer_or_key).load()
    value = provider()
    if not isinstance(value, ModelSpec):
        raise TypeError(f"{transformer_or_key!r} did not construct a ModelSpec")
    return value


def is_supported(transformer_or_key) -> bool:
    return get_model_spec(transformer_or_key) is not None


def registered_techniques() -> list[str]:
    return [
        entry.id
        for entry in builtin_catalog().entries("optimizations")
        if entry.get("kind") == "runtime_technique"
    ]


def registered_models() -> list[str]:
    return [entry.id for entry in builtin_catalog().entries("models")]
