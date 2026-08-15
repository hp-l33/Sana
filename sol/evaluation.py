"""One authoritative evaluator for model-plugin acceptance contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sol import _toml


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class Verdict:
    gates: tuple[GateResult, ...]

    @property
    def passed(self) -> bool:
        return all(gate.passed for gate in self.gates)

    def as_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "gates": {
                gate.name: {"passed": gate.passed, "detail": gate.detail}
                for gate in self.gates
            },
        }


@dataclass(frozen=True)
class AcceptanceSpec:
    id: str
    required_artifacts: tuple[str, ...]
    min_speedup: float
    warmup_required: bool
    quality_required: bool
    visual_required: bool
    source: str

    @classmethod
    def from_toml(cls, path: str | Path) -> "AcceptanceSpec":
        source = Path(path).resolve()
        data = _toml.load(source)
        artifacts = data.get("artifacts", {})
        performance = data.get("performance", {})
        quality = data.get("quantitative_quality", {})
        visual = data.get("visual_artifact", {})
        return cls(
            id=str(data.get("id", source.stem)),
            required_artifacts=tuple(str(value) for value in artifacts.get("required", [])),
            min_speedup=float(performance.get("min_speedup_for_promotion", 1.0)),
            warmup_required=bool(performance.get("warmup_required_for_promotion", False)),
            quality_required=bool(quality.get("enabled", False)),
            visual_required=bool(visual.get("enabled", False)),
            source=str(source),
        )

    def evaluate(self, evidence: Mapping[str, Any]) -> Verdict:
        present = {str(value) for value in evidence.get("artifacts", ())}
        missing = sorted(set(self.required_artifacts) - present)
        speedup = float(evidence.get("speedup", 0.0))
        gates = [
            GateResult(
                "artifacts",
                not missing,
                "complete" if not missing else f"missing: {missing}",
            ),
            GateResult(
                "official_config",
                evidence.get("official_config_matches") is True,
                "matches" if evidence.get("official_config_matches") is True else "not proven",
            ),
            GateResult(
                "performance",
                speedup >= self.min_speedup,
                f"{speedup:.3f}x; required {self.min_speedup:.3f}x",
            ),
        ]
        if self.warmup_required:
            gates.append(
                GateResult(
                    "warmup",
                    evidence.get("warmup_complete") is True,
                    "complete" if evidence.get("warmup_complete") is True else "not proven",
                )
            )
        if self.quality_required:
            gates.append(
                GateResult(
                    "quality",
                    evidence.get("quality_passed") is True,
                    "passed" if evidence.get("quality_passed") is True else "not proven",
                )
            )
        if self.visual_required:
            gates.append(
                GateResult(
                    "visual_artifact",
                    evidence.get("visual_passed") is True,
                    "passed" if evidence.get("visual_passed") is True else "not proven",
                )
            )
        return Verdict(tuple(gates))
