"""Semantic-reference boundary, separate from executable backends."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SemanticReference(Protocol):
    name: str
    framework: str
    role: str
    model: str
