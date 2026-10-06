from pathlib import Path
import tempfile
import threading
import unittest

from lib.exercise import load_pipeline
from lib.fixture import create_history
from lib.simulation import APPS, Simulation
from lib.workflow import execute_pipeline


class PipelineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.revisions = create_history(self.root / "repo")
        self.sim = Simulation(self.root / "repo", self.root / "state", speed=0)
        self.pipeline = load_pipeline()

    def test_builds_for_different_prs_overlap(self):
        revisions = self.revisions[::2]
        both_started = threading.Barrier(2, timeout=5)

        def observe(event):
            if event["kind"] == "build_started" and event["app"] == "zorch":
                both_started.wait()

        self.sim.observer = observe
        execute_pipeline(self.sim, self.pipeline, revisions)
        starts = [event["revision"] for event in self.sim.events()
                  if event["kind"] == "build_started" and event["app"] == "zorch"]
        self.assertCountEqual(starts, revisions)

    def test_deployments_are_serial_and_blerg_waits_for_greeb(self):
        execute_pipeline(self.sim, self.pipeline, self.revisions)
        active = set()
        events = self.sim.events()
        for event in events:
            if event["kind"] == "deploy_started":
                self.assertFalse(active)
                active.add((event["revision"], event["app"]))
            elif event["kind"] == "deploy_finished":
                active.remove((event["revision"], event["app"]))
        self.assertFalse(active)
        for i, event in enumerate(events):
            if event["kind"] == "deploy_started" and event.get("app") == "blerg":
                greeb_end = max(j for j, previous in enumerate(events[:i])
                                if previous["revision"] == event["revision"]
                                and previous.get("app") == "greeb"
                                and (previous["kind"] in ("deploy_finished", "deploy_skipped")
                                     or previous.get("task") == "deploy-greeb"))
                self.assertLess(greeb_end, i)
        self.assertEqual({app: self.sim.deployed(app)["image"]["digest"] for app in APPS},
                         {app: self.sim.image_digest(self.revisions[-1], app) for app in APPS})

    def test_stale_pr_cannot_roll_back_newer_deployments(self):
        old, new = self.revisions[0], self.revisions[1]
        newer_deployed = threading.Event()

        def observe(event):
            if event["kind"] == "build_finished" and event["revision"] == old:
                if not newer_deployed.wait(timeout=5):
                    raise TimeoutError("newer PR did not deploy")
            if event["kind"] == "deploy_finished" and event["revision"] == new \
                    and event["app"] == "blerg":
                newer_deployed.set()

        self.sim.observer = observe
        execute_pipeline(self.sim, self.pipeline, [old, new])
        self.assertTrue(newer_deployed.is_set())
        self.assertEqual({app: self.sim.deployed(app)["image"]["digest"] for app in APPS},
                         {app: self.sim.image_digest(new, app) for app in APPS})
        self.assertFalse(any(event["kind"] == "deploy_started" and event["revision"] == old
                             for event in self.sim.events()))
        self.assertEqual({event["app"] for event in self.sim.events()
                          if event["kind"] == "build_finished" and event["revision"] == old},
                         set(APPS))


if __name__ == "__main__":
    unittest.main()
