import json
from pathlib import Path
import tempfile
import unittest

from lib.fixture import create_history, git
from lib.simulation import APPS, Simulation


class RegistryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.repo = self.root / "repo"
        self.revisions = create_history(self.repo)
        self.sim = Simulation(self.repo, self.root / "state", speed=0)

    def build_all(self, revision):
        artifacts = {}
        for app in APPS:
            artifacts[app] = self.sim.build(revision, app, artifacts.get("greeb"))
        return artifacts

    def image_path(self, revision, app):
        digest = self.sim.image_digest(revision, app)
        return self.sim.state / "registry" / "images" / f"{digest[7:]}.json"

    def tag_path(self, revision, app):
        tag = self.sim.image_tag(revision, app)
        return self.sim.state / "registry" / "tags" / f"{tag}.json"

    def release(self):
        return self.sim.deployed("blerg")

    def test_build_publishes_images_and_cache_hits_republish_tags(self):
        revision = self.revisions[0]
        artifacts = self.build_all(revision)
        for app in APPS:
            with self.subTest(app=app):
                digest = self.sim.image_digest(revision, app)
                tag = self.sim.image_tag(revision, app)
                blob = git(self.repo, "rev-parse", f"{revision}:source/{app}.txt")
                self.assertEqual(tag, f"{app}-{blob}")
                self.assertTrue(digest.startswith("sha256:"))
                self.assertEqual(len(digest), 71)
                image = self.sim.resolve_image(revision, app)
                self.assertEqual(image, self.sim.resolve_image(revision, app, "digest"))
                expected = {"app": app, "key": self.sim.cache_key(revision, app),
                            "digest": digest}
                if app == "blerg":
                    expected["greeb_key"] = self.sim.cache_key(revision, "greeb")
                self.assertEqual(image, expected)
                immutable_bytes = self.image_path(revision, app).read_bytes()
                self.tag_path(revision, app).unlink()
                self.assertEqual(self.sim.build(revision, app, artifacts.get("greeb")),
                                 artifacts[app])
                self.assertEqual(self.sim.resolve_image(revision, app), image)
                self.assertEqual(self.image_path(revision, app).read_bytes(), immutable_bytes)
                self.assertEqual(json.loads(self.tag_path(revision, app).read_text()),
                                 {"app": app, "tag": tag, "digest": digest})
                self.assertEqual(json.loads((self.sim.state / "cache" /
                                             f'{artifacts[app]["key"]}.json').read_text()),
                                 {"app": app, "key": artifacts[app]["key"]})
                events = [event for event in self.sim.events() if event.get("app") == app]
                self.assertEqual(sum(e["kind"] == "image_published" for e in events), 2)
                published, finished = events[-2:]
                self.assertEqual(published["kind"], "image_published")
                self.assertEqual((published["tag"], published["digest"]), (tag, digest))
                self.assertEqual(finished["kind"], "build_finished")
                self.assertTrue(finished["cache_hit"])

    def test_dependency_change_changes_image_but_not_own_source_tag(self):
        base, changed, same_content = self.revisions
        self.build_all(base)
        self.build_all(changed)
        self.assertEqual(self.sim.image_tag(base, "blerg"),
                         self.sim.image_tag(changed, "blerg"))
        self.assertNotEqual(self.sim.image_digest(base, "blerg"),
                            self.sim.image_digest(changed, "blerg"))
        self.assertEqual(self.sim.image_digest(changed, "blerg"),
                         self.sim.image_digest(same_content, "blerg"))
        original = self.sim.resolve_image(base, "blerg", "digest")
        updated = self.sim.resolve_image(changed, "blerg", "digest")
        self.assertNotEqual(original["greeb_key"], updated["greeb_key"])
        self.assertTrue(self.image_path(base, "blerg").exists())
        self.assertTrue(self.image_path(changed, "blerg").exists())

    def test_sequential_tag_overwrite_and_digest_resolution(self):
        base, changed, _ = self.revisions
        artifacts = self.build_all(base)
        self.build_all(changed)
        self.sim.deploy(base, "blerg", artifacts["blerg"])
        release = self.release()
        expected = self.sim.resolve_image(base, "blerg", "digest")
        actual = self.sim.resolve_image(changed, "blerg", "digest")
        self.assertEqual(release["artifact"], artifacts["blerg"])
        self.sim.validate_artifact(base, "blerg", release["artifact"])
        self.assertEqual(release["image_reference"], "tag")
        self.assertEqual(release["image"], actual)
        self.assertNotEqual(release["image"], expected)
        self.assertEqual(release["image_mismatch"], {
            "expected": expected["digest"], "actual": actual["digest"],
        })
        self.sim.deploy(base, "blerg", artifacts["blerg"], image_reference="digest")
        release = self.release()
        self.assertEqual(release["image"], expected)
        self.assertEqual(release["image_reference"], "digest")
        self.assertEqual(release["image_mismatch"], {})
        events = [event for event in self.sim.events() if event["kind"].startswith("deploy_")
                  or event["kind"] == "image_resolved"]
        self.assertEqual([event["kind"] for event in events[-4:]],
                         ["deploy_requested", "deploy_started", "image_resolved", "deploy_finished"])
        self.assertEqual(events[-2]["image"], release["image"])

    def test_invalid_app_and_reference_are_rejected(self):
        revision = self.revisions[0]
        for helper in (self.sim.image_digest, self.sim.image_tag,
                       self.sim.resolve_image, self.sim.publish_image):
            with self.subTest(helper=helper.__name__), self.assertRaises(ValueError):
                helper(revision, "unknown")
        for reference in ("latest", "sha256:bad", "../tag", None):
            with self.subTest(reference=reference):
                with self.assertRaises(ValueError):
                    self.sim.resolve_image(revision, "zorch", reference)
                with self.assertRaises(ValueError):
                    self.sim.deploy(revision, "zorch", {}, image_reference=reference)
        self.assertEqual(self.sim.events(), [])

    def test_missing_and_corrupt_tag_fail_closed(self):
        revision = self.revisions[0]
        artifacts = self.build_all(revision)
        path = self.tag_path(revision, "zorch")
        original = path.read_text()
        path.unlink()
        with self.assertRaises(ValueError):
            self.sim.resolve_image(revision, "zorch")
        for content in ("not json", "[]", "{}", json.dumps({
                "app": "zorch", "tag": self.sim.image_tag(revision, "zorch"),
                "digest": "sha256:../../escape"}), original.replace("zorch", "greeb")):
            with self.subTest(content=content):
                path.write_text(content)
                with self.assertRaises(ValueError):
                    self.sim.deploy(revision, "zorch", artifacts["zorch"])
                self.assertIsNone(self.sim.deployed("zorch"))
        self.assertEqual(self.sim.resolve_image(revision, "zorch", "digest")["digest"],
                         self.sim.image_digest(revision, "zorch"))

    def test_missing_and_corrupt_images_fail_closed_without_repair(self):
        revision = self.revisions[0]
        self.build_all(revision)
        for app in APPS:
            with self.subTest(app=app):
                path = self.image_path(revision, app)
                original = json.loads(path.read_text())
                path.unlink()
                for reference in ("tag", "digest"):
                    with self.assertRaises(ValueError):
                        self.sim.resolve_image(revision, app, reference)
                corruptions = ["not json", "[]", "{}",
                               json.dumps(dict(original, key="0" * 64)),
                               json.dumps(dict(original, digest="sha256:" + "0" * 64)),
                               json.dumps(dict(original, extra=True))]
                if app == "blerg":
                    corruptions.append(json.dumps(dict(original, greeb_key="bad")))
                for content in corruptions:
                    path.write_text(content)
                    for reference in ("tag", "digest"):
                        with self.assertRaises(ValueError):
                            self.sim.resolve_image(revision, app, reference)
                    with self.assertRaises(ValueError):
                        self.sim.publish_image(revision, app)
                    self.assertEqual(path.read_text(), content)
                path.write_text(json.dumps(original))


if __name__ == "__main__":
    unittest.main()
