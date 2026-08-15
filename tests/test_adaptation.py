import json
import tempfile
import unittest
from pathlib import Path

from sol.adaptation import AdaptationManager, AdaptationStore, TASKS
from sol.errors import AdaptationError


def evidence_value(key: str):
    values = {
        "reference_command": ["python", "reference.py"],
        "baseline_command": ["python", "dense.py"],
        "candidate_command": ["python", "candidate.py"],
        "model_revision": "sha256:model",
        "environment_fingerprint": "sha256:environment",
        "target_fingerprint": "h100_sxm_80gb_x4:nvlink:ulysses4",
        "artifacts": ["sha256:artifact"],
        "semantic_checks": {"gate": "pass"},
        "parity": {"gate": "pass"},
        "seams": ["attention"],
        "dense_fallbacks": ["attention:dense"],
        "engagement_checks": ["sparse_counter"],
        "dimensions": {"sparse.density": [0.1, 0.2]},
        "constraints": ["same_topology"],
        "interaction_plan": ["sparse+cache"],
        "trials": [{"id": "trial-1", "result": "pass"}],
        "best_candidate": {"id": "trial-1"},
        "budget_used": 1,
        "rejected": ["none"],
        "baseline_samples_seconds": [2.0, 2.1, 1.9],
        "candidate_samples_seconds": [1.0, 1.1, 0.9],
        "quality": {"gate": "pass"},
        "engagement": {"sparse": True},
        "interaction_matrix": {"sparse+cache": "pass"},
        "preset_id": "balanced",
        "plan_fingerprint": "sha256:plan",
        "replay_commands": [["sol", "inspect"], ["sol", "run"]],
        "evidence_links": ["state:evidence"],
        "checks": {"unit": "pass", "doctor": "pass"},
        "release_preset": "balanced",
        "review_summary": "ready for maintainer review",
        "changed_paths": ["sol/plugins/demo/plugin.py"],
    }
    return values[key]


class AdaptationTests(unittest.TestCase):
    def setUp(self):
        self.repo_tmp = tempfile.TemporaryDirectory()
        self.state_tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.repo_tmp.name)
        (self.repo / "sol" / "plugins").mkdir(parents=True)
        (self.repo / "tests").mkdir()
        self.manager = AdaptationManager(AdaptationStore(Path(self.state_tmp.name)))
        self.state = self.manager.start(
            "demo", "diffusers", "sglang", "h100_x4", 4, self.repo
        )

    def tearDown(self):
        self.repo_tmp.cleanup()
        self.state_tmp.cleanup()

    def test_start_and_scaffold_are_durable(self):
        task = self.manager.next(self.state["id"])
        self.assertEqual(task["action"], "scaffold")
        status = self.manager.scaffold(self.state["id"])
        self.assertEqual(status["stage"], "scaffolded")
        self.assertTrue((self.repo / "sol" / "plugins" / "demo" / "plugin.toml").is_file())
        reloaded = AdaptationManager(AdaptationStore(Path(self.state_tmp.name)))
        self.assertEqual(reloaded.status(self.state["id"])["stage"], "scaffolded")

    def test_evidence_fails_closed_and_enforces_paths(self):
        self.manager.scaffold(self.state["id"])
        evidence = {
            "schema_version": 1,
            "stage": "scaffolded",
            "passed": True,
            "reference_command": ["python", "reference.py"],
        }
        path = Path(self.state_tmp.name) / "evidence.json"
        path.write_text(json.dumps(evidence), encoding="utf-8")
        with self.assertRaisesRegex(AdaptationError, "missing non-empty keys"):
            self.manager.submit(self.state["id"], path)
        evidence.update(
            {
                "model_revision": "sha",
                "artifacts": ["sha256:artifact"],
                "semantic_checks": {"gate": "pass"},
                "changed_paths": ["README.md"],
            }
        )
        path.write_text(json.dumps(evidence), encoding="utf-8")
        with self.assertRaisesRegex(AdaptationError, "outside allowed_paths"):
            self.manager.submit(self.state["id"], path)

    def test_full_lifecycle_stops_for_approval_and_promotes_manifest(self):
        run_id = self.state["id"]
        self.manager.scaffold(run_id)
        evidence_file = Path(self.state_tmp.name) / "evidence.json"
        while True:
            task = self.manager.next(run_id)
            if task["action"] != "submit":
                break
            evidence = {
                "schema_version": 1,
                "stage": task["stage"],
                "passed": True,
                **{key: evidence_value(key) for key in task["required_evidence"]},
            }
            evidence_file.write_text(json.dumps(evidence), encoding="utf-8")
            self.manager.submit(run_id, evidence_file)
            if task["stage"] == "accepted":
                manifest = self.repo / "sol" / "plugins" / "demo" / "plugin.toml"
                content = manifest.read_text(encoding="utf-8")
                manifest.write_text(
                    content.replace("presets = []", 'presets = ["balanced"]'),
                    encoding="utf-8",
                )
        self.assertEqual(task["stage"], "awaiting_approval")
        self.assertEqual(task["action"], "approve")
        status = self.manager.approve(run_id, "maintainer")
        self.assertEqual(status["stage"], "released")
        manifest_text = (
            self.repo / "sol" / "plugins" / "demo" / "plugin.toml"
        ).read_text(encoding="utf-8")
        self.assertIn('status = "released"', manifest_text)

    def test_budget_is_a_hard_limit(self):
        run_id = self.state["id"]
        self.manager.scaffold(run_id)
        state = self.manager.store.load(run_id)
        state["stage"] = "space_ready"
        self.manager.store.save(state)
        task = self.manager.next(run_id)
        evidence = {
            "schema_version": 1,
            "stage": "space_ready",
            "passed": True,
            **{key: evidence_value(key) for key in task["required_evidence"]},
            "trials": [{"id": f"trial-{index}"} for index in range(5)],
            "budget_used": 5,
        }
        path = Path(self.state_tmp.name) / "over-budget.json"
        path.write_text(json.dumps(evidence), encoding="utf-8")
        with self.assertRaisesRegex(AdaptationError, "exceeds budget"):
            self.manager.submit(run_id, path)


if __name__ == "__main__":
    unittest.main()
