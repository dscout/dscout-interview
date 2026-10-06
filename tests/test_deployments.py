from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest

from lib.exercise import load_pipeline
from lib.fixture import create_history
from lib.simulation import APPS, Simulation
from lib.workflow import Build, Deploy, Pipeline, execute_pipeline


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.revisions = create_history(self.root / "repo")
        self.sim = Simulation(self.root / "repo", self.root / "state", speed=0)

    def build_all(self, revision):
        artifacts = {}
        for app in APPS:
            artifacts[app] = self.sim.build(revision, app, artifacts.get("greeb"))
        return artifacts

    def deploy_all(self, revision, artifacts):
        for app in APPS:
            self.sim.deploy(revision, app, artifacts[app], image_reference="digest")

    def test_cache_hit_does_not_mean_already_deployed(self):
        revision = self.revisions[0]
        self.build_all(revision)
        artifacts = self.build_all(revision)
        builds = [event for event in self.sim.events() if event["kind"] == "build_finished"]
        self.assertEqual(len(builds), 6)
        self.assertTrue(all(event["cache_hit"] for event in builds[-3:]))
        self.assertIsNone(self.sim.deployed("zorch"))
        self.deploy_all(revision, artifacts)
        self.assertEqual({event["app"] for event in self.sim.events()
                          if event["kind"] == "deploy_finished"}, set(APPS))

    def test_only_changed_images_roll_out_and_dependency_inputs_count(self):
        base, changed, last = self.revisions
        self.deploy_all(base, self.build_all(base))
        before = self.sim.deployed("zorch")
        self.deploy_all(changed, self.build_all(changed))
        self.assertEqual(self.sim.deployed("zorch"), before)
        self.assertEqual(self.sim.deployed("greeb")["revision"], changed)
        self.assertEqual(self.sim.deployed("blerg")["revision"], changed)
        self.deploy_all(last, self.build_all(last))
        events = self.sim.events()
        for revision, expected in ((base, set(APPS)), (changed, {"greeb", "blerg"}),
                                   (last, {"zorch"})):
            self.assertEqual({event["app"] for event in events
                              if event["revision"] == revision
                              and event["kind"] == "deploy_finished"}, expected)
            self.assertEqual({event["app"] for event in events
                              if event["revision"] == revision
                              and event["kind"] == "build_finished"}, set(APPS))

    def test_partial_failure_preserves_other_apps_and_cache_hit_retry_deploys(self):
        base, changed, _ = self.revisions
        self.deploy_all(base, self.build_all(base))
        old_blerg = self.sim.deployed("blerg")
        artifacts = self.build_all(changed)
        self.sim.fail_deploy = lambda revision, app: app == "blerg"
        with self.assertRaises(RuntimeError):
            self.deploy_all(changed, artifacts)
        self.assertEqual(self.sim.deployed("greeb")["revision"], changed)
        self.assertEqual(self.sim.deployed("blerg"), old_blerg)
        self.sim.fail_deploy = None
        self.deploy_all(changed, self.build_all(changed))
        self.assertEqual(self.sim.deployed("blerg")["revision"], changed)
        self.assertTrue(any(event["kind"] == "deploy_failed" and event["app"] == "blerg"
                            for event in self.sim.events()))
        retries = [event for event in self.sim.events()
                   if event["revision"] == changed and event["kind"] == "deploy_finished"]
        self.assertEqual([event["app"] for event in retries], ["greeb", "blerg"])

    def test_independent_deployments_do_not_lose_other_app_state(self):
        revision = self.revisions[0]
        artifacts = self.build_all(revision)
        gate = threading.Barrier(3, timeout=5)
        self.sim.observer = lambda event: gate.wait() if event["kind"] == "deploy_started" else None
        with ThreadPoolExecutor(max_workers=3) as workers:
            jobs = [workers.submit(self.sim.deploy, revision, app, artifacts[app]) for app in APPS]
            for job in jobs:
                job.result(timeout=10)
        self.assertTrue(all(self.sim.deployed(app)["revision"] == revision for app in APPS))

    def test_failed_app_does_not_block_independent_app(self):
        revision = self.revisions[0]
        self.sim.fail_deploy = lambda revision, app: app == "greeb"
        declaration = Pipeline(tasks=[
            Build("zorch"), Build("greeb"),
            Deploy("zorch-rollout", "zorch", needs=["zorch"]),
            Deploy("greeb-rollout", "greeb", needs=["greeb"]),
        ])
        with self.assertRaises(RuntimeError):
            execute_pipeline(self.sim, declaration, [revision])
        self.assertIsNotNone(self.sim.deployed("zorch"))
        self.assertIsNone(self.sim.deployed("greeb"))

    def test_starter_serializes_rollouts_without_cross_app_dependencies(self):
        declaration = load_pipeline()
        calls = {task.name: task for task in declaration.tasks
                 if task.name.startswith("deploy-")}
        for app in APPS:
            expected = (app, "deploy-greeb") if app == "blerg" else (app,)
            self.assertEqual(calls[f"deploy-{app}"].needs, expected)
            self.assertEqual(calls[f"deploy-{app}"].pipeline.pool, "deployment")
        execute_pipeline(self.sim, declaration, self.revisions)
        active = set()
        for event in self.sim.events():
            if event["kind"] == "deploy_started":
                self.assertFalse(active)
                active.add((event["revision"], event["app"]))
            elif event["kind"] == "deploy_finished":
                active.remove((event["revision"], event["app"]))
        self.assertFalse(active)

    def test_starter_failure_releases_pool_for_unrelated_apps(self):
        revision = self.revisions[0]
        self.sim.fail_deploy = lambda revision, app: app == "zorch"
        with self.assertRaises(RuntimeError):
            execute_pipeline(self.sim, load_pipeline(), [revision])
        self.assertIsNone(self.sim.deployed("zorch"))
        self.assertEqual(self.sim.deployed("greeb")["revision"], revision)
        self.assertEqual(self.sim.deployed("blerg")["revision"], revision)

    def test_greeb_rollout_failure_blocks_blerg_but_not_zorch(self):
        revision = self.revisions[0]
        self.sim.fail_deploy = lambda revision, app: app == "greeb"
        with self.assertRaises(RuntimeError):
            execute_pipeline(self.sim, load_pipeline(), [revision])
        self.assertIsNotNone(self.sim.deployed("zorch"))
        self.assertIsNone(self.sim.deployed("greeb"))
        self.assertIsNone(self.sim.deployed("blerg"))
        self.assertTrue(any(event["kind"] == "task_blocked"
                            and event["task"] == "deploy-blerg" for event in self.sim.events()))

    def test_greeb_rollout_finishes_or_skips_before_blerg(self):
        execute_pipeline(self.sim, load_pipeline(), self.revisions)
        events = self.sim.events()
        for revision in self.revisions:
            greeb_end = next(i for i, event in enumerate(events)
                             if event["revision"] == revision and event.get("app") == "greeb"
                             and event["kind"] in ("deploy_finished", "deploy_skipped"))
            blerg_request = next(i for i, event in enumerate(events)
                                 if event["revision"] == revision and event.get("app") == "blerg"
                                 and event["kind"] == "deploy_requested")
            self.assertLess(greeb_end, blerg_request)

    def test_simulator_does_not_impose_a_no_rollback_policy(self):
        base, changed, _ = self.revisions
        base_artifacts = self.build_all(base)
        changed_artifacts = self.build_all(changed)
        self.sim.deploy(changed, "greeb", changed_artifacts["greeb"], image_reference="digest")
        self.sim.deploy(base, "greeb", base_artifacts["greeb"], image_reference="digest")
        self.assertEqual(self.sim.deployed("greeb")["revision"], base)


if __name__ == "__main__":
    unittest.main()
