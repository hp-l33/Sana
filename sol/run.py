"""A run is the result of preparing or executing one validated plan."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping

from sol.plan import ExecutionPlan


def default_run_root() -> Path:
    state_home = os.environ.get("XDG_STATE_HOME")
    base = Path(state_home).expanduser() if state_home else Path.home() / ".local" / "state"
    return base / "sol" / "runs"


def _fingerprint(plan: ExecutionPlan, overrides: Mapping[str, str]) -> str:
    payload = {
        "plan": plan.fingerprint,
        "overrides": dict(sorted(overrides.items())),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class Run:
    """Immutable preparation/execution record.

    Constructing a Run has no filesystem or process side effects. ``save`` and
    ``execute`` are deliberately explicit operations.
    """

    plan: ExecutionPlan
    overrides: Mapping[str, str]
    command: tuple[str, ...]
    run_root: str
    execution_fingerprint: str
    status: str = "planned"
    returncode: int | None = None

    @classmethod
    def prepare(
        cls,
        plan: ExecutionPlan,
        *,
        repo_root: Path,
        overrides: Mapping[str, str] | None = None,
        run_root: str | Path | None = None,
    ) -> "Run":
        if not plan.runtime_ready:
            raise ValueError(
                f"model plugin {plan.model_provider!r} cannot compile a runtime environment"
            )
        user_overrides = dict(overrides or {})
        protected = {
            "SOL_PLAN_FINGERPRINT",
            "SOL_EXECUTION_FINGERPRINT",
            "SOL_PRESET",
        }
        collision = sorted(protected & set(user_overrides))
        if collision:
            raise ValueError(f"cannot override provenance keys: {collision}")
        execution = _fingerprint(plan, user_overrides)
        target_root = Path(run_root).expanduser().resolve() if run_root else default_run_root()
        command = [
            sys.executable,
            str(repo_root / "scripts" / "run.py"),
            str(repo_root / plan.launch_config),
            "--run-root",
            str(target_root),
        ]
        environment = {
            **plan.runtime_env,
            **user_overrides,
            "SOL_PLAN_FINGERPRINT": plan.fingerprint,
            "SOL_EXECUTION_FINGERPRINT": execution,
            "SOL_PRESET": plan.preset_id,
        }
        for key, value in sorted(environment.items()):
            command.extend(("--set", f"{key}={value}"))
        return cls(
            plan=plan,
            overrides=user_overrides,
            command=tuple(command),
            run_root=str(target_root),
            execution_fingerprint=execution,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "status": self.status,
            "returncode": self.returncode,
            "execution_fingerprint": self.execution_fingerprint,
            "run_root": self.run_root,
            "overrides": dict(sorted(self.overrides.items())),
            "command": list(self.command),
            "plan": self.plan.as_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True)

    def save(self, destination: str | Path) -> Path:
        path = Path(destination).expanduser().resolve()
        if path.suffix.lower() != ".json":
            path = path / f"{self.execution_fingerprint}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json() + "\n")
        return path

    def execute(self, *, cwd: str | Path) -> "Run":
        process = subprocess.run(self.command, cwd=Path(cwd))
        return replace(self, status="completed" if process.returncode == 0 else "failed", returncode=process.returncode)
