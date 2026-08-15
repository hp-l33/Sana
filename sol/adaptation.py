import fnmatch
import json
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ._toml import load_toml
from .discovery import MODEL_ID
from .errors import AdaptationError
from .scaffold import scaffold_plugin

TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
STAGES = (
    "scoped",
    "scaffolded",
    "reference_verified",
    "dense_backend_verified",
    "seams_wired",
    "space_ready",
    "tuned",
    "accepted",
    "release_candidate",
    "awaiting_approval",
    "released",
)


@dataclass(frozen=True)
class TaskSpec:
    action: str
    title: str
    instructions: str
    acceptance: Tuple[str, ...]
    required_evidence: Tuple[str, ...]
    allowed_paths: Tuple[str, ...] = ()


PLUGIN_PATHS = ("sol/plugins/{model}/**", "tests/plugins/{model}/**")
TASKS: Mapping[str, TaskSpec] = {
    "scoped": TaskSpec(
        action="scaffold",
        title="Create the self-owned model surface",
        instructions="Run `sol adapt scaffold RUN_ID`; do not hand-create a parallel schema.",
        acceptance=("Plugin and test skeletons exist", "Manifest identity matches its directory"),
        required_evidence=(),
        allowed_paths=PLUGIN_PATHS,
    ),
    "scaffolded": TaskSpec(
        action="submit",
        title="Reproduce the semantic reference",
        instructions="Pin the model revision and produce deterministic reference artifacts before optimizing.",
        acceptance=("Reference command is replayable", "Semantic checks and artifact hashes are recorded"),
        required_evidence=(
            "reference_command", "model_revision", "artifacts", "semantic_checks", "changed_paths"
        ),
        allowed_paths=PLUGIN_PATHS,
    ),
    "reference_verified": TaskSpec(
        action="submit",
        title="Verify the dense performance backend",
        instructions="Integrate a dense backend path and prove parity with the semantic reference.",
        acceptance=("Backend is dense", "Environment is pinned", "Parity gate passes"),
        required_evidence=(
            "baseline_command",
            "environment_fingerprint",
            "target_fingerprint",
            "parity",
            "artifacts",
            "changed_paths",
        ),
        allowed_paths=PLUGIN_PATHS,
    ),
    "dense_backend_verified": TaskSpec(
        action="submit",
        title="Wire stable optimization seams",
        instructions="Expose composable technique seams with explicit dense fallbacks and engagement checks.",
        acceptance=("Seams are model-owned", "Unsupported combinations fail closed"),
        required_evidence=("seams", "dense_fallbacks", "engagement_checks", "changed_paths"),
        allowed_paths=PLUGIN_PATHS,
    ),
    "seams_wired": TaskSpec(
        action="submit",
        title="Define a bounded target-specific search space",
        instructions="Declare only legal dimensions, constraints, and interactions for this backend and target.",
        acceptance=("Every dimension is bounded", "Target and topology are explicit"),
        required_evidence=("dimensions", "constraints", "interaction_plan", "changed_paths"),
        allowed_paths=PLUGIN_PATHS,
    ),
    "space_ready": TaskSpec(
        action="submit",
        title="Tune within the experiment budget",
        instructions="Run staged single-family and interaction trials; preserve rejected attempts and raw results.",
        acceptance=("Budget is respected", "Winning candidate has raw samples and artifacts"),
        required_evidence=("trials", "best_candidate", "budget_used", "rejected", "artifacts"),
        allowed_paths=PLUGIN_PATHS,
    ),
    "tuned": TaskSpec(
        action="submit",
        title="Run release acceptance",
        instructions="Re-run baseline and candidate from clean processes under one immutable protocol.",
        acceptance=("Same-topology comparison", "Quality and engagement gates pass"),
        required_evidence=(
            "baseline_command",
            "candidate_command",
            "environment_fingerprint",
            "target_fingerprint",
            "baseline_samples_seconds",
            "candidate_samples_seconds",
            "quality",
            "artifacts",
            "engagement",
            "interaction_matrix",
        ),
        allowed_paths=PLUGIN_PATHS,
    ),
    "accepted": TaskSpec(
        action="submit",
        title="Encode the measured release preset",
        instructions="Promote only the accepted target-specific configuration and replay commands into the plugin.",
        acceptance=("Preset resolves to an inspectable plan", "Manifest lists the preset"),
        required_evidence=(
            "preset_id", "plan_fingerprint", "replay_commands", "evidence_links", "changed_paths"
        ),
        allowed_paths=PLUGIN_PATHS,
    ),
    "release_candidate": TaskSpec(
        action="submit",
        title="Validate and prepare maintainer review",
        instructions="Run repository checks and summarize evidence; do not approve or publish.",
        acceptance=("All checks pass", "Release preset is replayable", "Review summary is complete"),
        required_evidence=("checks", "release_preset", "review_summary"),
        allowed_paths=PLUGIN_PATHS,
    ),
    "awaiting_approval": TaskSpec(
        action="approve",
        title="Wait for maintainer approval",
        instructions="A maintainer must review the evidence and run `sol adapt approve RUN_ID --by NAME`.",
        acceptance=("Approval is explicit and attributable",),
        required_evidence=(),
    ),
    "released": TaskSpec(
        action="complete",
        title="Adaptation released",
        instructions="The manifest is released. Publishing remains a separately authorized operation.",
        acceptance=(),
        required_evidence=(),
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_state_root() -> Path:
    explicit = os.environ.get("SOL_STATE_HOME")
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "state"
    return base / "sol"


class AdaptationStore:
    def __init__(self, state_root: Optional[Path] = None):
        self.root = (state_root or default_state_root()).expanduser().resolve() / "adaptations"

    def _run_dir(self, run_id: str) -> Path:
        if not TOKEN.fullmatch(run_id):
            raise AdaptationError(f"invalid run id {run_id!r}")
        return self.root / run_id

    def load(self, run_id: str) -> Dict[str, Any]:
        path = self._run_dir(run_id) / "state.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise AdaptationError(f"unknown adaptation run {run_id!r}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise AdaptationError(f"cannot read adaptation run {run_id!r}: {exc}") from exc
        if data.get("schema_version") != 1 or data.get("id") != run_id:
            raise AdaptationError(f"adaptation state for {run_id!r} is invalid")
        return data

    def save(self, state: Mapping[str, Any]) -> None:
        run_dir = self._run_dir(str(state["id"]))
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / "state.json"
        temporary = run_dir / "state.json.tmp"
        temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)

    def evidence_path(self, run_id: str, stage: str) -> Path:
        return self._run_dir(run_id) / "evidence" / f"{stage}.json"


class AdaptationManager:
    def __init__(self, store: Optional[AdaptationStore] = None):
        self.store = store or AdaptationStore()

    def start(
        self,
        model: str,
        reference: str,
        backend: str,
        target: str,
        budget: int,
        repo_root: Path,
    ) -> Dict[str, Any]:
        if not MODEL_ID.fullmatch(model):
            raise AdaptationError("model id must use lower-case letters, digits, and underscores")
        for label, value in (("reference", reference), ("backend", backend), ("target", target)):
            if not TOKEN.fullmatch(value):
                raise AdaptationError(f"invalid {label} {value!r}")
        if budget < 1:
            raise AdaptationError("budget must be at least 1")
        root = repo_root.expanduser().resolve()
        if not (root / "sol" / "plugins").is_dir():
            raise AdaptationError(f"{root} is not a Sol Engine repository")
        if (root / "sol" / "plugins" / model).exists():
            raise AdaptationError(f"model plugin {model!r} already exists")
        run_id = f"{model}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{secrets.token_hex(3)}"
        now = _now()
        state: Dict[str, Any] = {
            "schema_version": 1,
            "id": run_id,
            "model": model,
            "reference": reference,
            "backend": backend,
            "target": target,
            "budget": budget,
            "repo_root": str(root),
            "stage": "scoped",
            "created_at": now,
            "updated_at": now,
            "history": [{"stage": "scoped", "at": now, "event": "started"}],
        }
        self.store.save(state)
        return state

    def status(self, run_id: str) -> Dict[str, Any]:
        state = self.store.load(run_id)
        result = dict(state)
        result["next"] = self.next(run_id)
        return result

    def next(self, run_id: str) -> Dict[str, Any]:
        state = self.store.load(run_id)
        stage = str(state["stage"])
        spec = TASKS[stage]
        allowed = [item.format(model=state["model"]) for item in spec.allowed_paths]
        return {
            "run_id": run_id,
            "stage": stage,
            "action": spec.action,
            "title": spec.title,
            "instructions": spec.instructions,
            "allowed_paths": allowed,
            "acceptance": list(spec.acceptance),
            "required_evidence": list(spec.required_evidence),
            "budget": state["budget"],
            "model": state["model"],
            "reference": state["reference"],
            "backend": state["backend"],
            "target": state["target"],
        }

    def _advance(self, state: Dict[str, Any], event: str, details: Mapping[str, Any]) -> None:
        current = str(state["stage"])
        state["stage"] = STAGES[STAGES.index(current) + 1]
        state["updated_at"] = _now()
        state["history"].append(
            {"stage": state["stage"], "at": state["updated_at"], "event": event, **details}
        )
        self.store.save(state)

    def scaffold(self, run_id: str) -> Dict[str, Any]:
        state = self.store.load(run_id)
        if state["stage"] != "scoped":
            raise AdaptationError("scaffold is only valid at the scoped stage")
        files = scaffold_plugin(
            Path(state["repo_root"]),
            state["model"],
            state["reference"],
            state["backend"],
            state["target"],
        )
        evidence = {
            "schema_version": 1,
            "stage": "scoped",
            "passed": True,
            "generated_files": files,
        }
        path = self.store.evidence_path(run_id, "scoped")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._advance(state, "scaffolded", {"evidence": str(path)})
        return self.status(run_id)

    def submit(self, run_id: str, evidence_file: Path) -> Dict[str, Any]:
        state = self.store.load(run_id)
        stage = str(state["stage"])
        spec = TASKS[stage]
        if spec.action != "submit":
            raise AdaptationError(f"stage {stage!r} does not accept submitted evidence")
        try:
            evidence = json.loads(evidence_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AdaptationError(f"cannot read evidence: {exc}") from exc
        if not isinstance(evidence, dict):
            raise AdaptationError("evidence must be a JSON object")
        if evidence.get("schema_version") != 1:
            raise AdaptationError("evidence schema_version must be 1")
        if evidence.get("stage") != stage:
            raise AdaptationError(f"evidence stage must be {stage!r}")
        if evidence.get("passed") is not True:
            raise AdaptationError("evidence must declare passed: true")
        missing = [key for key in spec.required_evidence if self._empty(evidence.get(key))]
        if missing:
            raise AdaptationError(f"evidence is missing non-empty keys: {', '.join(missing)}")
        self._validate_changed_paths(evidence.get("changed_paths"), spec, state["model"])
        self._validate_evidence(stage, evidence, state)
        destination = self.store.evidence_path(run_id, stage)
        if destination.exists():
            raise AdaptationError(f"evidence for stage {stage!r} already exists")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._advance(state, "evidence_accepted", {"evidence": str(destination)})
        return self.status(run_id)

    def approve(self, run_id: str, approver: str) -> Dict[str, Any]:
        state = self.store.load(run_id)
        if state["stage"] != "awaiting_approval":
            raise AdaptationError("approval is only valid at the awaiting_approval stage")
        if not approver.strip():
            raise AdaptationError("approver must be non-empty")
        manifest = Path(state["repo_root"]) / "sol" / "plugins" / state["model"] / "plugin.toml"
        try:
            data = load_toml(manifest)
        except (OSError, ValueError) as exc:
            raise AdaptationError(f"cannot read release candidate manifest: {exc}") from exc
        if data.get("id") != state["model"]:
            raise AdaptationError("release candidate manifest model does not match adaptation state")
        if state["reference"] not in data.get("references", []):
            raise AdaptationError("release candidate dropped the scoped semantic reference")
        if state["backend"] not in data.get("backends", []):
            raise AdaptationError("release candidate dropped the scoped backend")
        if state["target"] not in data.get("targets", []):
            raise AdaptationError("release candidate dropped the scoped target")
        if data.get("status") != "draft":
            raise AdaptationError("release candidate manifest must still be draft")
        if not data.get("presets"):
            raise AdaptationError("release candidate manifest must contain at least one preset")
        release_evidence_path = self.store.evidence_path(run_id, "release_candidate")
        try:
            release_evidence = json.loads(release_evidence_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AdaptationError(f"cannot read release validation evidence: {exc}") from exc
        if release_evidence.get("release_preset") not in data["presets"]:
            raise AdaptationError("validated release preset is not listed in the manifest")
        content = manifest.read_text(encoding="utf-8")
        marker = 'status = "draft"'
        if content.count(marker) != 1:
            raise AdaptationError("cannot promote manifest status safely")
        manifest.write_text(content.replace(marker, 'status = "released"'), encoding="utf-8")
        self._advance(state, "approved", {"approver": approver.strip(), "manifest": str(manifest)})
        return self.status(run_id)

    @staticmethod
    def _empty(value: Any) -> bool:
        return value is None or value == "" or value == [] or value == {}

    @staticmethod
    def _validate_changed_paths(value: Any, spec: TaskSpec, model: str) -> None:
        if value is None:
            return
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise AdaptationError("changed_paths must be a list of repository-relative paths")
        patterns = [item.format(model=model) for item in spec.allowed_paths]
        for item in value:
            path = PurePosixPath(item)
            if path.is_absolute() or ".." in path.parts:
                raise AdaptationError(f"changed path is not repository-relative: {item!r}")
            normalized = str(path)
            if not any(fnmatch.fnmatchcase(normalized, pattern) for pattern in patterns):
                raise AdaptationError(f"changed path {item!r} is outside allowed_paths")

    @staticmethod
    def _validate_evidence(
        stage: str, evidence: Mapping[str, Any], state: Mapping[str, Any]
    ) -> None:
        if "artifacts" in evidence and (
            not isinstance(evidence["artifacts"], list)
            or not all(isinstance(item, str) and item for item in evidence["artifacts"])
        ):
            raise AdaptationError("artifacts must be a non-empty list of immutable references")
        for command_key in ("reference_command", "baseline_command", "candidate_command"):
            if command_key in evidence and (
                not isinstance(evidence[command_key], list)
                or not all(isinstance(item, str) and item for item in evidence[command_key])
            ):
                raise AdaptationError(f"{command_key} must be a non-empty argv list")
        if stage in {"scaffolded", "reference_verified"}:
            gate_key = "semantic_checks" if stage == "scaffolded" else "parity"
            gate = evidence.get(gate_key)
            if not isinstance(gate, dict) or gate.get("gate") != "pass":
                raise AdaptationError(f"{gate_key}.gate must be 'pass'")
        if stage == "space_ready":
            trials = evidence.get("trials")
            used = evidence.get("budget_used")
            if not isinstance(trials, list) or not trials:
                raise AdaptationError("trials must be a non-empty list")
            if isinstance(used, bool) or not isinstance(used, int) or used < 1:
                raise AdaptationError("budget_used must be a positive integer")
            if used != len(trials):
                raise AdaptationError("budget_used must equal the number of recorded trials")
            if used > state["budget"]:
                raise AdaptationError(f"budget_used {used} exceeds budget {state['budget']}")
        if stage == "tuned":
            for key in ("baseline_samples_seconds", "candidate_samples_seconds"):
                samples = evidence.get(key)
                if (
                    not isinstance(samples, list)
                    or len(samples) < 3
                    or any(
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or value <= 0
                        for value in samples
                    )
                ):
                    raise AdaptationError(f"{key} must contain at least three positive raw samples")
            quality = evidence.get("quality")
            if not isinstance(quality, dict) or quality.get("gate") != "pass":
                raise AdaptationError("quality.gate must be 'pass'")
            if not isinstance(evidence.get("engagement"), dict):
                raise AdaptationError("engagement must be a structured object")
        if stage == "accepted" and not TOKEN.fullmatch(str(evidence.get("preset_id", ""))):
            raise AdaptationError("preset_id is invalid")
        if stage == "release_candidate":
            if not TOKEN.fullmatch(str(evidence.get("release_preset", ""))):
                raise AdaptationError("release_preset is invalid")
            checks = evidence.get("checks")
            if not isinstance(checks, dict) or not checks:
                raise AdaptationError("checks must be a non-empty structured object")
