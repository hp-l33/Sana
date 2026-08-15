"""Diffusers semantic reference metadata for LTX-2.3."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiffusersReference:
    model: str
    name = "diffusers"
    framework = "diffusers"
    role = "semantic_reference"
