"""Machine-readable tuning axes owned by optimization implementations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Parameter:
    default: Any
    description: str = ""

    @property
    def kind(self) -> str:
        return type(self).__name__.removesuffix("Parameter").lower()

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, **asdict(self)}


@dataclass(frozen=True)
class ChoiceParameter(Parameter):
    choices: tuple[Any, ...] = ()


@dataclass(frozen=True)
class FloatParameter(Parameter):
    minimum: float = 0.0
    maximum: float = 1.0


@dataclass(frozen=True)
class IntegerParameter(Parameter):
    minimum: int = 0
    maximum: int = 1


@dataclass(frozen=True)
class TextParameter(Parameter):
    pattern: str = ""
