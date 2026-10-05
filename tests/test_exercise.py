import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from fixture import create_history, git
from pipeline import run, run_revision
from simulation import APPS, Simulation

ROOT = Path(__file__).resolve().parents[1]


class ExerciseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.repo = self.root / "repo"
        self.revisions = create_history(self.repo)
        self.sim = Simulation(self.repo, self.root / "state", speed=0)

    def test_git_history_and_sources(self):
        base, greeb, zorch = self.revisions
        self.assertEqual(git(self.repo, "rev-parse", f"{greeb}^"), base)
        self.assertEqual(git(self.repo, "rev-parse", f"{zorch}^"), greeb)
        for revision, app in ((greeb, "greeb"), (zorch, "zorch")):
            self.assertEqual(git(self.repo, "diff-tree", "--no-commit-id", "--name-only",
                                 "-r", revision), f"source/{app}.txt")
        self.assertEqual(git(self.repo, "show", f"{base}:source/greeb.txt"), "greeb-v1")
        self.assertEqual(git(self.repo, "show", f"{greeb}:source/greeb.txt"), "greeb-v2")
        self.assertEqual(git(self.repo, "show", f"{zorch}:source/zorch.txt"), "zorch-v2")

    def test_pipeline_cache_and_artifacts(self):
        # Finish each run before asserting that its published entries are reusable.
        expected_hits = (set(), {"zorch"}, {"greeb", "blerg"})
        for revision, hits in zip(self.revisions, expected_hits):
            run(self.sim, [revision])
            events = [e for e in self.sim.events()
                      if e["revision"] == revision and e["kind"] == "build_finished"]
            self.assertEqual({e["app"] for e in events}, set(APPS))
            self.assertEqual({e["app"] for e in events if e["cache_hit"]}, hits)
            release = json.loads((self.sim.state / "release.json").read_text())
            self.assertEqual(release["revision"], revision)
            for app in APPS:
                self.sim.validate_artifact(revision, app, release["artifacts"][app])
        base, greeb, zorch = self.revisions
        self.assertNotEqual(self.sim.cache_key(base, "blerg"),
                            self.sim.cache_key(greeb, "blerg"))
        self.assertEqual(self.sim.cache_key(greeb, "blerg"),
                         self.sim.cache_key(zorch, "blerg"))
        run(self.sim, self.revisions)
        builds = [e for e in self.sim.events() if e["kind"] == "build_finished"]
        self.assertTrue(all(e["cache_hit"] for e in builds[-9:]))

    def test_cache_is_content_based(self):
        base = self.revisions[0]
        git(self.repo, "checkout", "--quiet", "--detach", base)
        git(self.repo, "commit", "--quiet", "--allow-empty", "-m", "same source")
        other = git(self.repo, "rev-parse", "HEAD")
        self.assertNotEqual(base, other)
        run_revision(self.sim, base)
        run_revision(self.sim, other)
        hits = [e for e in self.sim.events()
                if e["kind"] == "cache_hit" and e["revision"] == other]
        self.assertEqual({e["app"] for e in hits}, set(APPS))

    def test_exact_source_bytes_affect_cache(self):
        previous = self.revisions[-1]
        (self.repo / "source/zorch.txt").write_text("zorch-v2\n\n")
        git(self.repo, "add", "source")
        git(self.repo, "commit", "--quiet", "-m", "change whitespace")
        revision = git(self.repo, "rev-parse", "HEAD")
        self.assertNotEqual(self.sim.cache_key(previous, "zorch"),
                            self.sim.cache_key(revision, "zorch"))

    def test_failed_build_does_not_publish_or_release(self):
        base, revision, _ = self.revisions
        run_revision(self.sim, base)
        release = (self.sim.state / "release.json").read_bytes()
        failing = Simulation(self.repo, self.sim.state, speed=0,
                             fail_build=lambda rev, app: app == "greeb")
        with self.assertRaises(RuntimeError):
            run_revision(failing, revision)
        key = self.sim.cache_key(revision, "greeb")
        self.assertFalse((self.sim.state / "cache" / f"{key}.json").exists())
        self.assertFalse(self.sim.artifact_path(revision, "greeb").exists())
        self.assertEqual((self.sim.state / "release.json").read_bytes(), release)
        run_revision(self.sim, revision)
        self.assertEqual(json.loads((self.sim.state / "release.json").read_text())
                         ["revision"], revision)

    def test_dependency_and_release_validation(self):
        base, other, _ = self.revisions
        with self.assertRaises(ValueError):
            self.sim.build(base, "blerg")
        artifacts = {}
        for app in APPS:
            artifacts[app] = self.sim.build(base, app, artifacts.get("greeb"))
        with self.assertRaises(ValueError):
            self.sim.deploy(other, artifacts)
        with self.assertRaises(ValueError):
            self.sim.deploy(base, {"zorch": artifacts["zorch"]})
        self.assertFalse((self.sim.state / "release.json").exists())

    def test_concurrent_cache_publication(self):
        revision = self.revisions[0]
        started, release, requested = (threading.Event() for _ in range(3))

        def hold(event):
            if event["kind"] == "build_started":
                started.set()
                if not release.wait(5):
                    raise TimeoutError("build gate")

        def observe(event):
            if event["kind"] == "build_requested":
                requested.set()

        first = Simulation(self.repo, self.sim.state, speed=0, observer=hold)
        second = Simulation(self.repo, self.sim.state, speed=0, observer=observe)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(first.build, revision, "zorch")
            try:
                self.assertTrue(started.wait(5))
                b = pool.submit(second.build, revision, "zorch")
                self.assertTrue(requested.wait(5))
                key = self.sim.cache_key(revision, "zorch")
                self.assertFalse((self.sim.state / "cache" / f"{key}.json").exists())
            finally:
                release.set()
            self.assertEqual(a.result(timeout=5), b.result(timeout=5))
        kinds = [e["kind"] for e in self.sim.events()]
        self.assertEqual(kinds.count("build_started"), 1)
        self.assertEqual(kinds.count("cache_hit"), 1)
        self.assertEqual(kinds.count("build_finished"), 2)

    def test_cli_repeated_invocations(self):
        directory = self.root / "cli"
        command = [sys.executable, "-B", str(ROOT / "exercise.py"),
                   "--directory", str(directory), "--speed", "0"]
        for _ in range(2):
            subprocess.run(command, check=True, capture_output=True, cwd=self.root)
        events = [json.loads(line) for line in
                  (directory / "state/events.jsonl").read_text().splitlines()]
        builds = [e for e in events if e["kind"] == "build_finished"]
        self.assertEqual(len(builds), 18)
        self.assertTrue(all(e["cache_hit"] for e in builds[-9:]))
        release = json.loads((directory / "state/release.json").read_text())
        sim = Simulation(directory / "repo", directory / "state", speed=0)
        for app in APPS:
            sim.validate_artifact(release["revision"], app, release["artifacts"][app])


if __name__ == "__main__":
    unittest.main()
