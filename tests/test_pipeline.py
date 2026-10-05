import json
from pathlib import Path
import tempfile
import threading
import unittest

from fixture import create_history, git
from pipeline import pipeline
from simulation import APPS, Simulation
from workflow import execute_pipeline


class PipelineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.commits = create_history(root / "repo")
        self.sim = Simulation(root / "repo", root / "state", speed=0)

    def released(self):
        return json.loads((self.sim.state / "release.json").read_text())["revision"]

    def deployments(self):
        return [event["revision"] for event in self.sim.events()
                if event["kind"] == "deploy_finished"]

    def assert_artifacts(self, commits):
        for commit in commits:
            for app in APPS:
                artifact = json.loads(self.sim.artifact_path(commit, app).read_text())
                self.sim.validate_artifact(commit, app, artifact)

    def test_late_older_builds_cannot_roll_back_newest_release(self):
        newest_released = threading.Event()

        def observe(event):
            if event["kind"] == "build_finished" and event["app"] == "zorch" \
                    and event["revision"] in self.commits[:-1]:
                if not newest_released.wait(5):
                    raise TimeoutError("newest revision did not release while older build waited")
            if event["kind"] == "deploy_finished" and event["revision"] == self.commits[-1]:
                newest_released.set()

        self.sim.observer = observe
        execute_pipeline(self.sim, pipeline, self.commits)
        self.assertEqual(self.deployments(), [self.commits[-1]])
        self.assertEqual(self.released(), self.commits[-1])
        self.assert_artifacts(self.commits)
        skipped = {event["revision"] for event in self.sim.events()
                   if event["kind"] == "task_skipped" and event["task"] == "release"}
        self.assertEqual(skipped, set(self.commits[:-1]))

    def test_releases_are_serial_and_only_move_forward(self):
        execute_pipeline(self.sim, pipeline, self.commits)
        active = None
        previous = -1
        for event in self.sim.events():
            if event["kind"] == "deploy_started":
                self.assertIsNone(active)
                active = event["revision"]
                index = self.commits.index(active)
                self.assertGreater(index, previous)
                previous = index
            elif event["kind"] == "deploy_finished":
                self.assertEqual(active, event["revision"])
                active = None
        self.assertIsNone(active)
        self.assertEqual(self.released(), self.commits[-1])
        self.assert_artifacts(self.commits)

    def test_separate_runs_and_warm_replay_preserve_newest_release(self):
        execute_pipeline(self.sim, pipeline, [self.commits[-1]])
        original = (self.sim.state / "release.json").read_bytes()
        execute_pipeline(self.sim, pipeline, self.commits)
        self.assertEqual((self.sim.state / "release.json").read_bytes(), original)
        self.assertEqual(self.deployments(), [self.commits[-1]])
        self.assert_artifacts(self.commits)
        offset = len(self.sim.events())
        execute_pipeline(self.sim, pipeline, list(reversed(self.commits)))
        builds = [event for event in self.sim.events()[offset:]
                  if event["kind"] == "build_finished"]
        self.assertEqual(len(builds), 9)
        self.assertTrue(all(event["cache_hit"] for event in builds))
        self.assertEqual((self.sim.state / "release.json").read_bytes(), original)

    def test_failed_newest_does_not_block_successful_older_release(self):
        self.sim.fail_build = lambda commit, app: commit == self.commits[-1] and app == "zorch"
        with self.assertRaises(RuntimeError):
            execute_pipeline(self.sim, pipeline, self.commits)
        self.assertEqual(self.released(), self.commits[1])
        self.assertNotIn(self.commits[-1], self.deployments())
        self.assertFalse((self.sim.state / "cache" /
                          f"{self.sim.cache_key(self.commits[-1], 'zorch')}.json").exists())
        self.sim.fail_build = None
        execute_pipeline(self.sim, pipeline, [self.commits[-1]])
        self.assertEqual(self.released(), self.commits[-1])

    def test_divergent_revision_is_not_released(self):
        execute_pipeline(self.sim, pipeline, [self.commits[-1]])
        git(self.sim.repo, "checkout", "--quiet", "--detach", self.commits[0])
        git(self.sim.repo, "commit", "--quiet", "--allow-empty", "-m", "divergent history")
        divergent = git(self.sim.repo, "rev-parse", "HEAD")
        execute_pipeline(self.sim, pipeline, [divergent])
        self.assertEqual(self.released(), self.commits[-1])
        self.assertEqual(self.deployments(), [self.commits[-1]])
        self.assert_artifacts([divergent])

    def test_invalid_release_history_fails_closed(self):
        (self.sim.state / "release.json").write_text(json.dumps({"revision": "missing-commit"}))
        with self.assertRaises(RuntimeError):
            execute_pipeline(self.sim, pipeline, self.commits[:1])
        self.assertEqual(self.deployments(), [])
        self.assertEqual(self.released(), "missing-commit")


if __name__ == "__main__":
    unittest.main()
