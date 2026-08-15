"""Public structural contract shared by runtime and preparation optimizations."""

from __future__ import annotations

from typing import Mapping, Protocol, runtime_checkable


@runtime_checkable
class Optimization(Protocol):
    """The only optimization concept exposed by the product API."""

    name: str
    required_capabilities: frozenset
    parameters: Mapping[str, object]
